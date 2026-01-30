"""
语音识别和理解接口
供树莓派硬件调用
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional

router = APIRouter()

@router.post("/recognize")
async def recognize_speech(
    audio: UploadFile = File(...)
):
    """
    语音识别接口
    接收音频文件，返回识别文本
    """
    # 保存上传的音频文件
    audio_data = await audio.read()
    
    # TODO: 调用百度ASR API
    # 这里需要大模型同学的百度API密钥
    
    # 模拟返回
    return {"text": "我要去放射科"}

@router.post("/understand")
async def understand_intent(
    text: str
):
    """
    意图理解接口
    接收文本，返回结构化意图
    """
    # TODO: 调用大模型API
    # 这里需要大模型同学的文心一言API
    
    # 模拟返回
    return {
        "destination": "放射科",
        "destination_id": 3,  # 对应数据库中的位置ID
        "action": "导航",
        "user_type": "normal"
    }