"""
调用云端API的客户端
"""

import requests
import json

class APIClient:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url
    
    def recognize_speech(self, audio_file_path):
        """上传音频进行语音识别"""
        url = f"{self.base_url}/api/v1/speech/recognize"
        
        with open(audio_file_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            response = requests.post(url, files=files)
        
        if response.status_code == 200:
            return response.json().get('text', '')
        else:
            raise Exception(f"语音识别失败: {response.text}")
    
    def understand_intent(self, text):
        """理解用户意图（调用大模型）"""
        url = f"{self.base_url}/api/v1/speech/understand"
        
        data = {'text': text}
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"意图理解失败: {response.text}")
    
    def get_navigation_path(self, start_id, end_id, user_type="normal"):
        """获取导航路径（复用现有接口）"""
        url = f"{self.base_url}/api/v1/plan"
        
        data = {
            'start_id': start_id,
            'end_id': end_id,
            'user_type': user_type
        }
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"路径规划失败: {response.text}")
