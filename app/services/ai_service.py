import asyncio
import httpx
import json
import re
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from core.config import AI_URL, NOTIFY_URL, API_KEY
from core.logging_config import logger
from models.schemas import NotificationData
from db.session import db

ai_semaphore = asyncio.Semaphore(50)

client = httpx.AsyncClient(
    timeout=httpx.Timeout(20.0, connect=5.0),
    headers={"X-API-Key": API_KEY},
    limits=httpx.Limits(max_connections=200, max_keepalive_connections=50)
)

def sanitize_ai_response(content: str) -> NotificationData:
    json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', content, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    else:
        json_obj_match = re.search(r'({.*})', content, re.DOTALL)
        if json_obj_match:
            content = json_obj_match.group(1)

    content = content.replace("'", '"')

    if content.count('{') > content.count('}'):
        content += '}'

    data = json.loads(content)

    mappings = {
        "Recipient": "to", "To": "to", "destination": "to",
        "body": "message", "Message": "message", "text": "message",
        "channel": "type", "Type": "type", "method": "type"
    }

    normalized = {}
    for k, v in data.items():
        normalized[mappings.get(k, k)] = v

    return NotificationData(**normalized)

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True
)
async def call_ai_extract(user_input: str):
    async with ai_semaphore:
        payload = {
            "messages": [
                {"role": "system", "content": "Return ONLY JSON with to, message, type"},
                {"role": "user", "content": user_input}
            ]
        }

        r = await client.post(AI_URL, json=payload)
        r.raise_for_status()
        return r.json()

# --- NOTIFY (NO BLOQUEANTE) ---
async def send_notification(data: NotificationData):
    try:
        await client.post(
            NOTIFY_URL,
            json=data.model_dump(),
            timeout=5.0
        )
    except Exception as e:
        logger.error(f"notify error: {e}")

# --- WORKER ASYNC ---
async def process_ai_request_task(request_id: str):
    request_entry = db.get(request_id)
    if not request_entry:
        return

    db[request_id]["status"] = "processing"

    try:
        ai_raw = await call_ai_extract(request_entry["input"])
        content = ai_raw["choices"][0]["message"]["content"]

        structured = sanitize_ai_response(content)

        asyncio.create_task(send_notification(structured))

        db[request_id]["status"] = "sent"
        logger.info(f"OK {request_id}")

    except Exception as e:
        db[request_id]["status"] = "failed"
        logger.error(f"FAIL {request_id}: {e}")
