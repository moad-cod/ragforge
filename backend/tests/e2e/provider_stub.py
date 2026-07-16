"""Deterministic OpenAI-compatible provider used by Task 26 E2E tests."""

from __future__ import annotations

import asyncio
import json
import time
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse


ANSWER = "RAGForge Task 26 proves the complete upload-to-answer control plane."

app = FastAPI(title="RAGForge E2E Provider")
_failure_enabled = False


class FailureControl(BaseModel):
    enabled: bool


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "failure_enabled": _failure_enabled}


@app.post("/control/failure")
def set_failure(control: FailureControl) -> dict[str, bool]:
    global _failure_enabled
    _failure_enabled = control.enabled
    return {"failure_enabled": _failure_enabled}


def _completion_payload(model: str) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": ANSWER},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 32,
            "completion_tokens": 12,
            "total_tokens": 44,
        },
    }


async def _stream_completion(model: str):
    completion_id = f"chatcmpl-{uuid.uuid4()}"
    fragments = [
        "RAGForge Task 26 proves ",
        "the complete upload-to-answer ",
        "control plane.",
    ]
    for fragment in fragments:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": fragment},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(0.01)
    final = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(payload: dict):
    if _failure_enabled:
        raise HTTPException(503, "Forced provider failure for Task 26")
    model = str(payload.get("model") or "ragforge-e2e")
    if payload.get("stream"):
        return StreamingResponse(
            _stream_completion(model),
            media_type="text/event-stream",
        )
    return _completion_payload(model)
