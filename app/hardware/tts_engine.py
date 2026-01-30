"""
语音合成（TTS）模块
"""

import os
import tempfile
import edge_tts

class TTSEngine:
    def __init__(self, voice="zh-CN-XiaoxiaoNeural"):
        self.voice = voice
    
    def text_to_speech(self, text, output_file="output.mp3"):
        """文本转语音"""
        try:
            # 使用edge-tts
            import asyncio
            
            async def generate():
                communicate = edge_tts.Communicate(text, self.voice)
                await communicate.save(output_file)
            
            asyncio.run(generate())
            return output_file
            
        except ImportError:
            # 备用方案：使用系统命令
            print("⚠️ edge-tts不可用，使用espeak备用方案")
            self._espeak_tts(text)
            return "output.wav"
    
    def _espeak_tts(self, text):
        """使用espeak生成语音（树莓派常用）"""
        # espeak需要在树莓派上安装：sudo apt install espeak
        os.system(f'espeak -vzh "{text}" -w output.wav 2>/dev/null')
    
    def play_text(self, text):
        """直接播放文本"""
        audio_file = self.text_to_speech(text)
        
        if os.path.exists(audio_file):
            # 播放音频文件
            os.system(f"aplay {audio_file} 2>/dev/null || mpg123 {audio_file} 2>/dev/null")
            os.remove(audio_file)  # 清理临时文件