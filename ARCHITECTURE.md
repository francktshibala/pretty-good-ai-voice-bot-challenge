# Architecture

**What was built:** a Python voice bot that places real outbound calls via Twilio,
streams live caller audio to Deepgram for transcription, uses Deepgram's own
endpointing (`speech_final`/`UtteranceEnd`) to detect real turn boundaries instead
of a fixed timer, generates a patient-persona reply with an LLM (OpenAI, after
switching from Anthropic mid-build when Anthropic credits ran out), speaks it back
through ElevenLabs over the same bidirectional Twilio Media Stream, and saves a
transcript + recording automatically once the call ends. Each of the 12 real calls
runs a distinct persona and scenario, loaded from a small JSON config selected via
Twilio's `<Parameter>` mechanism rather than hardcoded — letting 12 different
patients run without editing the server between calls. One call type deliberately
barges in on the agent mid-sentence (based on interim, not final, transcripts) to
test interruption handling, a capability the bot doesn't otherwise use, since
natural turn-taking is the default and interruption is a specific test, not normal
behavior.

**Why this stack, and what else was considered:** the three genuinely unfamiliar
pieces — telephony, streaming STT, and turn-taking — were built and proven
individually before any LLM logic was added on top (documented step by step in
`BUILD_LOG.md`), rather than building the whole pipeline at once and debugging it
as one unit. Two real architecture decisions were made with actual research rather
than assumption, both recorded in `PLAN.md`'s Section 7: Deepgram was chosen over
AssemblyAI because its base streaming tier includes endpointing for free, where
AssemblyAI gates comparable turn-detection behind a pricier tier; and the pipeline
was hand-wired directly (Twilio + Deepgram + LLM + ElevenLabs) rather than built on
a managed voice-AI platform (Vapi, Retell, Bland) or a mid-layer framework like
Pipecat. The tradeoff: hand-wiring costs more setup time and required working
through real integration bugs — Twilio's `<Stream>` verb not forwarding URL query
parameters as expected, a stdout-buffering issue that briefly hid real event logs
as if nothing were arriving — but a managed platform would have hidden exactly the
architecture decisions this evaluation asks to see reasoned about, and would have
made deliberately testing interruption handling (barge-in) much harder to build as
a controlled, one-time capability rather than a black-boxed platform feature.

**Safety and cost bounds:** every real call is bounded by two independent caps
(`MAX_TURNS`, `MAX_CALL_SECONDS`) so a misbehaving LLM or an unresponsive target
system can never turn into an open-ended call — the same reasoning applied to
turning off Twilio's auto-recharge during testing. These caps were raised once
during Step 2 after an early real call showed 8 turns wasn't enough to reach a
natural conclusion; the current values (16 turns / 180s) were sized against actual
observed conversation lengths, not guessed upfront.
