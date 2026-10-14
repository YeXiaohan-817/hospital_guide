"""
硬件配置
"""

HARDWARE_CONFIG = {
    # 音频设备索引（树莓派通常是0或1）
    "audio": {
        "input_device_index": 0,    # 麦克风
        "output_device_index": 0,   # 扬声器
        "sample_rate": 16000,       # 采样率
        "chunk_size": 1024          # 缓冲区大小
    },
    
    # GPIO引脚配置（树莓派）
    "gpio": {
        "wake_button_pin": 17,      # 唤醒按钮GPIO17
        "led_pin": 18               # 状态灯GPIO18
    },
    
    # 云端API地址
    "api": {
        "base_url": "http://127.0.0.1:8000",  # 本地测试
        "speech_endpoint": "/api/v1/speech/recognize",
        "understand_endpoint": "/api/v1/speech/understand",
        "plan_endpoint": "/api/v1/plan"
    }
}