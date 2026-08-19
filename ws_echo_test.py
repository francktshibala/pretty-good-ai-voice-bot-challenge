"""
Step 1, pieces 2-4, built as one evolving server.

Piece 2, sub-pieces 1-3 (done): tunnel reachable, Twilio frames logged,
Deepgram live transcription confirmed on a real call.

Piece 3 (done): Deepgram's endpointing/UtteranceEnd signals replace the
fixed test-script timer as the real "their agent stopped talking" signal.

Piece 4 (this addition): on turn-end, synthesize a scripted line via
ElevenLabs (not real LLM reasoning yet — proving the loop closes end to
end is the point of this piece, per the plan's walking-skeleton step),
stream it back to Twilio over the same bidirectional connection, then
hang up. Closes the full loop: call -> transcribe -> detect turn ->
speak back -> end.

Run with: python3 -u ws_echo_test.py   (unbuffered — see piece 2 log
entry for why this matters)
Then, in another terminal: ngrok http 8000
"""

import asyncio
import base64
import json

import requests
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

ELEVENLABS_API_KEY = ENV.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # "Sarah" — confirmed present in this account's own voice list; placeholder for this checkpoint, a persona voice gets picked deliberately in Step 2
SCRIPTED_REPLY_TEXT = "Hi, I'd like to schedule an appointment please."


def synthesize_speech_ulaw(text):
    """Returns raw 8kHz mulaw audio bytes — the exact format Twilio expects, no transcoding needed."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    params = {"output_format": "ulaw_8000"}
    payload = {"text": text, "model_id": "eleven_turbo_v2_5"}
    r = requests.post(url, headers=headers, params=params, json=payload, timeout=30)
    r.raise_for_status()
    return r.content


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
    stream_sid = None
    turn_ended = False

    async with websockets.connect(
        DEEPGRAM_URL,
        additional_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"},
    ) as dg_ws:
        print("Connected to Deepgram streaming API")

        async def send_tts_reply(text):
            if not stream_sid:
                print("[TTS] no streamSid yet, skipping reply")
                return
            print(f"[TTS] synthesizing: {text!r}")
            audio_bytes = synthesize_speech_ulaw(text)
            print(f"[TTS] got {len(audio_bytes)} bytes of mulaw audio, sending to Twilio")

            chunk_size = 160  # 20ms of 8kHz 8-bit mulaw, matches Twilio's own frame size
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i : i + chunk_size]
                media_msg = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": base64.b64encode(chunk).decode("utf-8")},
                }
                await websocket.send_text(json.dumps(media_msg))

            playback_seconds = len(audio_bytes) / 8000  # 8000 bytes/sec at 8kHz 8-bit mulaw
            print(f"[TTS] all frames sent, waiting ~{playback_seconds:.1f}s for playback")
            await asyncio.sleep(playback_seconds + 0.5)

        async def end_call(reason):
            nonlocal turn_ended
            if turn_ended or not call_sid:
                return
            turn_ended = True
            print(f"[TURN END DETECTED] reason={reason}")
            await send_tts_reply(SCRIPTED_REPLY_TEXT)
            print(f"-> hanging up call {call_sid}")
            try:
                twilio_client.calls(call_sid).update(status="completed")
            except Exception as e:
                print(f"Failed to hang up call (may have already ended): {e}")

        async def twilio_to_deepgram():
            nonlocal frame_count, call_sid, stream_sid
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
                        stream_sid = start.get("streamSid")
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
