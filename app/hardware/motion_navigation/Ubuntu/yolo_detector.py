#!/usr/bin/env python3
import math
import cv2
from cv_bridge import CvBridge
from geometry_msgs.msg import Point
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
from ultralytics import YOLO


class YoloNavigationNode(Node):

    def __init__(self):
        super().__init__('yolo_navigation_node')

        # 1. 订阅压缩图像与大模型目标指令
        self.sub_img = self.create_subscription(
            CompressedImage,
            '/image_raw/compressed',
            self.image_callback,
            qos_profile_sensor_data,
        )
        self.sub_target = self.create_subscription(
            String, '/high_level_target', self.target_callback, 10
        )

        # 2. 发布目标视觉矢量 (仅供 APF 导航节点使用，不直接发布 /cmd_vel)
        self.target_pub = self.create_publisher(Point, '/yolo_target_vector', 10)

        self.bridge = CvBridge()
        self.model = YOLO('yolov8s.pt')
        self.target_class = 'chair'

        self.camera_fov_rad = math.radians(60.0)
        self.tolerance_deg = 12.0
        self.tolerance_rad = math.radians(self.tolerance_deg)

        self.enable_gui = True
        if self.enable_gui:
            cv2.namedWindow('YOLO Target Tracking', cv2.WINDOW_NORMAL)

        self.is_processing = False

        # 🎯 视觉缓存防抖与空间几何记忆
        self.last_target_center = None
        self.cached_detections = []
        self.max_ttl = 8  # TTL 维持帧数

        self.get_logger().info(
            '🚀 YOLO 节点已升级：左侧输出正角偏差 (+rad, 驱动左转) | 右侧输出负角偏差 (-rad, 驱动右转)'
        )

    def target_callback(self, msg):
        new_target = msg.data.strip().lower()
        if new_target != self.target_class:
            self.target_class = new_target
            self.last_target_center = None
            self.get_logger().info(f'🔄 目标类别更新为: [{self.target_class}]')

    def image_callback(self, msg):
        if self.is_processing:
            return

        self.is_processing = True
        try:
            self.process_image(msg)
        finally:
            self.is_processing = False

    def process_image(self, msg):
        try:
            np_arr = self.bridge.compressed_imgmsg_to_cv2(msg, 'bgr8')
        except Exception as e:
            self.get_logger().error(f'图像解码失败: {e}')
            return

        if len(np_arr.shape) == 2:
            np_arr = cv2.cvtColor(np_arr, cv2.COLOR_GRAY2BGR)

        h, w = np_arr.shape[:2]
        img_center_x = w / 2.0

        # 1. 执行 YOLO 推理
        results = self.model(np_arr, imgsz=320, verbose=False)

        current_detections = []
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                label = self.model.names[cls_id].lower()
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                current_detections.append({
                    'label': label,
                    'conf': conf,
                    'box': [x1, y1, x2, y2],
                    'ttl': self.max_ttl,
                })

        # 2. 帧间缓存处理
        if current_detections:
            self.cached_detections = current_detections
        else:
            for det in self.cached_detections:
                det['ttl'] -= 1
            self.cached_detections = [
                det for det in self.cached_detections if det['ttl'] > 0
            ]

        # 3. 目标智配逻辑
        best_candidate = None
        min_dist = float('inf')

        for det in self.cached_detections:
            x1, y1, x2, y2 = det['box']
            label = det['label']
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

            is_class_match = label == self.target_class
            is_spatial_match = False

            if self.last_target_center is not None:
                dist_to_last = math.hypot(
                    cx - self.last_target_center[0], cy - self.last_target_center[1]
                )
                if dist_to_last < (w * 0.40):
                    is_spatial_match = True

            if is_class_match or is_spatial_match:
                dist = (
                    math.hypot(
                        cx - self.last_target_center[0], cy - self.last_target_center[1]
                    )
                    if self.last_target_center
                    else abs(cx - img_center_x)
                )
                if dist < min_dist:
                    min_dist = dist
                    best_candidate = det

        target_msg = Point()
        display_img = np_arr if self.enable_gui else None

        # 4. 计算并封装目标相对矢量（符号物理绑定：左正右负）
        if best_candidate is not None:
            x1, y1, x2, y2 = best_candidate['box']
            label = best_candidate['label']
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            box_height = y2 - y1

            self.last_target_center = (cx, cy)

            # 💡 物理规则：
            # cx < img_center_x (左侧) -> error_x > 0 -> angle_offset > 0 (+w 驱动底盘左转)
            # cx > img_center_x (右侧) -> error_x < 0 -> angle_offset < 0 (-w 驱动底盘右转)
            error_x = img_center_x - cx
            angle_offset = (error_x / img_center_x) * (self.camera_fov_rad / 2.0)
            estimated_dist = max(0.15, 1.0 - (box_height / float(h)))

            target_msg.x = float(angle_offset)
            target_msg.y = float(estimated_dist)
            target_msg.z = 1.0  # z=1.0 代表成功捕获目标

            if self.enable_gui and display_img is not None:
                is_aligned = abs(angle_offset) <= self.tolerance_rad
                dir_str = (
                    'CENTER' if is_aligned else ('LEFT' if angle_offset > 0 else 'RIGHT')
                )
                status_text = f'DIR: {dir_str} ({math.degrees(angle_offset):.1f}deg)'
                status_color = (0, 255, 0) if is_aligned else (0, 0, 255)
                cv2.putText(
                    display_img,
                    status_text,
                    (int(cx) - 60, int(cy) - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    status_color,
                    2,
                )
        else:
            target_msg.x = 0.0
            target_msg.y = 1.5
            target_msg.z = 0.0  # z=0.0 代表未捕获到目标
            self.last_target_center = None

        # 5. 渲染可视化界面
        if self.enable_gui and display_img is not None:
            for det in self.cached_detections:
                x1, y1, x2, y2 = det['box']
                label = det['label']
                conf = det['conf']
                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

                cv2.rectangle(
                    display_img,
                    (int(x1), int(y1)),
                    (int(x2), int(y2)),
                    (0, 255, 0),
                    2,
                )
                cv2.circle(display_img, (int(cx), int(cy)), 5, (0, 0, 255), -1)

                text_str = f'{label} {conf:.2f}'
                (text_w, text_h), baseline = cv2.getTextSize(
                    text_str, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                )
                text_y = max(int(y1), text_h + 5)

                cv2.rectangle(
                    display_img,
                    (int(x1), text_y - text_h - 4),
                    (int(x1) + text_w + 4, text_y + baseline),
                    (0, 255, 0),
                    -1,
                )
                cv2.putText(
                    display_img,
                    text_str,
                    (int(x1) + 2, text_y - 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 0),
                    1,
                )

            # 绘制中心线与容忍范围绿线界线
            offset_pixels = int(
                (self.tolerance_rad / (self.camera_fov_rad / 2.0)) * img_center_x
            )
            cv2.line(
                display_img,
                (int(img_center_x), 0),
                (int(img_center_x), h),
                (0, 255, 255),
                2,
            )
            cv2.line(
                display_img,
                (int(img_center_x - offset_pixels), 0),
                (int(img_center_x - offset_pixels), h),
                (0, 255, 0),
                1,
            )
            cv2.line(
                display_img,
                (int(img_center_x + offset_pixels), 0),
                (int(img_center_x + offset_pixels), h),
                (0, 255, 0),
                1,
            )

            cv2.imshow('YOLO Target Tracking', display_img)
            cv2.waitKey(1)

        self.target_pub.publish(target_msg)

    def destroy_node(self):
        if self.enable_gui:
            cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = YoloNavigationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
