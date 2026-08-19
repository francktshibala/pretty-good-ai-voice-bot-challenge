# Build Log

Running record of what was built, real decisions/tradeoffs made and why, and anything that didn't go as expected. Short, factual entries — not essays. See `PLAN.md` for the full plan this log tracks against.

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
