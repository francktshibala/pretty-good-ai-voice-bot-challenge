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
