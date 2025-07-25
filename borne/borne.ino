#include <WiFi.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <BLEEddystoneURL.h>
#include <BLEEddystoneTLM.h>
#include <BLEBeacon.h>
#include <WebSocketsClient.h>

#define _WEBSOCKETS_LOGLEVEL_ 4

int scanTime = 5;  //In seconds
BLEScan *pBLEScan;

// === Configuration Wi‑Fi ===
const char* ssid     = "EBOX-0993";
const char* password = "4cd49aec2f";

unsigned long lastMsg = 0;
int compteur = 0;

WebSocketsClient webSocket;

static const int  LED_PIN        = 18;                // change to whichever GPIO you wired your LED


void handleLED(const String &payload) {
  if (payload == "1")
    digitalWrite(LED_PIN, HIGH);
  else if (payload == "0")
    digitalWrite(LED_PIN, LOW);
  else
    Serial.printf("Unrecognised command: %s\n", payload.c_str());
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_CONNECTED:
      Serial.println("[WS] Connected to server");
      break;
    case WStype_TEXT: {
      Serial.printf("[WS] message receivred: %s\n", payload);
      String msg = String((char*)payload, length);
      handleLED(msg);
      break;
    }
    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected");
      break;
  }
}

// === Connexion au Wi‑Fi ===
void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connexion à ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWi‑Fi connecté");
  Serial.print("Adresse IP : ");
  Serial.println(WiFi.localIP());
}

void setup_websocket() {
  webSocket.begin("192.168.1.161", 8000, "/badges/uuid");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);  // try reconnecting every 5s
}

class MyAdvertisedDeviceCallbacks : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice advertisedDevice) {
    if (advertisedDevice.haveServiceUUID()) {
      BLEUUID devUUID = advertisedDevice.getServiceUUID();
    }

    if (advertisedDevice.haveManufacturerData() == true) {
      String strManufacturerData = advertisedDevice.getManufacturerData();

      uint8_t cManufacturerData[100];
      memcpy(cManufacturerData, strManufacturerData.c_str(), strManufacturerData.length());

      if (strManufacturerData.length() == 25 && cManufacturerData[0] == 0x4C && cManufacturerData[1] == 0x00) {
        BLEBeacon oBeacon = BLEBeacon();
        oBeacon.setData(strManufacturerData);
        String message = oBeacon.getProximityUUID().toString().c_str();
        Serial.printf("UUID connected: %s\n", message.c_str());
        webSocket.sendTXT(message);
      }
    }
  }
};

void setup_ble(){
  Serial.println("Scanning BLE...");
  BLEDevice::init("");
  pBLEScan = BLEDevice::getScan();  //create new scan
  pBLEScan->setAdvertisedDeviceCallbacks(new MyAdvertisedDeviceCallbacks());
  pBLEScan->setActiveScan(true);  //active scan uses more power, but get results faster
  pBLEScan->setInterval(100);
  pBLEScan->setWindow(99);  // less or equal setInterval value
}

void ble_loop() {
  BLEScanResults *foundDevices = pBLEScan->start(scanTime, true);
  pBLEScan->clearResults();  // delete results fromBLEScan buffer to release memory
}

// === Setup initial ===
void setup() {
  Serial.begin(115200);
  setup_wifi();
  setup_websocket();
  setup_ble();
  pinMode(LED_PIN, OUTPUT);
}

// === Boucle principale ===
void loop() {
  webSocket.loop();
  unsigned long now = millis();
  if (now - lastMsg > 5000) {
    lastMsg = now;
    if (!webSocket.isConnected()) {
      Serial.println("[WS] reconnecting…");
    } else {
      ble_loop();
    }
  }
}
