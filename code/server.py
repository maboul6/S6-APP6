# THIS IS THE CONTROL SERVER THAT INTERACTS WITH THE DATABASE (TEXT FILE)
import json, time, pathlib
from typing import List
from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
EVENTS_FILE = pathlib.Path("events.txt")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # or your UI origin
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# — HTTP endpoint to render the file contents —
@app.get("/api/events")
async def get_events():
    events = []
    for line in EVENTS_FILE.read_text().splitlines():
        try:
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
            record = {
            "timestamp": time.time(),
            "device_id": data
            # you can add more fields here if you want…
            }
            data = f"{record['timestamp']} {record['device_id']}"
            with EVENTS_FILE.open("a") as f:
                f.write(json.dumps(record) + "\n")
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
