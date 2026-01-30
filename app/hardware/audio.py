"""
音频录制和播放基础类
"""

import pyaudio
import wave
import time

class AudioDevice:
    def __init__(self, config):
        self.config = config
        self.audio = pyaudio.PyAudio()
    
    def list_devices(self):
        """列出所有音频设备"""
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            print(f"{i}: {info['name']}")
    
    def record(self, duration=5, filename="record.wav"):
        """录制音频"""
        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.config["sample_rate"],
            input=True,
            input_device_index=self.config["input_device_index"],
            frames_per_buffer=self.config["chunk_size"]
        )
        
        frames = []
        for _ in range(0, int(self.config["sample_rate"] / self.config["chunk_size"] * duration)):
            frames.append(stream.read(self.config["chunk_size"]))
        
        stream.stop_stream()
        stream.close()
        
        # 保存文件
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.config["sample_rate"])
            wf.writeframes(b''.join(frames))
        
        return filename
    
    def play(self, filename):
        """播放音频文件"""
        wf = wave.open(filename, 'rb')
        stream = self.audio.open(
            format=self.audio.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True,
            output_device_index=self.config["output_device_index"]
        )
        
        data = wf.readframes(self.config["chunk_size"])
        while data:
            stream.write(data)
            data = wf.readframes(self.config["chunk_size"])
        
        stream.stop_stream()
        stream.close()
        wf.close()
    
    def close(self):
        self.audio.terminate()