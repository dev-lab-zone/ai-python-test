import uuid
import asyncio
from fastapi import APIRouter, HTTPException, status
from models.schemas import IngestRequest, StatusResponse
from db.session import db
from services.ai_service import process_ai_request_task

router = APIRouter()

@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def ingest_request(req: IngestRequest):
    request_id = str(uuid.uuid4())

    db[request_id] = {
        "id": request_id,
        "status": "queued",
        "input": req.user_input
    }

    return {"id": request_id}

@router.post("/requests/{id}/process", status_code=status.HTTP_202_ACCEPTED)
async def process_request(id: str):
    if id not in db:
        raise HTTPException(status_code=404, detail="Not found")

    if db[id]["status"] not in ["processing", "sent"]:
        asyncio.create_task(process_ai_request_task(id))

    return {"id": id, "status": "queued"}

@router.get("/requests/{id}", response_model=StatusResponse)
async def get_status(id: str):
    if id not in db:
        raise HTTPException(status_code=404, detail="Not found")

    return {"id": id, "status": db[id]["status"]}
