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
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{NEW_API_URL}/models",
            headers={"Authorization": auth}
        )
    return JSONResponse(content=resp.json())

@app.post("/v1/chat/completions")
async def proxy(request: Request):
    body = await request.json()
    auth = request.headers.get("authorization", "")

    body["messages"] = inject_time(body.get("messages", []))
    is_stream = body.get("stream", False)

    if is_stream:
        async def stream_generator():
            done_sent = False
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST",
                        f"{NEW_API_URL}/chat/completions",
                        json=body,
                        headers={
                            "Authorization": auth,
                            "Content-Type": "application/json",
                        },
                    ) as resp:
                        # ✅ 按行迭代，保证每次 yield 是完整的 SSE 行
                        async for line in resp.aiter_lines():
                            if line:
                                yield f"{line}\n\n"
                                if "data: [DONE]" in line:
                                    done_sent = True
            except Exception as e:
                print(f"流式传输异常: {e}")
            finally:
                # ✅ 兜底：确保 [DONE] 一定被发送，Open WebUI 才会停转
                if not done_sent:
                    yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            # ✅ 关键响应头，防止 nginx 等缓冲 SSE
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    else:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{NEW_API_URL}/chat/completions",
                json=body,
                headers={
                    "Authorization": auth,
                    "Content-Type": "application/json",
                },
            )
        return JSONResponse(content=resp.json())

if __name__ == "__main__":
    import uvicorn
    print("启动代理服务...")
    uvicorn.run(app, host="0.0.0.0", port=25144)