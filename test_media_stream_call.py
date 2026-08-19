"""
Step 1, piece 2, sub-piece 2: confirm Twilio actually connects to our
WebSocket and sends real media frames from a real call. No Deepgram yet
— just proving the wiring works, per ws_echo_test.py's /media-stream
logging.

Auto-hangs-up after ~10s so the test doesn't run indefinitely.

Run with: python3 test_media_stream_call.py <ngrok_public_url>
Example:  python3 test_media_stream_call.py humorous-subheader-exorcism.ngrok-free.dev
"""

import sys
import time

from twilio.rest import Client


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
    print("Streaming for ~10 seconds, check server log for frame activity...")

    time.sleep(10)

    call = client.calls(call.sid).fetch()
    if call.status not in ("completed", "canceled", "failed", "busy", "no-answer"):
        client.calls(call.sid).update(status="completed")
        print("Call ended by script after 10s test window.")
    else:
        print(f"Call already ended on its own, status: {call.status}")


if __name__ == "__main__":
    main()
