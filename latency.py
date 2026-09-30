import asyncio
import json
import time
import statistics
import sys
import websockets


async def main():
    if len(sys.argv) < 3:
        print("Usage: python latency.py <SESSION_ID> <WORKER_TOKEN>")
        print("Example: python latency.py session_123 worker_token_abc")
        return

    session_id = sys.argv[1]
    worker_token = sys.argv[2]
    from urllib.parse import quote
    encoded_token = quote(worker_token)
    url = f"ws://localhost:8000/ws/worker?session={session_id}&token={encoded_token}"

    samples = []
    print(f"Connecting to worker WebSocket at {url}...")
    
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({"type": "hello", "name": "Test", "lang": "en"}))
            while len(samples) < 30:
                msg = json.loads(await ws.recv())
                if "sent_at" in msg:
                    latency_ms = (time.time() - msg["sent_at"]) * 1000.0
                    samples.append(latency_ms)
                    print(f"[{len(samples)}/30] Latency: {latency_ms:.2f} ms")
                    
        median_ms = statistics.median(samples)
        max_ms = max(samples)
        print("\n" + "="*40)
        print(f"SUMMARY: median {median_ms:.1f} ms, max {max_ms:.1f} ms, n={len(samples)}")
        print("="*40)
    except Exception as e:
        print(f"Error measuring latency: {e}")

if __name__ == "__main__":
    asyncio.run(main())
