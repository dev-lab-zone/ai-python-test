from pydantic import BaseModel

class IngestRequest(BaseModel):
    user_input: str

class StatusResponse(BaseModel):
    id: str
    status: str

class NotificationData(BaseModel):
    to: str
    message: str
    type: str
