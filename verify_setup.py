"""
Step 0 sanity check: confirms every API key in .env actually authenticates,
before any bot code gets written. Run with: python3 verify_setup.py
"""

import os
import sys

import requests


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


def mask(value):
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def check_twilio(env):
    sid = env.get("TWILIO_ACCOUNT_SID", "")
    token = env.get("TWILIO_AUTH_TOKEN", "")
    if not sid or not token:
        return False, "TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN missing"
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json"
    try:
        r = requests.get(url, auth=(sid, token), timeout=10)
    except requests.RequestException as e:
        return False, f"request failed: {e}"
    if r.status_code == 200:
        status = r.json().get("status", "unknown")
        return True, f"account status: {status}"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"


def check_elevenlabs(env):
    key = env.get("ELEVENLABS_API_KEY", "")
    if not key:
        return False, "ELEVENLABS_API_KEY missing"
    try:
        r = requests.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": key},
            timeout=10,
        )
    except requests.RequestException as e:
        return False, f"request failed: {e}"
    if r.status_code == 200:
        return True, "authenticated"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"


def check_deepgram(env):
    key = env.get("DEEPGRAM_API_KEY", "")
    if not key:
        return False, "DEEPGRAM_API_KEY missing"
    try:
        r = requests.get(
            "https://api.deepgram.com/v1/projects",
            headers={"Authorization": f"Token {key}"},
            timeout=10,
        )
    except requests.RequestException as e:
        return False, f"request failed: {e}"
    if r.status_code == 200:
        n = len(r.json().get("projects", []))
        return True, f"authenticated, {n} project(s)"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"


def check_anthropic(env):
    key = env.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None, "ANTHROPIC_API_KEY not set, skipped"
    try:
        r = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            timeout=10,
        )
    except requests.RequestException as e:
        return False, f"request failed: {e}"
    if r.status_code == 200:
        return True, "authenticated"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"


def check_openai(env):
    key = env.get("OPENAI_API_KEY", "")
    if not key:
        return None, "OPENAI_API_KEY not set, skipped"
    try:
        r = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
    except requests.RequestException as e:
        return False, f"request failed: {e}"
    if r.status_code == 200:
        return True, "authenticated"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"


def main():
    if not os.path.exists(".env"):
        print("No .env file found in current directory. Run this from the project root.")
        sys.exit(1)

    env = load_env()

    checks = [
        ("Twilio", check_twilio),
        ("ElevenLabs", check_elevenlabs),
        ("Deepgram", check_deepgram),
        ("Anthropic", check_anthropic),
        ("OpenAI", check_openai),
    ]

    print(f"{'Service':<12} {'Result':<8} Detail")
    print("-" * 60)

    all_ok = True
    for name, fn in checks:
        ok, detail = fn(env)
        if ok is None:
            label = "SKIP"
        elif ok:
            label = "PASS"
        else:
            label = "FAIL"
            all_ok = False
        print(f"{name:<12} {label:<8} {detail}")

    print("-" * 60)
    if all_ok:
        print("All configured keys are working.")
    else:
        print("One or more keys failed — fix before starting Step 1.")
        sys.exit(1)


if __name__ == "__main__":
    main()
