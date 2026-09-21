"""
语音识别和理解接口
供树莓派硬件调用
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional

import requests
from pydantic import BaseModel
from app.core.config import LLM_CONFIG



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
import requests
from pydantic import BaseModel
from app.core.config import LLM_CONFIG

class ChatRequest(BaseModel):
    text: str
    history: list = []

@router.post("/chat")
async def chat_with_llm(req: ChatRequest):
    """智能导诊助手：转发到 DeepSeek"""
    messages = [
        {"role": "system", "content": "你是医院智能导诊助手，用简洁中文回答患者就诊问题，并尽量给出建议目的地科室。"}
    ]
    messages += req.history
    messages.append({"role": "user", "content": req.text})

    resp = requests.post(
        LLM_CONFIG["base_url"],
        headers={"Authorization": f"Bearer {LLM_CONFIG['api_key']}"},
        json={"model": LLM_CONFIG["model"], "messages": messages},
        timeout=30
    )
    resp.raise_for_status()
    return {"reply": resp.json()["choices"][0]["message"]["content"]}