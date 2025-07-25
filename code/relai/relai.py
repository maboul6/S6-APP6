from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json, pathlib, time, asyncio, uvicorn

from pydantic import BaseModel

# asyncio-mqtt and aiocoap imports
from asyncio_mqtt import Client as MQTTClient, MqttError
from aiocoap import Context as CoAPContext, Message as CoAPMessage, Code as CoAPCode

EVENTS_FILE = pathlib.Path("../events.txt")
RELAY_TOPIC = "badges/uuid"
MQTT_BROKER = "192.168.1.xxx" # 200
MQTT_PORT = 1883
COAP_ENDPOINT = "coap://192.168.1.xxx/relay/events" # 201
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Event(BaseModel):
    timestamp: float
    device_id: str
    event_type: str
mqtt_client: MQTTClient
coap_context: CoAPContext

@app.on_event("startup")
async def setup_clients():
    global mqtt_client, coap_context
    mqtt_client = MQTTClient(MQTT_BROKER, MQTT_PORT)
    # mqtt initialization
    await mqtt_client.connect()
    # coap initialization
    coap_context = await CoAPContext.create_client_context()

@app.on_event("shutdown")
async def teardown_clients():
    await mqtt_client.disconnect()
    await coap_context.shutdown()

@app.post("/relay/events")
async def relay_events(event: dict):
    print(f"Received event: {event}")
    payload_bytes = json.dumps(event.dict()).encode("utf‑8")
    asyncio.create_task(_publish_mqtt(payload_bytes))
    asyncio.create_task(_publish_coap(payload_bytes))

    return {"status": "ok"}

async def _publish_mqtt(payload: bytes):
    try:
        # QoS=1 ensures at‑least‑once delivery
        await mqtt_client.publish(RELAY_TOPIC, payload, qos=1)
    except MqttError as e:
        print(f"[MQTT ERROR] {e!r}")

async def _publish_coap(payload: bytes):
    try:
        req = CoAPMessage(code=CoAPCode.POST, uri=COAP_ENDPOINT, payload=payload)
        # wait up to 5s for a response
        resp = await asyncio.wait_for(coap_context.request(req).response, timeout=5.0)
        print(f"[CoAP RESP] {resp.code} {resp.payload!r}")
    except Exception as e:
        print(f"[CoAP ERROR] {e!r}")

if __name__ == "__main__":
    # single process runs both HTTP and WS on port 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)