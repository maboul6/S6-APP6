import json
import threading
import asyncio
import tkinter as tk
from tkinter import ttk

import aiocoap.resource as resource
import aiocoap

def load_name_db(path='coap_database.txt'):
    db = {}
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                entry = json.loads(line)
                db.update(entry)
            except json.JSONDecodeError:
                print("Skipping bad JSON:", line)
    return db

name_db = load_name_db()

root = tk.Tk()
root.title("CoAP: Badge Observer")

tree = ttk.Treeview(root, columns=('status',), show='headings')
tree.heading('status', text='Connected')
tree.column('status', width=80, anchor='center')
tree.pack(fill='both', expand=True)

tree.configure(show='tree headings')
tree.heading('#0', text='Name')

for uuid, name in name_db.items():
    tree.insert('', 'end', iid=uuid, text=name, values=('✗',))

class StatusResource(resource.Resource):
    async def render_put(self, request):
        """
        Expects payload like: b'{"<uuid>":"true"}'
        """
        try:
            data = json.loads(request.payload.decode('utf‑8'))
        except Exception:
            return aiocoap.Message(code=aiocoap.BAD_REQUEST)

        for uuid, is_conn in data.items():
            symbol  = '✓' if is_conn else '✗'
            root.after(0, lambda u=uuid.upper(), s=symbol: tree.set(u, 'status', s))

        return aiocoap.Message(code=aiocoap.CHANGED, payload=b'')

async def coap_server_main():
    site = resource.Site()
    site.add_resource(['status'], StatusResource())
    await aiocoap.Context.create_server_context(site, bind=('192.168.1.113', 5683))
    await asyncio.get_running_loop().create_future()

def start_coap_server():
    asyncio.run(coap_server_main())

threading.Thread(target=start_coap_server, daemon=True).start()

root.mainloop()
