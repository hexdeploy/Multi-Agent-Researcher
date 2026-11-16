import os
import json
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import iterate_in_threadpool
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from graph.workflow import build_research_graph

load_dotenv()

app = FastAPI(
    title="Autonomous Multi-Agent Research Assistant API",
    description="LangGraph + Groq research automation pipeline with HITL approval and live SSE streaming.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

research_app = build_research_graph()


class ResearchRequest(BaseModel):
    topic: str = Field(..., description="The research topic to investigate.")


class ResumeRequest(BaseModel):
    thread_id: str = Field(..., description="Active LangGraph checkpoint thread ID.")
    approved_plan: str = Field(..., description="User-reviewed or edited research plan.")


@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "Multi-Agent Research Assistant API",
        "model": os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile"),
    }


def _sync_stream_start(initial_state: dict, config: dict, thread_id: str):
    try:
        for event in research_app.stream(initial_state, config=config):
            for node_name, node_state in event.items():
                yield f"data: {json.dumps({'node': node_name, 'state': node_state, 'thread_id': thread_id})}\n\n"

        snapshot = research_app.get_state(config)
        if snapshot.next and "researcher" in snapshot.next:
            yield f"data: {json.dumps({'status': 'awaiting_approval', 'thread_id': thread_id, 'plan': snapshot.values.get('research_plan', '')})}\n\n"
        else:
            yield f"data: {json.dumps({'status': 'completed'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


def _sync_stream_resume(config: dict, thread_id: str, approved_plan: str):
    try:
        research_app.update_state(config, {"research_plan": approved_plan})
        for event in research_app.stream(None, config=config):
            for node_name, node_state in event.items():
                yield f"data: {json.dumps({'node': node_name, 'state': node_state, 'thread_id': thread_id})}\n\n"

        yield f"data: {json.dumps({'status': 'completed'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@app.post("/api/stream-research")
async def stream_research(request: ResearchRequest):
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Research topic cannot be empty.")

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "topic": request.topic.strip(),
        "research_plan": "",
        "raw_research": "",
        "fact_check_result": "",
        "confidence_score": "HIGH",
        "analysis": "",
        "final_report": "",
        "retry_count": 0,
    }

    return StreamingResponse(
        iterate_in_threadpool(_sync_stream_start(initial_state, config, thread_id)),
        media_type="text/event-stream",
    )


@app.post("/api/resume-research")
async def resume_research(request: ResumeRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    return StreamingResponse(
        iterate_in_threadpool(_sync_stream_resume(config, request.thread_id, request.approved_plan)),
        media_type="text/event-stream",
    )