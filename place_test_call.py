"""
Step 1, piece 1: prove outbound telephony works at all, before adding
streaming audio/STT/TTS on top. Places a real call to TEST_TARGET_NUMBER
with a static spoken line, then hangs up. No websocket, no AI yet.

Run with: python3 place_test_call.py
"""

import os

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
    env = load_env()

    sid = env["TWILIO_ACCOUNT_SID"]
    token = env["TWILIO_AUTH_TOKEN"]
    from_number = env["TWILIO_PHONE_NUMBER"]
    to_number = env["TEST_TARGET_NUMBER"]

    client = Client(sid, token)

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        '<Say voice="Polly.Joanna">'
        "This is a walking skeleton test call. Telephony is working. Goodbye."
        "</Say>"
        "</Response>"
    )

    call = client.calls.create(
        to=to_number,
        from_=from_number,
        twiml=twiml,
        record=True,
    )

    print(f"Call placed. SID: {call.sid}")
    print(f"To: {to_number}  From: {from_number}")
    print("Check the Twilio console (Monitor > Logs > Calls) for call status and recording.")


if __name__ == "__main__":
    main()
