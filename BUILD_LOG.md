# Build Log

Running record of what was built, real decisions/tradeoffs made and why, and anything that didn't go as expected. Short, factual entries — not essays. See `PLAN.md` for the full plan this log tracks against.

## Why this workflow (reference for explaining decisions later)

- **Risk-first ordering.** The unfamiliar, hard-to-debug pieces — telephony, streaming STT, turn-taking — get proven before any real "patient" intelligence is added. A bug in unfamiliar plumbing is far harder to isolate once smart logic is layered on top of it.
- **Walking skeleton before intelligence.** Step 1 builds the entire pipeline thin and dumb (a scripted reply, not real reasoning) to prove the loop closes end-to-end, before Step 2 swaps in the LLM. Don't optimize or add intelligence to a path that isn't proven yet.
- **Verify before advancing.** Each step gets a real test — an actual phone call, an actual API ping — before the next step starts, instead of stacking untested layers and debugging the whole stack at once.
- **Real calls are the test suite for conversational quality.** "Did that sound natural" isn't a unit test. Lightweight tests are reserved for deterministic infra (file-saving, transcript formatting) — trust what you hear over what you assume for everything else.
- **Decide with evidence, not assumption.** Open architecture questions (STT provider, build vs. managed platform, Twilio feasibility) were resolved with actual research before writing code against them, not guessed and fixed later.
- **Log reasoning as it happens, not after.** Each entry below captures a decision and its why in the moment. This is what makes "iteration" demonstrable instead of a claim made after the fact from memory.
- **Commit at each verified checkpoint, not in large batches.** Same reasoning as "verify before advancing" applied to git history — a small commit after each proven piece means nothing gets lost, and a break in the next piece is attributable to that piece specifically rather than debugged across a pile of unreviewed changes.

---

## 2026-08-18 — Planning phase complete, PLAN.md saved

**What happened:** Brought a complete pre-formed plan (component breakdown, risk-first build order, deliverables checklist, eval criteria) for this challenge, worked out ahead of time outside this session. It already treated turn-taking/VAD as a first-tier risk (not a later refinement), included call recording in the Step 1 walking skeleton, and put account/infra setup before any code. Saved verbatim as `PLAN.md`.

**Decision:** Before writing code, validate the plan's three open architecture questions (Section 7) with actual research rather than assuming. Deployed 3 parallel research agents:
1. Twilio trial account restrictions for calling the fixed test number
2. STT/VAD provider comparison
3. Custom-built stack vs. managed voice-AI platform (build-vs-buy)

**Findings, folded into PLAN.md:**
- **Twilio — real blocker found.** Trial accounts cannot call +1-805-439-8008 at all (it's a third party's number; Twilio's verify-by-code flow requires code entry by the number's owner, which isn't possible here — fails with error 32100). Even on a verified number, trial accounts inject an audible "upgrade your account" message before any audio plays, which would break the clean-recording requirement regardless. Twilio's suggested minimum top-up to go paid is $20 — the entire reimbursement budget on telephony alone, though actual per-call usage cost is trivial (<$1 for the full test suite). **Open question, not yet resolved:** whether a smaller top-up is actually accepted in practice — needs checking directly in the Twilio console.
- **STT/VAD — resolved.** Deepgram Nova-3 streaming, no separate VAD library. Its built-in `endpointing`/`utterance_end_ms` params handle turn-detection directly in the stream. AssemblyAI is cheaper for raw transcription but gates comparable turn-detection behind a pricier tier.
- **Architecture — resolved.** Hybrid approach: Pipecat (or LiveKit Agents) handling real-time plumbing (audio streaming, turn-taking, interruption) over Twilio, with Deepgram (STT), an LLM, and ElevenLabs (TTS) still explicitly chosen and wired by hand. Reasoning: fully custom risks burning the time budget on unfamiliar telephony/VAD plumbing; fully managed platforms (Vapi/Retell/Bland) hide the wiring the eval explicitly wants reasoned about, and are built for generic assistants, not an adversarial bug-hunting persona.

**Not yet done:** No code written. No accounts upgraded/verified yet. Step 0 (account + API key verification) starts next.

---

## 2026-08-19 — Twilio upgraded to paid (Step 0, part 1 of 4)

**What happened:** Upgraded Twilio from trial to Pay As You Go. Console did not offer a smaller starting balance than $20 — confirms the earlier research finding; the full suggested top-up was required, no lower option surfaced. Got a bonus of 75 free voice minutes (no 30-day expiration), which likely covers the entire test-call suite without touching the paid balance.

**Decision:** Selected role "Individual," use-case "Customer Support" (closest fit of the offered onboarding categories, doesn't affect functionality/billing), and "With code" for the build method — matches the plan's Twilio-API-via-Python approach.

**Flagged, not yet resolved:** Auto-recharge is ON (refills to $20 whenever balance drops below $10), with no hard ceiling. Given this project deliberately stress-tests a voice agent for malfunctions (loops, hangs) and the bot code itself is new/unproven, a runaway call loop on either side could trigger repeated auto-recharges beyond the $20 reimbursement cap. Recommended turning it off or lowering the threshold until Step 1 (walking skeleton) is proven stable — user decision pending.

**Not yet done:** ElevenLabs, Deepgram, and LLM API keys not yet confirmed. pgai.us/athena test account not yet created. No code written.

---

## 2026-08-19 — Step 0 complete: all accounts and keys verified

**What happened:** Bought a Twilio phone number (+12602702673, local, $1.15/mo — chosen over toll-free since only outbound Voice capability is needed). Reused existing ElevenLabs, Anthropic, and OpenAI keys from a prior project (BookBridge) rather than generating new ones — a deliberate speed tradeoff, acceptable since those keys won't be used on the other project anymore, so there's no cross-project usage/billing conflict. Generated a fresh Deepgram key. All values placed in a local `.env` (gitignored), scaffolded from `.env.example` (template, no real values, safe to commit).

Created the pgai.us/athena test account for product context, as the plan's setup note required. It redirects to a branded intake form ("Pivot Point Orthopedics, powered by Pretty Good AI") collecting name/email/phone/DOB, then shows a confirmation screen with a demo phone number and a "call me instead" option. **Did not call that number or use "call me instead"** — per the plan's explicit warning, the only number this project ever calls is the fixed test number +1-805-439-8008. Useful context gained: the demo covers appointment scheduling/changes, insurance updates, and prescription refills — informs the scenario design for Step 4's real calls.

**Verification:** Wrote `verify_setup.py`, a small script (not bot code — pure infra check) that pings each service's API with a minimal authenticated request (Twilio account lookup, ElevenLabs user endpoint, Deepgram projects list, Anthropic/OpenAI models list) and reports pass/fail without printing key values. Ran it — all 5 services (Twilio, ElevenLabs, Deepgram, Anthropic, OpenAI) passed.

**Still open:** Twilio auto-recharge flag from the previous entry — not yet turned off. Decide before Step 1 if a runaway call loop during testing is a real concern.

**Step 0 is now complete.** No bot code written yet. Next: Step 1, the thin walking skeleton (Twilio call → Deepgram streaming transcription → VAD/endpointing → scripted ElevenLabs reply → recording + transcript saved), via Pipecat/LiveKit Agents per the Section 7 architecture decision.

---

## 2026-08-19 — Step 1, piece 1: first real outbound call confirmed

**What happened:** Wrote `place_test_call.py` — the smallest possible proof that telephony works: places a real outbound call to the fixed test number with a static spoken line (no streaming audio, no STT/TTS yet) and hangs up. Broke Step 1 into small pieces deliberately (telephony first, alone) rather than building the whole pipeline — the highest-risk, least-familiar unknown gets proven in isolation before adding streaming audio complexity on top, per the workflow principles above.

Ran it — call SID `CAf683...`, connected to +18054398008, status `completed`, duration 5s (matches expected length of the spoken line), recording captured (`RE72f2...`, 5s). Confirms both outbound calling and call recording work end-to-end before building anything more complex on top.

**Not yet done:** No streaming audio, no Deepgram STT, no turn-detection, no TTS reply, no transcript saving yet. Twilio auto-recharge still not turned off — user reviewing.

---

## 2026-08-19 — Approach for Step 1, piece 2: streaming audio (documented before building)

Piece 2 (Twilio → live audio → Deepgram transcription) is a bigger jump in complexity than piece 1, so before writing code, the piece itself is broken down further and the known failure points are named ahead of time — same "verify before advancing" principle, applied at finer grain because more can silently go wrong here.

**Sub-pieces, each its own checkpoint:**
1. WebSocket server + ngrok tunnel reachable at all — a trivial echo test, before Twilio is involved.
2. Twilio's TwiML pointed at that WebSocket, confirm Twilio actually connects and sends media frames — log frame count/bytes only, no Deepgram yet. Isolates "is Twilio wired to my server correctly" as its own checkpoint.
3. Pipe those frames to Deepgram's streaming API, print live transcripts. Isolates the STT wiring as the last checkpoint before combining.

**Known failure points in this exact stack, named in advance so they're recognized instead of debugged blind:**
- Twilio Media Streams sends 8kHz **mulaw**-encoded audio in base64 — Deepgram must be told this exact encoding/sample rate, or it mistranscribes silently rather than erroring clearly.
- Twilio's messages are a JSON envelope with event types (`connected`, `start`, `media`, `stop`) — raw audio is nested inside `media` events, not the whole payload.
- The Stream URL must be `wss://`, not `ws://`.
- ngrok's free tier issues a new URL every restart — the TwiML webhook must be updated to match each time, easy to forget and debug the wrong layer.

**Practice while building:** log liberally at each checkpoint (frame counts, raw transcript text) rather than assuming success — a wrong sample rate still produces *a* transcript, just a garbled one, which looks like progress at a glance if not actually inspected. Commit to git between sub-pieces so a break in the next layer is attributable, not stacked on top of unverified work.

---

## 2026-08-19 — Step 1, piece 2, sub-piece 1: WebSocket + ngrok tunnel confirmed reachable

**What happened:** Installed ngrok (via Homebrew) and FastAPI/Uvicorn/websockets. ngrok requires its own free account + authtoken to open tunnels — one more account added to Step 0's list, not anticipated in the original plan. Wrote `ws_echo_test.py`, a minimal local WebSocket echo server, and confirmed the full path before Twilio is involved at all: local server responds → ngrok tunnel exposes it publicly (`https://humorous-subheader-exorcism.ngrok-free.dev`) → a `wss://` WebSocket client connected through that public URL and got a correct echo back → server log confirms the connection came from an external IP, not localhost, proving it actually round-tripped the public internet rather than taking a local shortcut.

**Decision:** Left the server and ngrok tunnel running rather than restarting them for the next sub-piece, since ngrok's free tier assigns a new URL on every restart — reusing this session avoids having to re-sync the TwiML webhook URL mid-step.

**Not yet done:** Twilio isn't wired to this WebSocket yet (sub-piece 2, next). No Deepgram involved yet (sub-piece 3).

---

## 2026-08-19 — Step 1, piece 2, sub-piece 2: real Twilio media frames confirmed

**What happened:** Added a `/media-stream` endpoint to `ws_echo_test.py` that logs Twilio's event envelope (`connected`, `start`, `media`, `stop`) and frame/byte counts only — no Deepgram yet, isolating "does Twilio's audio actually arrive, and in what shape" as its own checkpoint. Wrote `test_media_stream_call.py`, which places a real call with `<Connect><Stream>` TwiML pointed at the ngrok URL, then auto-hangs-up after ~10s so the test doesn't run indefinitely.

First run showed the WebSocket connecting and closing but **zero event logs** — looked like Twilio wasn't sending anything. Root cause: Python's stdout buffering was delaying `print()` output when redirected to a file from a background process; uvicorn's own logger flushed independently, which is why connection-level logs appeared but not our own. Fixed by rerunning with `python3 -u` (unbuffered). Real example of "log liberally, verify immediately" catching a tooling issue rather than an actual pipeline bug — worth keeping as a debugging example for the video walkthrough.

Second run, unbuffered, confirmed the real thing: `protocol=Call`, correct `streamSid`/`callSid`, `mediaFormat: {encoding: audio/x-mulaw, sampleRate: 8000, channels: 1}` — matches the mulaw/8kHz format the Section 7 research flagged as required for Deepgram, confirmed directly rather than assumed. 358 media frames received over the ~10s window, clean `stop` event.

**Not yet done:** Frames aren't going to Deepgram yet (sub-piece 3, next). No TTS reply, no turn-detection logic, no transcript saving.

---

## 2026-08-19 — Step 1, piece 2, sub-piece 3: live Deepgram transcription confirmed (piece 2 complete)

**What happened:** Extended `/media-stream` to open a second WebSocket to Deepgram's streaming endpoint (`wss://api.deepgram.com/v1/listen`, `encoding=mulaw&sample_rate=8000&channels=1`, direct connection rather than the full SDK — kept dependencies minimal for what this checkpoint needs), running two concurrent async loops: one decoding Twilio's base64 audio and forwarding raw bytes to Deepgram, one reading Deepgram's responses and printing transcripts. Confirmed the `websockets` library's connect signature uses `additional_headers` (not `extra_headers`, which is the older/deprecated name still common in outdated examples online) before writing the call, rather than hitting it as a runtime error.

Ran a real test call — got a real, legible transcript of Pretty Good AI's own system message: interim results built up progressively (`"This call"` → `"This call may be recorded"` → `"This call may be recorded for quality and train"`) then locked into `[FINAL] "This call may be recorded for quality and training purposes."` 318 frames forwarded, clean shutdown.

**This closes out Step 1, piece 2.** The three genuinely unfamiliar unknowns named at the start of the plan — telephony, streaming audio wiring, and STT — are now proven working together end-to-end on a real call, not assumed.

**Not yet done:** No turn-detection logic yet (piece 3 — currently the test call is cut off by a fixed 10s timer, not by detecting a natural pause). No TTS reply (piece 4). No transcript saved to disk (piece 5).

---

## 2026-08-19 — Step 1, piece 3: real turn-detection confirmed

**What happened:** Added `endpointing=300&utterance_end_ms=1000` to the Deepgram connection and had the server react to `speech_final`/`UtteranceEnd` signals by hanging up the call itself via the Twilio REST API — replacing the fixed 10s timer from piece 2 with an actual "the far end stopped talking" signal. Chose to have the server end the call directly (using the `callSid` captured from Twilio's `start` event) rather than have the external test script keep timing/polling — closer to how the real bot will eventually behave, where the pipeline itself reacts to a turn boundary. Rewrote `test_media_stream_call.py` to just poll call status with a 30s safety cap, instead of force-hanging-up on a timer — the cap exists only so a detection bug can't leave a call running indefinitely, not as the primary mechanism.

Ran a real test call: `speech_final` fired immediately after Deepgram's real final transcript (`"This call may be recorded for quality and training purposes."`), and the call ended cleanly at **8.7 seconds** — well under the old fixed 10s cutoff and driven by an actual turn boundary, not a guess. This is the eval's turn-taking requirement (criterion #1, the hard gate) demonstrated directly, not assumed.

**Not yet done:** No TTS reply yet (piece 4 — the call currently just hangs up silently once their agent stops talking, doesn't say anything back). No transcript saved to disk yet (piece 5).

---
