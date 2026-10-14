#!/usr/bin/env python3
import base64
import json
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String


# ----------------- 1. ROS 2 后台节点 -----------------
class FastAPIRosBridge(Node):

  def __init__(self):
    super().__init__('fastapi_vlm_bridge')
    self.goal_pub = self.create_publisher(String, '/high_level_target', 10)
    self.sub_img = self.create_subscription(
        CompressedImage, '/image_raw/compressed', self.img_callback, 1
    )
    self.latest_frame_base64 = None

  def img_callback(self, msg):
    self.latest_frame_base64 = base64.b64encode(msg.data).decode('utf-8')

  def publish_target(self, target_str):
    msg = String()
    msg.data = target_str
    self.goal_pub.publish(msg)
    self.get_logger().info(f'📡 [FastAPI 驱动] 下发 ROS 2 目标: [{target_str}]')


# 初始化 ROS 2 与后台线程
rclpy.init()
ros_node = FastAPIRosBridge()
ros_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
ros_thread.start()

# ----------------- 2. OpenAI API Client -----------------
client = OpenAI(
    api_key='sk-zxtbONQv0MmTWYdByz90m5YwhQfigB7xzIMc4YUNSQzHtRGL',
    base_url='https://gemai.huchan.cn/v1',
)
MODEL_NAME = '[满血A]gemini-2.5-flash'

# COCO 80 常用物体分类池
COCO_CLASSES = [
    'person',
    'bicycle',
    'car',
    'motorcycle',
    'airplane',
    'bus',
    'train',
    'truck',
    'boat',
    'bench',
    'bird',
    'cat',
    'dog',
    'backpack',
    'umbrella',
    'handbag',
    'tie',
    'suitcase',
    'bottle',
    'cup',
    'fork',
    'knife',
    'spoon',
    'bowl',
    'banana',
    'apple',
    'sandwich',
    'orange',
    'chair',
    'couch',
    'potted plant',
    'bed',
    'dining table',
    'toilet',
    'tv',
    'laptop',
    'mouse',
    'remote',
    'keyboard',
    'cell phone',
    'microwave',
    'oven',
    'sink',
    'refrigerator',
    'book',
    'clock',
    'vase',
    'scissors',
]

# ----------------- 3. FastAPI 应用构建 -----------------
app = FastAPI(title='CyberBot VLA FastAPI Server')

# 允许跨域请求 (CORS)，方便前后端独立部署
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


class ChatRequest(BaseModel):
  message: str


@app.post('/api/chat')
async def chat_endpoint(req: ChatRequest):
  user_msg = req.message

  prompt = f"""
你是一个赛博朋克风具身智能小车的 AI 智能大脑（代号：CYBER-BOT）。
【用户请求】: "{user_msg}"

【任务指示】:
1. 用带有科幻赛博风、有礼貌且酷炫的语气回复用户（字数控制在 40 字以内）。
2. 分析用户意图，判断是否包含寻找/导航到特定物体的需求：
   - 若用户属于纯闲聊（如打招呼、问你是谁等），target 输出 "none"。
   - 若用户需要导航寻物，请从以下 COCO 物体列表中挑选最匹配的一个英文单词：
     {COCO_CLASSES}

【输出格式】: 必须严格输出纯 JSON，严禁带有 markdown 标记或任何解释性文字：
{{"reply": "对用户说的话", "target": "选择的英文单词或none"}}
"""

  try:
    messages = [{'role': 'user', 'content': prompt}]

    # 如果抓取到了树莓派的摄像头帧，则注入视觉信息辅助推理
    if ros_node.latest_frame_base64:
      messages = [{
          'role': 'user',
          'content': [
              {'type': 'text', 'text': prompt},
              {
                  'type': 'image_url',
                  'image_url': {
                      'url': (
                          'data:image/jpeg;base64,'
                          f'{ros_node.latest_frame_base64}'
                      )
                  },
              },
          ],
      }]

    response = client.chat.completions.create(
        model=MODEL_NAME, messages=messages, max_tokens=150, temperature=0.7
    )

    res_text = response.choices[0].message.content.strip()
    if res_text.startswith('```json'):
      res_text = res_text.replace('```json', '').replace('```', '')

    data = json.loads(res_text)
    reply = data.get('reply', '指令已接收。')
    target = data.get('target', 'none').lower().strip()

    # 如果解析出了有效的物理目标，广播给 ROS 2 YOLO 节点
    if target != 'none':
      ros_node.publish_target(target)

    return {'status': 'success', 'reply': reply, 'target': target}

  except Exception as e:
    ros_node.get_logger().error(f'FastAPI 处理异常: {str(e)}')
    return {
        'status': 'error',
        'reply': f'系统链路异常: {str(e)}',
        'target': 'none',
    }
