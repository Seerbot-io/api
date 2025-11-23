# 1. Can WebSocket send data every 5 minutes?
**Yes.**
A WebSocket connection can stay open for hours or days with almost no resource cost.
Example: sending something every 5 minutes:
```python
@app.websocket("/ws/update")
async def ws_update(ws: WebSocket):
    await ws.accept()
    while True:
        await ws.send_json({"msg": "hello"})
        await asyncio.sleep(300)  # 5 minutes
```
This is completely normal.
---
# 2. Performance: WebSocket vs REST every 5 minutes
| Method                      | Resource usage                      | Notes                                    |
| --------------------------- | ----------------------------------- | ---------------------------------------- |
| REST request every 5 mins   | High (new TCP connection each time) | Wastes CPU + connection overhead         |
| WebSocket push every 5 mins | Very low                            | 1 connection stays open, no reconnection |
So **WebSocket is better** even if updates are slow.
---
# 3. Optimization techniques for your performance
### **A. Keep concurrency small**
On a 2-core server:
* Run **2 Uvicorn workers** only
  (Too many workers = too many open connections spread across workers)
Start Gunicorn like:
```
gunicorn main:app -k uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:8000
```
---
### **B. Avoid heavy code in WebSocket loop**
Do NOT do heavy CPU tasks inside:
❌ Bad:
```python
while True:
    big_calculation()
    await ws.send_json(...)
```
Put heavy work into:
* Background tasks
* Celery
* Redis Pub/Sub
* Async queues
---
### **C. Use a shared store for many clients**
If many clients need the same data:
1. Compute data **once**
2. Store in Redis/Memorystore
3. All WebSockets read from that store
Example pattern:
```python
# background task
redis.set("latest_price", new_price)
# websocket
while True:
    price = redis.get("latest_price")
    await ws.send_json({"price": price})
    await asyncio.sleep(300)
```
This prevents CPU work running inside each connection.
---
### **D. Use `asyncio.sleep()` not `time.sleep()`**
Always:
```python
await asyncio.sleep(300)
```
Never:
```
time.sleep(300)
```
Using `time.sleep()` will **block entire worker** for 5 minutes.
---
### **E. Enable NGINX WebSocket optimizations**
Add this:
```
proxy_read_timeout 3600;
proxy_send_timeout 3600;
proxy_connect_timeout 60;
```
This keeps long WS alive.
---
### **F. Set ping/pong (optional but good)**
Some servers/clients close idle connections.
Example:
```python
while True:
    await ws.send_json({"ping": "heartbeat"})
    await asyncio.sleep(60)
```
This keeps the connection alive.
---
