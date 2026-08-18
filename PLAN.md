# Pretty Good AI — Voice Bot Challenge: Complete Plan

---

## 1. The Actual Task

Build a Python voice bot that:
1. Calls only the test number: **+1-805-439-8008**
2. Acts as a realistic "patient" (scheduling, refills, questions, edge cases)
3. Records and transcribes every conversation
4. Finds and documents real bugs/quality issues in their agent

**Setup note:** create a test account at pgai.us/athena first, for context on how the product works. Do not call the number shown on that confirmation screen, only the test number above.

---

## 2. Full Deliverables Checklist

- [ ] **Working code** (Python), in a **public** GitHub repo
- [ ] **README** — clear setup + ideally a single command to run after setup
- [ ] **Architecture doc** — 1–2 paragraphs: what you built, and *why*, tradeoffs considered, alternatives evaluated
- [ ] **10+ real recorded calls**, both sides, 1–3 minutes each (not a single question and hang-up)
  - [ ] Audio in **OGG or MP3**
  - [ ] Matching transcript per call
- [ ] **Bug report** — clear, not necessarily in their exact format, just: what happened, why it's a problem, where to find it
- [ ] **2 public Loom videos**, own voice, webcam on:
  - [ ] Walkthrough of approach and what you built (max 3 min)
  - [ ] Screen recording of you prompting AI to debug/fix code, showing your actual prompts
- [ ] **Submission form**, including:
  - [ ] The **single phone number** used for every test call, in E.164 format (e.g. +13334445555)
- [ ] **Receipts** for API/telephony costs, if requesting the $20 reimbursement

**Cost expectation:** typically under $20 total, reimbursed with receipts.

---

## 3. What They're Actually Evaluating (in priority order)

1. **Coherent voice conversation, first.** This is a hard gate. Fail this and the rest isn't reviewed.
2. **Quality of bugs found** — a few real, well-described issues beat a long list of nitpicks
3. **Working code that makes real calls**
4. **Clear thinking** — architecture doc + Loom must explain *why*, not just *what*. Reasoning about Realtime APIs, architecture, tradeoffs, alternatives considered
5. **Evidence of iteration** — did it visibly improve after early results?
6. **Clean enough code to read** — not perfect, just understandable

**Explicitly NOT wanted:** perfect code, over-engineering, fancy diagrams, punctuation nitpicks, one-shot AI copy-paste, production-grade infrastructure.

**Minimum bar for every call:** natural voice interaction, sensible turn-taking (unless deliberately testing barge-in), active steering toward the intended test outcome, realistic pacing, minimal glitches/latency/awkward pauses. It should feel like a real user, not a scripted benchmark runner.

---

## 4. The Real Components, and Why Each One Matters

| Component | New to you? | Why it matters here |
|---|---|---|
| Telephony (placing/holding the real call) | Yes | Nothing works without this |
| Turn-taking / end-of-turn detection (VAD) | Yes | Directly maps to eval criterion #1, the hard gate |
| Speech-to-text (understanding their agent) | Yes | Feeds every decision the bot makes |
| Call recording + transcript persistence | Infra, but new in this context | 2 of your deliverables depend entirely on this working |
| LLM decision-making (what a patient would say) | **Already proven** | Same pattern as your dictionary feature's provider-racing logic |
| Text-to-speech (ElevenLabs) | **Already proven** | Already shipped in BookBridge |

---

## 5. Build Order — Risk-First, Synthesized Plan

**Step 0: Account and infrastructure setup (do this first, before any code)**
- **Twilio: upgrade to a paid account before anything else — trial will not work.** Confirmed: trial accounts can only call numbers verified via a code sent to that number, which is impossible for a third party's business line (+1-805-439-8008 belongs to Pretty Good AI, not you) — the call fails outright (error 32100). Even on a verified number, trial accounts inject an audible "upgrade your account" message before any audio plays, which breaks the clean-recording requirement regardless. Twilio's suggested minimum top-up is **$20**, which is the entire reimbursement budget on its own (though actual usage cost for ~10 calls is trivial, under $1). Check the Twilio console directly for whether a smaller top-up is actually accepted before assuming the full $20 is required.
- ElevenLabs API key confirmed working
- STT provider: **Deepgram Nova-3 streaming**, confirmed as the right call — its built-in `endpointing`/`utterance_end_ms` params handle turn-detection directly in the stream, so no separate VAD library is needed. Pay-as-you-go ~$0.0077/min, $200 free credit to start. (AssemblyAI is cheaper for plain transcription but charges extra — a pricier tier — to get comparable turn-detection.)
- LLM API key confirmed working
- `.env.example` scaffolded from the start, not bolted on later

**Step 1: The thin, real, working path (the walking skeleton)**
Build all of these together, as one connected pass, before adding real intelligence:
- A real call connects through Twilio to +1-805-439-8008
- Streaming speech-to-text is transcribing their agent's audio
- End-of-turn detection (VAD) correctly identifies when their agent stops talking
- A **scripted, dumb reply** goes out through ElevenLabs, just to prove the full loop works
- Call recording and transcript-saving both work correctly, end to end

**Do not move on until this thin path is solid.** This is where telephony, STT, and turn-taking, your three real unknowns, get proven cheaply.

**Step 2: Swap in real intelligence**
- Replace the scripted reply with real LLM reasoning
- Give it a clear patient persona and a specific scenario goal per call
- This is the part you already know how to build well

**Step 3: Define bug categories before making real calls**
Example categories to test against deliberately, not discover by accident:
- Latency / dead air
- Misheard input
- Repeated or looping questions
- Incorrect or unsafe information given
- Failure to handle interruption
- Failure on ambiguous or unclear input

**Step 4: Make the real 10+ calls**
Design calls deliberately across scenarios (scheduling, rescheduling, refills, hours/insurance questions, edge cases) and across your bug categories above, not 10 similar calls you reverse-engineer a report from afterward.

**Step 5: Iterate visibly**
Let real call results drive real fixes. This directly satisfies eval criterion #5, keep a rough sense of what changed after which round of calls, useful for both the bug report and the Loom walkthrough.

**Step 6: Deliverables**
- Write the architecture doc explaining *why*, not just *what*
- Write the bug report
- Record both Loom videos (own voice, webcam on)
- Push the public GitHub repo
- Submit the form with your single test phone number in E.164 format
- Save receipts if claiming reimbursement

---

## 6. Testing Philosophy for This Project

- **No TDD on conversational quality.** "Did that sound natural" isn't a unit test.
- **Lightweight tests only on deterministic infrastructure**: file-saving, transcript formatting, bug-report structure.
- **No CI/CD.** Explicitly not wanted for a single 6-hour submission.
- **Real calls are the actual test suite.** Trust what you hear over what you assume.

---

## 7. Architecture Decisions (resolved 2026-08-18, via pre-implementation research)

- **STT/VAD — resolved: Deepgram Nova-3 streaming, no separate VAD library.** Its built-in `endpointing` / `utterance_end_ms` params detect turn-completion directly in the WebSocket stream. AssemblyAI is cheaper for raw transcription but gates comparable turn-detection behind a pricier tier. A standalone VAD (Silero/WebRTC) is only clearly justified for low-latency barge-in detection on the bot's own outbound audio — not needed for this project's scope; a simple energy-threshold check is enough if barge-in is tested at all.
- **Build approach — resolved: hybrid, not fully custom and not fully managed.** Use **Pipecat** (or LiveKit Agents) to handle real-time plumbing (audio streaming, turn-taking, interruption handling) over Twilio, while still explicitly choosing and wiring your own Deepgram (STT) + LLM + ElevenLabs (TTS) — same components as the original custom plan, just with the plumbing layer handled by a framework instead of hand-rolled. Reasoning: fully custom risks burning the 6-hour budget on unfamiliar telephony/VAD/audio-buffering plumbing; fully managed platforms (Vapi/Retell/Bland) are fast but hide the STT/LLM/TTS/turn-taking wiring behind a dashboard, which undercuts eval criterion #4 (there's little architecture left to reason about if it's a black box), and are built for generic assistants rather than an adversarial bug-hunting patient persona. This line of reasoning is what should go in the architecture doc's "alternatives evaluated" section.
- **Telephony — Twilio confirmed as provider, but requires a paid account.** See Step 0 above: trial accounts cannot call the test number at all, and even verified numbers get an audible upgrade-prompt injected that would break the recording requirement. This is a real budget conflict (Twilio's suggested top-up is $20, the full reimbursement cap) worth deciding on explicitly before Step 0, not discovering mid-build.

---

## What To Do From Here

1. **Resolve the Twilio budget question first** — decide whether to top up the suggested $20 (using the full reimbursement on telephony alone, since actual usage cost is under $1) or check the Twilio console for a smaller accepted top-up amount.
2. **Do the rest of Step 0**, before writing any code: get every remaining account and API key (ElevenLabs, Deepgram, LLM) working in isolation.
3. Once accounts are confirmed, open Cursor and hand Claude Code this plan directly, along with the resolved decisions in Section 7, and build Step 1, the thin walking skeleton, first — using Pipecat/LiveKit Agents + Twilio + Deepgram + ElevenLabs.
4. Don't touch Step 2 (real LLM intelligence) until Step 1 is genuinely solid and tested with a real call.
5. Come back here if anything in the plan needs to change once you're actually building, this document should stay the source of truth, not just an initial idea.
