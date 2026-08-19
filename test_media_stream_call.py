"""
Places one real outbound call, connects it to the media-stream server with
a specific scenario (persona + settings from scenarios/<name>.json), and
polls until the call ends naturally (turn-based hangup, safety cap, or the
far end hanging up) — with an external safety cap in case none of those
fire for some reason, so a bug never turns into a runaway open call.

Run with: python3 test_media_stream_call.py <ngrok_host> [scenario_name]
Example:  python3 test_media_stream_call.py humorous-subheader-exorcism.ngrok-free.dev 01_baseline
If scenario_name is omitted, the server falls back to DEFAULT_SCENARIO.
"""

import sys
import time

from twilio.rest import Client

SAFETY_CAP_SECONDS = 210  # above the server's own MAX_CALL_SECONDS (180s) so it doesn't cut a real multi-turn conversation short


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


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_media_stream_call.py <ngrok_host_without_protocol> [scenario_name]")
        sys.exit(1)

    ngrok_host = sys.argv[1]
    scenario_name = sys.argv[2] if len(sys.argv) > 2 else None
    stream_url = f"wss://{ngrok_host}/media-stream"

    env = load_env()
    sid = env["TWILIO_ACCOUNT_SID"]
    token = env["TWILIO_AUTH_TOKEN"]
    from_number = env["TWILIO_PHONE_NUMBER"]
    to_number = env["TEST_TARGET_NUMBER"]

    client = Client(sid, token)

    # Scenario is passed via a nested <Parameter>, not a URL query string —
    # Twilio's <Stream> verb doesn't reliably forward query params to the
    # actual WebSocket connection (confirmed the hard way: a first attempt
    # using ?scenario= silently fell back to the server's default on a real
    # call). <Parameter> is the documented mechanism; it arrives in the
    # "start" event's customParameters instead.
    stream_tag = f'<Stream url="{stream_url}">'
    if scenario_name:
        stream_tag += f'<Parameter name="scenario" value="{scenario_name}" />'
    stream_tag += "</Stream>"

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f"{stream_tag}"
        "</Connect>"
        "</Response>"
    )

    call = client.calls.create(to=to_number, from_=from_number, twiml=twiml, record=True)
    print(f"Call placed. SID: {call.sid}  Scenario: {scenario_name or 'DEFAULT_SCENARIO'}")
    print(f"Waiting for the server to detect turn-end and hang up (safety cap: {SAFETY_CAP_SECONDS}s)...")

    start = time.time()
    while time.time() - start < SAFETY_CAP_SECONDS:
        time.sleep(2)
        call = client.calls(call.sid).fetch()
        if call.status in ("completed", "canceled", "failed", "busy", "no-answer"):
            elapsed = round(time.time() - start, 1)
            print(f"Call ended on its own after {elapsed}s, status: {call.status}")
            return

    print(f"Safety cap of {SAFETY_CAP_SECONDS}s hit — turn-detection may not have fired. Hanging up now.")
    client.calls(call.sid).update(status="completed")


if __name__ == "__main__":
    main()
