"""
唤醒词检测（简化版，用按钮模拟）
"""

import time

class WakeDetector:
    def __init__(self, use_button=True, button_pin=17):
        self.use_button = use_button
        self.button_pin = button_pin
        
        if use_button:
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                self.has_gpio = True
            except:
                self.has_gpio = False
                print("⚠️ GPIO不可用，使用键盘模拟")
    
    def wait_for_wake(self):
        """等待唤醒信号"""
        if self.use_button and self.has_gpio:
            return self._wait_for_button()
        else:
            return self._wait_for_keyboard()
    
    def _wait_for_button(self):
        """等待按钮按下"""
        import RPi.GPIO as GPIO
        print("🔄 等待按钮唤醒...")
        
        while True:
            if GPIO.input(self.button_pin) == GPIO.LOW:
                print("🔘 按钮按下，开始录音")
                return True
            time.sleep(0.1)
    
    def _wait_for_keyboard(self):
        """等待键盘输入（开发测试用）"""
        print("🔄 按回车键开始录音，或输入'q'退出")
        
        while True:
            cmd = input("> ")
            if cmd == '':
                return True
            elif cmd.lower() == 'q':
                return False
            else:
                print("输入回车开始，或'q'退出")