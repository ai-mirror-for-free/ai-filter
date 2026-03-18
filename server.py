from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NEW_API_URL = "http://localhost:25142/v1"

def inject_time(messages: list) -> list:
    now = datetime.now()
    time_info = (
        f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}，"
        f"{['周一','周二','周三','周四','周五','周六','周日'][now.weekday()]}"
    )
    if messages and messages[0]["role"] == "system":
        messages[0]["content"] += f"\n{time_info}"
    else:
        messages.insert(0, {"role": "system", "content": time_info})
    return messages

@app.get("/v1/models")
async def models(request: Request):
    auth = request.headers.get("authorization", "")
    
    # 临时调试：打印收到的 headers
    print(f"收到的 Authorization: {auth}")
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{NEW_API_URL}/models",
            headers={"Authorization": auth}
        )
    
    print(f"New API 返回: {resp.status_code} {resp.text[:200]}")
    return JSONResponse(content=resp.json())

@app.post("/v1/chat/completions")
async def proxy(request: Request):
    body = await request.json()
    auth = request.headers.get("authorization", "")
    
    body["messages"] = inject_time(body.get("messages", []))
    
    is_stream = body.get("stream", False)
    
    if is_stream:
        async def stream_generator():
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{NEW_API_URL}/chat/completions",
                    json=body,
                    headers={
                        "Authorization": auth,
                        "Content-Type": "application/json"
                    }
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream"
        )
    else:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{NEW_API_URL}/chat/completions",
                json=body,
                headers={
                    "Authorization": auth,
                    "Content-Type": "application/json"
                }
            )
        return JSONResponse(content=resp.json())
    
if __name__ == "__main__":
    import uvicorn
    print("启动代理服务...")
    uvicorn.run(app, host="0.0.0.0", port=25144)