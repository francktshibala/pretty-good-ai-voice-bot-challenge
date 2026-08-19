# Pretty Good AI — Voice Bot Challenge

A Python voice bot that calls Pretty Good AI's test line, plays a realistic patient
persona, and finds real bugs in their AI receptionist. Built as a risk-first walking
skeleton: telephony → live transcription → turn-detection → LLM reasoning → speech,
with a scripted patient persona per call.

See `ARCHITECTURE.md` for what was built and why, `BUG_REPORT.md` for findings,
`BUILD_LOG.md` for the full build history (decisions, bugs hit and fixed, in the
order they happened), and `calls/` for all 12 real call recordings + transcripts.

## Setup

1. **Clone and install dependencies:**
   ```
   pip3 install -r requirements.txt
   ```
   Also requires [ngrok](https://ngrok.com) (`brew install ngrok` on macOS) for
   exposing the local server to Twilio during development.

2. **Accounts needed** (all have free tiers sufficient for this project):
   - [Twilio](https://twilio.com) — paid account required (trial accounts cannot
     call arbitrary numbers); buy a phone number with Voice capability.
   - [ElevenLabs](https://elevenlabs.io) — for text-to-speech.
   - [Deepgram](https://deepgram.com) — for streaming speech-to-text.
   - [OpenAI](https://platform.openai.com) — for the patient-persona LLM.
   - [ngrok](https://ngrok.com) — free account, needed for a tunnel authtoken.

3. **Configure environment:**
   ```
   cp .env.example .env
   ```
   Fill in `.env` with your real credentials (Twilio SID/token/phone number,
   ElevenLabs key, Deepgram key, OpenAI key, and the fixed test target number).

4. **Add your ngrok authtoken** (one-time):
   ```
   ngrok config add-authtoken YOUR_TOKEN
   ```

5. **Verify everything works** before placing any real calls:
   ```
   python3 verify_setup.py
   ```
   This pings every service with a minimal request and reports pass/fail —
   no bot code runs yet.

## Running

Start the server and tunnel together:
```
./start_server.sh
```
This prints the public ngrok host to use for placing calls, and keeps both
processes running until you press Ctrl+C.

In another terminal, place a call with a specific patient scenario:
```
python3 test_media_stream_call.py <ngrok_host> <scenario_name>
```
Example:
```
python3 test_media_stream_call.py abc123.ngrok-free.dev 01_baseline
```

Scenario files live in `scenarios/` — each is a JSON file with a persona prompt
and settings (e.g. whether that call deliberately tests interruption handling).
Omitting the scenario name falls back to a default persona, useful for quick
manual testing.

The bot places a real outbound call to the fixed test number, has a full
multi-turn conversation as the patient persona, and automatically saves the
call recording (mp3) and a matching transcript (JSON) once the call ends.

## Project structure

- `ws_echo_test.py` — the media-stream server: handles the live Twilio call,
  Deepgram transcription, turn-detection, LLM reasoning, and ElevenLabs replies.
- `test_media_stream_call.py` — places an outbound call with a chosen scenario.
- `scenarios/` — one JSON file per patient persona/scenario.
- `calls/` — the 12 real deliverable call recordings + transcripts.
- `verify_setup.py` — one-time sanity check that every API key works.
- `place_test_call.py` — minimal script that proved basic telephony works
  (Step 1's first checkpoint; kept for reference, not used day-to-day).
- `PLAN.md`, `BUILD_LOG.md`, `BUG_CATEGORIES.md`, `CALL_PLAN.md` — planning and
  process documents, in the order they were written.

## Cost

Typical usage for this project (12 real calls, ~2 minutes average) costs under
$2 in per-minute API/telephony usage. The larger cost is Twilio's mandatory
account top-up (trial accounts can't call arbitrary numbers) — see
`BUILD_LOG.md`'s Step 0 entries for details.
