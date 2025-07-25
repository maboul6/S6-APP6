#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import threading
import tkinter as tk
from tkinter import ttk

BROKER_HOST = "192.168.1.113"
BROKER_PORT = 1883
TOPIC       = "badges/uuid"

def load_name_db(path='mqtt_database.txt'):
    db = {}
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                print("Skipping invalid JSON line:", line)
                continue
            db.update(entry)
    return db

name_db = load_name_db()

root = tk.Tk()
root.title("MQTT: Badge Observer")

tree = ttk.Treeview(root, columns=('status',), show='headings')
tree.heading('status', text='Connected')
tree.column('status', width=80, anchor='center')
tree.pack(fill='both', expand=True)

for uuid, name in name_db.items():
    tree.insert('', 'end', iid=uuid, text=name, values=('✗',))

tree.configure(show='tree headings')
tree.heading('#0', text='Name')

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Subscribing to topic:", TOPIC)
        client.subscribe(TOPIC)
    else:
        print(f"Connection failed (code {rc})")

def on_message(client, userdata, msg):
  payload = msg.payload.decode('utf-8')
  try:
      data = json.loads(payload)
  except json.JSONDecodeError:
      return

  for uuid, is_conn in data.items():
      symbol  = '✓' if is_conn else '✗'
      root.after(0, lambda u=uuid.upper(), s=symbol: tree.set(u, 'status', s))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

def mqtt_loop():
    client.loop_forever()

threading.Thread(target=mqtt_loop, daemon=True).start()

root.mainloop()
