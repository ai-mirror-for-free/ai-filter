from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import copy
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

NEW_API_URL = "http://localhost:25142/v1"

_INJECTION_MARKER = "<!-- __time_injected__ -->"

def inject_time(messages: list) -> list:
    now = datetime.now()
    time_info = (
        f"{_INJECTION_MARKER}\n"
        f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}，"
        f"{['周一','周二','周三','周四','周五','周六','周日'][now.weekday()]}"
    )
    # 深拷贝，避免修改原列表
    messages = copy.deepcopy(messages)
    if messages and messages[0]["role"] == "system":
        messages[0]["content"] = time_info + "\n" + messages[0]["content"]
    else:
        messages.insert(0, {"role": "system", "content": time_info})
    return messages


@app.get("/v1/models")
async def models(request: Request):
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() in ("authorization", "new-api-user", "accesstoken", "content-type")
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{NEW_API_URL}/models",
            headers=headers,
        )
    if resp.status_code != 200:
        return JSONResponse(
            content=resp.json(),
            status_code=resp.status_code,
        )
    return JSONResponse(content=resp.json())


@app.post("/v1/chat/completions")
async def proxy(request: Request):
    body = await request.json()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() in ("authorization", "new-api-user", "accesstoken", "content-type")
    }

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
                        headers=headers,
                    ) as resp:
                        if resp.status_code != 200:
                            try:
                                error_body = resp.json()
                            except Exception:
                                error_body = {"error": "上游服务返回非 200 状态码"}
                            yield f"data: {error_body}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        async for line in resp.aiter_lines():
                            if line:
                                yield f"{line}\n\n"
                                if "data: [DONE]" in line:
                                    done_sent = True
            except Exception as e:
                print(f"流式传输异常: {e}")
                import traceback
                traceback.print_exc()
                yield 'data: {"error": "上游服务异常"}\n\n'
            finally:
                if not done_sent:
                    yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{NEW_API_URL}/chat/completions",
                json=body,
                headers=headers,
            )
        if resp.status_code != 200:
            return JSONResponse(
                content=resp.json(),
                status_code=resp.status_code,
            )
        return JSONResponse(content=resp.json())


if __name__ == "__main__":
    import uvicorn
    print("启动代理服务...")
    uvicorn.run(app, host="0.0.0.0", port=25144)
