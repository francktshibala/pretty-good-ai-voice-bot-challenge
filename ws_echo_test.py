"""
Step 1, piece 2: WebSocket server used across three sub-pieces.

Sub-piece 1 (done): /ws — plain echo test, confirms the ngrok tunnel
reaches this server from the public internet at all.

Sub-piece 2 (done): /media-stream logs Twilio's event envelope and
frame/byte counts only — no Deepgram yet. Isolated "is Twilio's audio
actually arriving, and what does it look like" as its own checkpoint.

Sub-piece 3 (this addition): /media-stream now forwards decoded audio
to Deepgram's streaming API and prints live transcripts. Last checkpoint
before piece 3 (turn-detection) and piece 4 (TTS reply) build on top.

Run with: python3 -u ws_echo_test.py   (unbuffered — see sub-piece 2 log
entry for why this matters)
Then, in another terminal: ngrok http 8000
"""

import asyncio
import base64
import json

import websockets
from fastapi import FastAPI, WebSocket

app = FastAPI()


def load_env(path=".env"):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


ENV = load_env()
DEEPGRAM_API_KEY = ENV.get("DEEPGRAM_API_KEY", "")
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?encoding=mulaw&sample_rate=8000&channels=1&punctuate=true&interim_results=true"
)


@app.get("/")
def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def echo(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected")
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received: {data}")
            await websocket.send_text(f"echo: {data}")
    except Exception as e:
        print(f"Connection closed: {e}")


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    print("Twilio media stream connected")

    frame_count = 0

    async with websockets.connect(
        DEEPGRAM_URL,
        additional_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"},
    ) as dg_ws:
        print("Connected to Deepgram streaming API")

        async def twilio_to_deepgram():
            nonlocal frame_count
            try:
                while True:
                    raw = await websocket.receive_text()
                    msg = json.loads(raw)
                    event = msg.get("event")

                    if event == "connected":
                        print(f"[connected] protocol={msg.get('protocol')}")

                    elif event == "start":
                        start = msg.get("start", {})
                        print(
                            f"[start] callSid={start.get('callSid')} "
                            f"mediaFormat={start.get('mediaFormat')}"
                        )

                    elif event == "media":
                        payload = msg.get("media", {}).get("payload", "")
                        audio_bytes = base64.b64decode(payload)
                        await dg_ws.send(audio_bytes)
                        frame_count += 1

                    elif event == "stop":
                        print(f"[stop] total frames forwarded to Deepgram: {frame_count}")
                        await dg_ws.send(json.dumps({"type": "CloseStream"}))
                        break

            except Exception as e:
                print(f"Twilio side closed: {e} (frames forwarded: {frame_count})")

        async def deepgram_to_transcript():
            try:
                async for message in dg_ws:
                    data = json.loads(message)
                    alternatives = data.get("channel", {}).get("alternatives", [{}])
                    transcript = alternatives[0].get("transcript", "")
                    if transcript:
                        tag = "FINAL" if data.get("is_final") else "interim"
                        print(f"[{tag}] {transcript}")
            except Exception as e:
                print(f"Deepgram side closed: {e}")

        await asyncio.gather(twilio_to_deepgram(), deepgram_to_transcript())

    print("Media stream handler done")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
