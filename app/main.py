from fastapi import FastAPI
from api.endpoints import router as api_router
from services.ai_service import client

app = FastAPI(title="AI Notification Service")

app.include_router(api_router, prefix="/v1")

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()