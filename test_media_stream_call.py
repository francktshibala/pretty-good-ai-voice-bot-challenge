"""
Step 1, piece 3: confirm real turn-detection — the server (ws_echo_test.py)
now hangs up the call itself once Deepgram signals the far end stopped
talking, instead of this script cutting it off on a fixed timer.

This script just places the call and polls status until it ends, with a
safety cap in case detection fails for some reason (so a bug never turns
into a runaway open call).

Run with: python3 test_media_stream_call.py <ngrok_public_url>
Example:  python3 test_media_stream_call.py humorous-subheader-exorcism.ngrok-free.dev
"""

import sys
import time

from twilio.rest import Client

SAFETY_CAP_SECONDS = 30


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
        print("Usage: python3 test_media_stream_call.py <ngrok_host_without_protocol>")
        sys.exit(1)

    ngrok_host = sys.argv[1]
    stream_url = f"wss://{ngrok_host}/media-stream"

    env = load_env()
    sid = env["TWILIO_ACCOUNT_SID"]
    token = env["TWILIO_AUTH_TOKEN"]
    from_number = env["TWILIO_PHONE_NUMBER"]
    to_number = env["TEST_TARGET_NUMBER"]

    client = Client(sid, token)

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<Stream url="{stream_url}" />'
        "</Connect>"
        "</Response>"
    )

    call = client.calls.create(to=to_number, from_=from_number, twiml=twiml)
    print(f"Call placed. SID: {call.sid}")
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
