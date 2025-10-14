from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from meal_advisor import meal_advisor, init_mcp
from agents import Runner, SQLiteSession

app = FastAPI(
    title="Health Advisor API",
    description="AgenticAI + RAG (ChromaDB) backend for healthy meal advice",
    version="1.0.0",
)

# Initialize MCP (Exa) once when the API starts
@app.on_event("startup")
async def startup():
    try:
        await init_mcp()
    except Exception as e:
        print(f"[startup] MCP init warning: {e}")

@app.get("/health")
async def health():
    return {"status": "ok"}

class AdviseRequest(BaseModel):
    prompt: str # User prompt for meal advice

class AdviseResponse(BaseModel):
    output: str

@app.post("/advise", response_model=AdviseResponse)
async def advise(req: AdviseRequest):
    try:
        session = SQLiteSession("conversation_history")
        result = await Runner.run(meal_advisor, req.prompt, session=session)
        text = result.final_output
        return AdviseResponse(output=text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))