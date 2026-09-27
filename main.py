import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any

from workflow import workflow_app
from pdf_generator import build_pdf_bytes

app = FastAPI(title="AI Learning Pipeline")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (css, js, assets)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

class TopicRequest(BaseModel):
    topic: str

class ExportPdfRequest(BaseModel):
    topic: str
    result: Dict[str, Any]

@app.get("/")
async def root():
    index_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"msg": "AI Learning Pipeline API is running. index.html not found."}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
    }

@app.post("/generate")
async def generate_learning_material(request: TopicRequest):
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
    
    initial_state = {
        "topic": topic,
        "learning_objectives": "",
        "explanation": "",
        "analogy": "",
        "technical_explanation": "",
        "code_example": "",
        "quiz": "",
        "answers": "",
        "revision_notes": ""
    }

    try:
        final_state = workflow_app.invoke(initial_state)
        return final_state
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export-pdf")
async def export_pdf(request: ExportPdfRequest):
    topic = request.topic.strip() or "Learning Module"
    try:
        pdf_bytes = build_pdf_bytes(request.result, topic)
        safe_filename = re.sub(r"[^a-zA-Z0-9]+", "_", topic).strip("_").lower() or "learning_module"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}.pdf"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")