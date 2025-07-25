import sys, os, asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json, pathlib, time, uvicorn

from pydantic import BaseModel

# asyncio-mqtt and aiocoap imports
from aiomqtt import Client as MQTTClient, MqttError
from aiocoap import Context as CoAPContext, Message as CoAPMessage, Code as CoAPCode

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
    set_event_loop_policy(WindowsSelectorEventLoopPolicy())
EVENTS_FILE = pathlib.Path("../events.txt")
RELAY_TOPIC = "badges/uuid"
MQTT_BROKER = "192.168.1.113" # 200
MQTT_PORT = 1883
COAP_ENDPOINT = "coap://192.168.1.113/relay/events" # 201
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Event(BaseModel):
    device_id: str
    event_type: str
mqtt_manager: MQTTClient
mqtt_client: MQTTClient
coap_context: CoAPContext

@app.on_event("startup")
async def setup_clients():
    global mqtt_manager, mqtt_client, coap_context
    mqtt_manager = MQTTClient(hostname=MQTT_BROKER, port=MQTT_PORT)
    # mqtt initialization
    mqtt_client = await mqtt_manager.__aenter__()
    # coap initialization
    coap_context = await CoAPContext.create_client_context()

@app.on_event("shutdown")
async def teardown_clients():
    await mqtt_manager.__aexit__(None, None, None)
    await coap_context.shutdown()

@app.post("/relay/events")
async def relay_events(event: Event):
    print(f"Received event: {event}")
    is_connected = event.event_type == "connected"
    payload = { event.device_id: is_connected  } 
    payload_bytes = json.dumps(payload).encode("utf‑8")
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