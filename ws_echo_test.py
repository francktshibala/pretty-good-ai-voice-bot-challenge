"""
Step 1, piece 2 (streaming audio -> transcription) and piece 3
(turn-detection), built as one evolving server.

Piece 2, sub-pieces 1-3 (done): tunnel reachable, Twilio frames logged,
Deepgram live transcription confirmed on a real call.

Piece 3 (this addition): Deepgram's endpointing/UtteranceEnd signals
replace the fixed test-script timer as the real "their agent stopped
talking" signal. On detection, the server itself hangs up the call via
the Twilio REST API — closer to how the real bot will eventually behave
(the pipeline reacts to a turn boundary, not an external script).

Run with: python3 -u ws_echo_test.py   (unbuffered — see piece 2 log
entry for why this matters)
Then, in another terminal: ngrok http 8000
"""

import asyncio
import base64
import json

import websockets
from fastapi import FastAPI, WebSocket
from twilio.rest import Client

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
    "&endpointing=300&utterance_end_ms=1000"
)

twilio_client = Client(ENV["TWILIO_ACCOUNT_SID"], ENV["TWILIO_AUTH_TOKEN"])


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
    call_sid = None
    turn_ended = False

    async with websockets.connect(
        DEEPGRAM_URL,
        additional_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"},
    ) as dg_ws:
        print("Connected to Deepgram streaming API")

        async def end_call(reason):
            nonlocal turn_ended
            if turn_ended or not call_sid:
                return
            turn_ended = True
            print(f"[TURN END DETECTED] reason={reason} -> hanging up call {call_sid}")
            try:
                twilio_client.calls(call_sid).update(status="completed")
            except Exception as e:
                print(f"Failed to hang up call (may have already ended): {e}")

        async def twilio_to_deepgram():
            nonlocal frame_count, call_sid
            try:
                while True:
                    raw = await websocket.receive_text()
                    msg = json.loads(raw)
                    event = msg.get("event")

                    if event == "connected":
                        print(f"[connected] protocol={msg.get('protocol')}")

                    elif event == "start":
                        start = msg.get("start", {})
                        call_sid = start.get("callSid")
                        print(
                            f"[start] callSid={call_sid} "
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
                    msg_type = data.get("type")

                    if msg_type == "UtteranceEnd":
                        await end_call("UtteranceEnd")
                        continue

                    alternatives = data.get("channel", {}).get("alternatives", [{}])
                    transcript = alternatives[0].get("transcript", "")
                    if transcript:
                        tag = "FINAL" if data.get("is_final") else "interim"
                        print(f"[{tag}] {transcript}")

                    if data.get("speech_final"):
                        await end_call("speech_final")

            except Exception as e:
                print(f"Deepgram side closed: {e}")

        await asyncio.gather(twilio_to_deepgram(), deepgram_to_transcript())

    print("Media stream handler done")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
