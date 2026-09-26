from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from workflow import workflow_app

app = FastAPI(title="AI Learning Pipeline")

class TopicRequest(BaseModel):
    topic: str

@app.get("/")
def root():
    return {"msg": "Hello, API is running"}

@app.post("/generate")
async def generate_learning_material(request: TopicRequest):
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
    
    initial_state = {
        "topic": request.topic,
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