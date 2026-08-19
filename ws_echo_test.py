"""
Barge-in, piece 1 (this addition): prove overlapping audio actually works
on a real Twilio call — a scripted interjection fires once, early in the
call, based on an INTERIM transcript (i.e. while their agent is still
mid-sentence), instead of waiting for speech_final/UtteranceEnd like every
other turn. This is deliberately opt-in (INTERRUPT_MODE) and fires at most
once per call — normal turn-taking for every other exchange is unaffected.
Built to test bug category 5 (failure to handle interruption) from
BUG_CATEGORIES.md, which the bot's normal architecture can't probe on its
own since it always waits for a full turn-end.

Step 2, piece 1 (done): real LLM reasoning replaces the scripted reply —
proved the LLM call works inside this pipeline with a single exchange
before piece 2 (below) builds the harder part.

Step 2, piece 2 (this addition): the conversation now continues across
multiple turns instead of ending after one reply. A real patient persona
+ scenario goal (scheduling for knee pain) drives it, with the model
signaling a natural end via a literal "[END_CALL]" marker in its final
reply. Two safety caps exist independently of that signal — max turn
count and max call duration — so a misbehaving LLM or agent loop can
never turn into a runaway call, same reasoning as the Twilio auto-recharge
discussion earlier in this log.

Step 1, pieces 2-4, built as one evolving server.

Piece 2, sub-pieces 1-3 (done): tunnel reachable, Twilio frames logged,
Deepgram live transcription confirmed on a real call.

Piece 3 (done): Deepgram's endpointing/UtteranceEnd signals replace the
fixed test-script timer as the real "their agent stopped talking" signal.

Piece 4 (done): on turn-end, synthesize a scripted line via ElevenLabs
(not real LLM reasoning yet — proving the loop closes end to end is the
point of this piece, per the plan's walking-skeleton step), stream it
back to Twilio over the same bidirectional connection, then hang up.
Closes the full loop: call -> transcribe -> detect turn -> speak back ->
end.

Piece 5 (this addition, last piece of Step 1): save a transcript (JSON,
both speakers) and download the call recording (mp3) to call_logs/ once
the call ends — two of the actual deliverables depend on this working.

Run with: python3 -u ws_echo_test.py   (unbuffered — see piece 2 log
entry for why this matters)
Then, in another terminal: ngrok http 8000
"""

import asyncio
import base64
import json
import os
import time
from datetime import datetime, timezone

import requests
import websockets
from fastapi import FastAPI, WebSocket
from twilio.rest import Client

app = FastAPI()

CALL_LOGS_DIR = "call_logs"
os.makedirs(CALL_LOGS_DIR, exist_ok=True)


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
ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # "Sarah" — confirmed present in this account's own voice list

OPENAI_API_KEY = ENV.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"  # switched from Anthropic mid-Step 2 — ran out of Anthropic credits

MAX_TURNS = 16  # 8 wasn't enough to reach a natural conclusion in the first real multi-turn test
MAX_CALL_SECONDS = 180

# Barge-in test (bug category 5). Opt-in per call, fires at most once.
INTERRUPT_MODE = True
INTERRUPT_TRIGGER_WORDS = 4  # only interrupt once they're clearly mid-sentence, not on their first word or two
INTERRUPT_TEXT = "Sorry, can I ask something real quick?"

PATIENT_SYSTEM_PROMPT = (
    "You are Maria Gonzalez, calling Pivot Point Orthopedics as a new patient. "
    "You've had knee pain for about two weeks after a hiking trip and want to "
    "schedule an appointment to get it checked out. You're available weekday "
    "afternoons. Your date of birth is March 14, 1990, and your phone number is "
    "555-201-4477. Speak naturally and briefly, like a real person on the phone — "
    "one or two sentences per turn, no lists, no markdown, no stage directions, "
    "don't repeat yourself. Answer the receptionist's questions directly and stay "
    "in character as the patient throughout. Once your appointment is confirmed, "
    "or the call reaches a natural conclusion (e.g. they take a message or say "
    "they'll call back), thank them, say goodbye, and end your final reply with "
    "the exact text [END_CALL] on its own line — do not use that marker at any "
    "other time."
)


def generate_llm_reply(conversation_history):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    messages = [{"role": "system", "content": PATIENT_SYSTEM_PROMPT}] + conversation_history
    payload = {
        "model": OPENAI_MODEL,
        "max_tokens": 150,
        "messages": messages,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def synthesize_speech_ulaw(text):
    """Returns raw 8kHz mulaw audio bytes — the exact format Twilio expects, no transcoding needed."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    params = {"output_format": "ulaw_8000"}
    payload = {"text": text, "model_id": "eleven_turbo_v2_5"}
    r = requests.post(url, headers=headers, params=params, json=payload, timeout=30)
    r.raise_for_status()
    return r.content


def save_transcript(call_sid, turns):
    path = os.path.join(CALL_LOGS_DIR, f"{call_sid}_transcript.json")
    record = {
        "call_sid": call_sid,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "turns": turns,
    }
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    print(f"[SAVED] transcript -> {path}")


def download_recording(call_sid, max_wait_seconds=30, poll_interval=3):
    """Recordings aren't available the instant a call ends, and the resource
    can exist before its media is actually ready (a first attempt hit a 404
    on the .mp3 even though recordings.list() already returned it) — poll on
    status=="completed" specifically, and retry the download itself too."""
    waited = 0
    while waited < max_wait_seconds:
        recordings = twilio_client.recordings.list(call_sid=call_sid)
        if recordings and recordings[0].status == "completed":
            recording = recordings[0]
            media_url = (
                f"https://api.twilio.com/2010-04-01/Accounts/{ENV['TWILIO_ACCOUNT_SID']}"
                f"/Recordings/{recording.sid}.mp3"
            )
            try:
                r = requests.get(
                    media_url,
                    auth=(ENV["TWILIO_ACCOUNT_SID"], ENV["TWILIO_AUTH_TOKEN"]),
                    timeout=30,
                )
                r.raise_for_status()
                path = os.path.join(CALL_LOGS_DIR, f"{call_sid}.mp3")
                with open(path, "wb") as f:
                    f.write(r.content)
                print(f"[SAVED] recording -> {path} ({len(r.content)} bytes)")
                return
            except requests.RequestException as e:
                print(f"[WARN] recording marked completed but download failed, retrying: {e}")
        elif recordings:
            print(f"[waiting] recording status={recordings[0].status}")
        time.sleep(poll_interval)
        waited += poll_interval
    print(f"[WARN] no completed recording found for {call_sid} after {max_wait_seconds}s")


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
    call_over = False
    call_start = time.time()
    transcript_turns = []
    conversation_history = []
    agent_buffer = []
    turn_count = 0
    has_interrupted = False

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
            transcript_turns.append({"speaker": "bot", "text": text})
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

        async def hang_up(reason):
            nonlocal call_over
            if call_over or not call_sid:
                return
            call_over = True
            print(f"[HANGUP] reason={reason} -> ending call {call_sid}")
            try:
                twilio_client.calls(call_sid).update(status="completed")
            except Exception as e:
                print(f"Failed to hang up call (may have already ended): {e}")

            save_transcript(call_sid, transcript_turns)
            await asyncio.to_thread(download_recording, call_sid)

        async def handle_turn_end(reason):
            nonlocal turn_count
            if call_over:
                return

            agent_text = " ".join(agent_buffer).strip()
            agent_buffer.clear()
            if not agent_text:
                # Both speech_final and UtteranceEnd can fire for the same pause;
                # whichever processes first empties the buffer, so the second
                # is a no-op rather than a duplicate LLM call for one turn.
                print(f"[TURN END] reason={reason} but no new agent speech, ignoring")
                return

            print(f"[TURN END DETECTED] reason={reason}: {agent_text!r}")
            conversation_history.append({"role": "user", "content": agent_text})
            turn_count += 1

            elapsed = time.time() - call_start
            if turn_count > MAX_TURNS:
                print(f"[SAFETY CAP] max turns ({MAX_TURNS}) reached, ending without another reply")
                await hang_up("max_turns_reached")
                return
            if elapsed > MAX_CALL_SECONDS:
                print(f"[SAFETY CAP] max call duration ({MAX_CALL_SECONDS}s) reached, ending without another reply")
                await hang_up("max_duration_reached")
                return

            print(f"[LLM] turn {turn_count}, generating reply...")
            reply_text = await asyncio.to_thread(generate_llm_reply, conversation_history)
            print(f"[LLM] reply: {reply_text!r}")
            conversation_history.append({"role": "assistant", "content": reply_text})

            should_end = "[END_CALL]" in reply_text
            spoken_text = reply_text.replace("[END_CALL]", "").strip()
            await send_tts_reply(spoken_text)

            if should_end:
                print("[LLM] signaled end of conversation")
                await hang_up("llm_end_signal")

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
                        # Covers the case where the far end hangs up first, before
                        # our own turn-end/safety-cap logic ever triggers a hang_up —
                        # without this, that call's transcript/recording never gets saved.
                        await hang_up("remote_stop")
                        break

            except Exception as e:
                print(f"Twilio side closed: {e} (frames forwarded: {frame_count})")

        async def deepgram_to_transcript():
            nonlocal has_interrupted
            try:
                async for message in dg_ws:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "UtteranceEnd":
                        await handle_turn_end("UtteranceEnd")
                        continue

                    alternatives = data.get("channel", {}).get("alternatives", [{}])
                    transcript = alternatives[0].get("transcript", "")
                    if transcript:
                        tag = "FINAL" if data.get("is_final") else "interim"
                        print(f"[{tag}] {transcript}")
                        if data.get("is_final"):
                            transcript_turns.append({"speaker": "agent", "text": transcript})
                            agent_buffer.append(transcript)
                        elif (
                            INTERRUPT_MODE
                            and not has_interrupted
                            and not call_over
                            and len(transcript.split()) >= INTERRUPT_TRIGGER_WORDS
                        ):
                            has_interrupted = True
                            elapsed = time.time() - call_start
                            print(
                                f"[INTERRUPT] barging in at {elapsed:.1f}s while agent mid-sentence: "
                                f"{transcript!r}"
                            )
                            conversation_history.append({"role": "assistant", "content": INTERRUPT_TEXT})
                            await send_tts_reply(INTERRUPT_TEXT)

                    if data.get("speech_final"):
                        await handle_turn_end("speech_final")

            except Exception as e:
                print(f"Deepgram side closed: {e}")

        await asyncio.gather(twilio_to_deepgram(), deepgram_to_transcript())

    print("Media stream handler done")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
