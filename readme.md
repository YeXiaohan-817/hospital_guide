# 🏥 医院智能导航系统 - 完整项目文档

## 📋 项目概述
**项目名称**：医院三维智能导航系统  
**技术架构**：FastAPI + SQLAlchemy + 智能算法 + 硬件集成  
**开发模式**：前后端分离，多模块协同开发  

## 🏗️ 项目结构
```
hospital_guide/                      # 项目根目录
├── app/                            # 后端核心代码
│   ├── api/endpoints/              # REST API接口
│   │   ├── health.py              # 健康检查
│   │   ├── auth.py                # 用户认证
│   │   ├── map.py                 # 地图数据接口
│   │   ├── navigation.py          # 导航任务接口
│   │   ├── robots.py              # 导引小车接口
│   │   └── speech.py              # ✅ 新增：语音服务接口
│   ├── algorithms/                 # ✅ 智能路径算法
│   │   ├── path_finder.py         # A*算法 + 动态权重
│   │   └── __init__.py
│   ├── core/                       # 核心工具
│   │   ├── config.py              # 算法配置
│   │   ├── graph.py               # 图数据结构
│   │   └── __init__.py
│   ├── hardware/                  # ✅ 新增：硬件模块
│   │   ├── audio.py               # 音频录制/播放
│   │   ├── wake_detector.py       # 唤醒词检测
│   │   ├── tts_engine.py          # 语音合成
│   │   ├── api_client.py          # API调用客户端
│   │   ├── main_hardware.py       # 硬件主程序
│   │   └── config.py              # 硬件配置
│   ├── services/                  # ✅ 新增：服务层
│   │   ├── speech_service.py      # 待实现：语音服务
│   │   ├── llm_service.py         # 待实现：大模型服务
│   │   └── __init__.py
│   ├── models.py                  # 数据库模型
│   ├── schemas.py                 # Pydantic模型
│   ├── database.py                # 数据库连接
│   └── main.py                    # FastAPI应用入口
├── docs/                          # 项目文档
│   └── 大模型对接指南.md           # ✅ 大模型同学必读
├── requirements.txt               # Python依赖包
└── README.md                      # 本文档
```

## 👥 各角色职责与接入指南

### 👨‍💻 **前端同学** - 三维界面开发
#### 🎯 你的任务
在三维地图中显示导航路径，提供用户交互界面。

#### 🔗 需要调用的核心接口
```javascript
// 1. 获取所有地点（用于地图标记）
GET /api/v1/locations

// 2. 智能路径规划（核心）
POST /api/v1/plan
请求体：
{
  "start_id": 1,
  "end_id": 3,
  "user_type": "wheelchair",  // wheelchair, emergency, elderly, normal, staff
  "preferences": {"avoid_crowds": true}
}

// 3. 创建导航任务（多点导航）
POST /api/v1/navigation/tasks
请求体：
{
  "user_id": 1,
  "location_ids": [1, 2, 3],
  "user_type": "wheelchair"
}
```

#### 📍 坐标系统说明
- **单位**：1单位 = 1米
- **原点**：医院西南角地面点 (0,0,0)
- **Z轴**：楼层 × 3.0米（1楼Z=0，2楼Z=3.0）
- **响应格式**：
```json
{
  "path": [
    {"x": 0, "y": 0, "z": 0, "floor": 1, "name": "起点"},
    {"x": 10, "y": 5, "z": 3, "floor": 2, "name": "电梯"}
  ]
}
```

#### 🚀 快速开始
1. **启动测试环境**：`uvicorn app.main:app --reload`
2. **测试连接**：`http://127.0.0.1:8000/docs`
3. **获取测试数据**：调用 `/api/v1/locations`
4. **绘制路径**：调用 `/api/v1/plan` 获取坐标点

---

### 🤖 **大模型同学** - 意图理解服务
#### 🎯 你的任务
提供语音识别和意图理解服务，将用户语音转换为结构化导航指令。

#### 📁 需要实现的文件
1. **`app/services/speech_service.py`** - 语音识别服务
2. **`app/services/llm_service.py`** - 大模型意图理解

#### 🔑 需要配置的API密钥
```python
# 百度语音识别
BAIDU_ASR_CONFIG = {
    "APP_ID": "你的APP_ID",
    "API_KEY": "你的API_KEY",
    "SECRET_KEY": "你的SECRET_KEY"
}

# 文心一言API
ERNIE_API_CONFIG = {
    "api_key": "你的API_KEY",
    "secret_key": "你的SECRET_KEY"
}
```

#### 📡 需要实现的接口
```python
# 1. 语音识别接口
POST /api/v1/speech/recognize
输入：音频文件(WAV)
输出：{"text": "我要去缴费处"}

# 2. 意图理解接口  
POST /api/v1/speech/understand
输入：{"text": "我要去缴费处"}
输出：{
  "destination": "缴费处",
  "destination_id": 5,
  "user_type": "normal",
  "action": "导航"
}
```

#### 📚 详细指南
见 `docs/大模型对接指南.md` 文档。

---

### 🔌 **硬件同学** - 树莓派硬件端
#### 🎯 你的任务
在树莓派上实现语音交互硬件客户端。

#### 📁 已提供的模块
```
app/hardware/
├── audio.py              # 音频录制和播放
├── wake_detector.py      # 唤醒检测（支持按钮/键盘）
├── tts_engine.py         # 语音合成（edge-tts/espeak）
├── api_client.py         # 云端API调用
└── main_hardware.py      # 主程序
```

#### 🔧 硬件配置
```python
# app/hardware/config.py
HARDWARE_CONFIG = {
    "audio": {
        "input_device_index": 0,    # 麦克风设备索引
        "output_device_index": 0,   # 扬声器设备索引
    },
    "gpio": {
        "wake_button_pin": 17,      # GPIO唤醒按钮
        "led_pin": 18               # 状态指示灯
    }
}
```

#### 🚀 运行步骤
1. **安装依赖**：
   ```bash
   sudo apt install espeak
   pip install pyaudio edge-tts requests
   ```

2. **配置API地址**：修改 `config.py` 中的云端地址

3. **运行程序**：
   ```bash
   cd /home/silver/navigation_project
   python -m app.hardware.main_hardware
   ```

4. **测试流程**：
   - 按下GPIO17按钮或按回车键
   - 说出目的地（如"我要去放射科"）
   - 收听语音导航指令

---

## 🚀 快速启动指南

### 1. 环境准备
```bash
# 克隆项目
git clone https://github.com/YeXiaohan-817/hospital_guide.git
cd hospital_guide

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python init_test.py
```

### 2. 启动后端服务
```bash
# 开发环境
uvicorn app.main:app --reload

# 生产环境（允许远程访问）
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. 接口测试
```bash
# 测试健康检查
curl http://127.0.0.1:8000/api/v1/health

# 测试智能路径
curl -X POST http://127.0.0.1:8000/api/v1/plan \
  -H "Content-Type: application/json" \
  -d '{"start_id":1,"end_id":3,"user_type":"wheelchair"}'

# 查看API文档
http://127.0.0.1:8000/docs
```

## 📊 测试数据
- **用户**：ID=1, username=test_user
- **地点**：ID 1-8（门诊大厅、药房、放射科、电梯等）
- **路径**：已建立完整路径网络
- **机器人**：导引车01-03

## 🔗 项目资源
- **GitHub仓库**：https://github.com/YeXiaohan-817/hospital_guide
- **API文档**：启动服务后访问 `/docs`
- **问题反馈**：GitHub Issues

## 📞 协作沟通
- **每日站会**：10分钟进度同步
- **技术评审**：每周一次接口对齐
- **紧急问题**：直接联系对应模块负责人

---

## 🎯 当前项目状态
- ✅ 后端核心框架完成
- ✅ 智能路径算法实现
- ✅ API接口文档化
- ✅ 硬件模块框架搭建
- 🔄 前端三维界面开发中
- 🔄 大模型意图理解开发中
- 🔄 树莓派硬件集成测试中

**各角色按上述指南开始工作，有问题及时沟通！**

---
*最后更新：2024年7月*  
*维护者：YeXiaohan-817*