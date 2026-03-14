from fastapi import FastAPI, Request
from datetime import datetime
import httpx
import json

app = FastAPI()

NEW_API_URL = "http://localhost:3000/v1"  # New API 地址

@app.post("/v1/chat/completions")
async def proxy(request: Request):
    body = await request.json()
    headers = dict(request.headers)
    
    # 注入时间信息
    time_info = f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S %A')}"
    
    messages = body.get("messages", [])
    
    # 检查是否已有 system 消息
    if messages and messages[0]["role"] == "system":
        messages[0]["content"] += f"\n{time_info}"
    else:
        messages.insert(0, {"role": "system", "content": time_info})
    
    body["messages"] = messages
    
    # 转发到 New API（保留原始 key）
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{NEW_API_URL}/chat/completions",
            json=body,
            headers={
                "Authorization": headers.get("authorization", ""),
                "Content-Type": "application/json"
            }
        )
    
    return resp.json()