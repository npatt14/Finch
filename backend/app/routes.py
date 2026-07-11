from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.graph import chat_answer
from app.ingest import extract_text
from app.models import VerificationReport

router = APIRouter()


class ChatRequest(BaseModel):
    thread_id: str
    message: str


def _ndjson(obj) -> str:
    return json.dumps(obj, default=str) + "\n"


@router.post("/api/verify")
async def verify(request: Request, file: UploadFile | None = None, text: str | None = Form(None)):
    services = request.app.state.services
    graph = request.app.state.graph
    if services is None or graph is None:
        detail = getattr(request.app.state, "config_error", None) or "verification service not configured"
        raise HTTPException(status_code=503, detail=detail)
    data = await file.read() if file else None
    try:
        brief_text = extract_text(file.filename if file else None, data, text, services.settings.max_chars)
    except ValueError:
        raise HTTPException(status_code=400, detail="empty document")

    thread_id = uuid.uuid4().hex[:12]
    config = {"configurable": {"thread_id": thread_id}}

    def gen():
        yield _ndjson({"type": "start", "thread_id": thread_id})
        results = []
        warnings: list[str] = []
        for update in graph.stream({"text": brief_text, "session_id": thread_id}, config, stream_mode="updates"):
            if "extract" in update:
                payload = update["extract"]
                warnings = payload.get("warnings", [])
                yield _ndjson({"type": "units", "units": payload.get("units", []), "warnings": warnings})
            if "verify_unit" in update:
                for r in update["verify_unit"].get("results", []):
                    results.append(r)
                    yield _ndjson({"type": "result", "result": r})
        report = VerificationReport(
            thread_id=thread_id,
            warnings=warnings,
            results=sorted(results, key=lambda r: r["unit_id"]),
        )
        yield _ndjson({"type": "done", "report": report.model_dump()})

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.post("/api/chat")
def chat(request: Request, body: ChatRequest):
    services = request.app.state.services
    graph = request.app.state.graph
    if services is None or graph is None:
        detail = getattr(request.app.state, "config_error", None) or "verification service not configured"
        raise HTTPException(status_code=503, detail=detail)
    answer = chat_answer(services, graph, body.thread_id, body.message)
    return {"answer": answer}
