"""
树莓派硬件主程序
"""

import time
import sys
sys.path.append("..")

from app.hardware.config import HARDWARE_CONFIG
from app.hardware.audio import AudioDevice
from app.hardware.wake_detector import WakeDetector
from app.hardware.tts_engine import TTSEngine
from app.hardware.api_client import APIClient

class NavigationHardware:
    def __init__(self):
        # 初始化各模块
        self.audio = AudioDevice(HARDWARE_CONFIG["audio"])
        self.wake_detector = WakeDetector(
            use_button=True,
            button_pin=HARDWARE_CONFIG["gpio"]["wake_button_pin"]
        )
        self.tts = TTSEngine()
        self.api_client = APIClient(HARDWARE_CONFIG["api"]["base_url"])
        
        print("✅ 硬件初始化完成")
    
    def run(self):
        """主循环"""
        print("🚀 医院导引系统硬件端启动")
        
        while True:
            try:
                # 1. 等待唤醒
                if not self.wake_detector.wait_for_wake():
                    break
                
                # 2. 录音
                print("🎤 录音中...")
                audio_file = self.audio.record(duration=5)
                print(f"✅ 录音保存: {audio_file}")
                
                # 3. 语音识别
                print("🔍 识别语音...")
                text = self.api_client.recognize_speech(audio_file)
                print(f"📝 识别结果: {text}")
                
                if not text:
                    self.tts.play_text("对不起，我没有听清楚")
                    continue
                
                # 4. 理解意图（调用大模型）
                print("🤖 理解意图...")
                intent = self.api_client.understand_intent(text)
                print(f"🎯 意图: {intent}")
                
                # 5. 获取导航路径
                print("🗺️ 规划路径...")
                # 这里需要从intent中提取目的地ID，简化处理
                path_data = self.api_client.get_navigation_path(
                    start_id=1,  # 默认起点
                    end_id=3,    # 从intent中解析
                    user_type="normal"
                )
                
                # 6. 语音播报
                if path_data.get("success"):
                    instructions = path_data.get("instructions", [])
                    for instruction in instructions:
                        print(f"🔊 {instruction}")
                        self.tts.play_text(instruction)
                        time.sleep(1)  # 指令间隔
                else:
                    self.tts.play_text("抱歉，找不到路径")
                
                print("✅ 导航完成，等待下一次唤醒\n")
                
            except KeyboardInterrupt:
                print("\n👋 程序退出")
                break
            except Exception as e:
                print(f"❌ 错误: {e}")
                self.tts.play_text("系统出现错误")
                time.sleep(2)
    
    def cleanup(self):
        """清理资源"""
        self.audio.close()
        print("🧹 资源清理完成")

if __name__ == "__main__":
    hardware = NavigationHardware()
    try:
        hardware.run()
    finally:
        hardware.cleanup()