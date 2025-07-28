# THIS IS THE CONTROL SERVER THAT INTERACTS WITH THE DATABASE (TEXT FILE)
import json, time, pathlib
import httpx
from typing import List
from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import uvicorn
EVENTS_FILE = pathlib.Path("events.txt")
RELAY_URL = "http://172.20.10.2:8001/relay/events"
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # or your UI origin
    allow_methods=["*"],
    allow_headers=["*"],
)
connectionMap = {
}
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
    async def broadcast_led(self, state: bool):
        for ws in list(self.active):
            await ws.send_text("1" if state else "0")
    async def broadcast_json(self, data: dict):
        text = json.dumps(data)
        for ws in list(self.active):
            await ws.send_text(text)

manager = ConnectionManager()

@app.on_event("startup")
async def start_background_tasks():
    # Schedule your loop as soon as the app starts
    app.state.relay_client = httpx.AsyncClient()
    asyncio.create_task(verifyActiveConnections())
@app.on_event("shutdown")
async def shutdown_background_tasks():
    # Cleanup tasks when the app shuts down
    await app.state.relay_client.aclose()

async def verifyActiveConnections():
    while True:
        current_time = time.time()
        for data, timestamp in list(connectionMap.items()):
            if current_time - timestamp > 10:  # 10 seconds timeout
                # print(f"Connection timed out: {data}")
                record = {
                    "timestamp": current_time,
                    "device_id": data,
                    "event_type": "disconnected",
                }
                # send disctionnection event to relay
                sendRelayUpdate(data, "disconnected")
                updateDatabase(record)
                del connectionMap[data]
        await asyncio.sleep(5)  # Check every 10 seconds

def updateDatabase(record):
    with EVENTS_FILE.open("a") as f:
        f.write(json.dumps(record) + "\n")

async def verifyConnection(data, timestamp):
    if data in connectionMap:
        connectionMap[data] = timestamp
    else:
        connectionMap[data] = timestamp
def sendRelayUpdate(device_id, event_type):
    payload = { "device_id": device_id, "event_type": event_type }
    asyncio.create_task(app.state.relay_client.post(RELAY_URL, json=payload))


def updateConnection(data, timestamp):
    if data not in connectionMap:
        # send relay new connection event
        sendRelayUpdate(data, "connected")
    connectionMap[data] = timestamp


# — HTTP endpoint to render the file contents —
@app.get("/api/events")
async def get_events():
    events = []
    for line in EVENTS_FILE.read_text().splitlines():
        try:
            # print(f"Processing line: {line}")
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # skip any malformed lines
            continue
    return {"events": events}
class LedPayload(BaseModel):
    state: bool
@app.post("/api/led")
async def toggle_led(payload: LedPayload):
    print(f"LED state changed: {payload.state}")
    # await manager.broadcast_json({
    #     "type": "led",
    #     "state": payload.state
    # })
    await manager.broadcast_led(payload.state)
    return {"success": True}

# — WebSocket endpoint for incoming ESP32 messages —
# @app.websocket("/ws/{topic}")
@app.websocket("/badges/uuid")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    print(f"WS connected")
    try:
        while True:
            data = await websocket.receive_text()
            timestamp = time.time()
            record = {
            "timestamp": timestamp,
            "device_id": data,
            "event_type": "connected",
            }
            updateConnection(data, timestamp)
            updateDatabase(record)
            # sendRelayUpdate(data, "connected")
            # asyncio.create_task(
            #     client.post(RELAY_URL, json=record)
            # )
            await websocket.send_text("ACK")
    except Exception as e:
        print(f"Error: {e}")
        print("WebSocket disconnected")
    finally:
        manager.disconnect(websocket)
        print("WebSocket connection closed")

if __name__ == "__main__":
    # single process runs both HTTP and WS on port 1883
    uvicorn.run(app, host="0.0.0.0", port=8000)
