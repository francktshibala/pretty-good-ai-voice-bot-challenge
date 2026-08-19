# Bug Categories — Step 3

Defined deliberately, before the real Step 4 calls, per the plan's eval criterion #2
(quality of bugs found) and #5 (evidence of iteration — these categories are informed
by what Step 2's mechanism-proving calls already surfaced, not written blind).

Each category: what it means concretely in this system, real evidence already seen
(if any), and how Step 4 will deliberately probe for it.

---

## 1. Latency / dead air
**What it means here:** noticeable silence between their agent finishing a turn and
either side responding — awkward pauses, not natural conversational rhythm.
**Not yet specifically measured** — worth timestamping in Step 4 (compare Deepgram's
`speech_final` timestamp to when our reply audio starts playing, and separately note
any long agent-side silences before *they* respond).
**How to probe:** no special scenario needed — listen for this in every real call, but
flag it explicitly per call rather than only noticing it if it's bad enough to be obvious.

## 2. Misheard input
**What it means here:** their agent (or our own Deepgram, which needs separating from
their bug — see the attribution caveat logged in Step 2) mishears something the
patient said.
**Already seen:** their agent heard "Maria" as "Marie" once, mid-call.
**How to probe:** scenarios that require precise recognition of things that are
genuinely easy to mishear — spelling a last name, giving a phone number or insurance
member ID digit-by-digit, an uncommon medication name.

## 3. Repeated or looping questions
**What it means here:** the agent asks something already answered, or re-asks the same
question without acknowledging a given answer — not the same as an incomplete/garbled
utterance (see #7).
**Not yet seen directly** — Step 2's calls showed dropped audio, not true repetition loops.
**How to probe:** a scenario where the patient gives an answer, then the persona
deliberately pauses or gives a partial/mumbled response, to see if the agent handles it
gracefully or resets and re-asks from scratch.

## 4. Incorrect or unsafe information given
**What it means here:** the agent states something false, or gives guidance it
shouldn't (e.g. anything resembling medical advice).
**Already seen, strong example:** the agent fabricated a date of birth ("July fourth
two thousand, for demo purposes") that the patient never gave — did not reproduce on a
second run, so possibly intermittent or branch-dependent.
**How to probe:** scenarios asking factual questions with a checkable right answer
(clinic hours, accepted insurance, walk-in availability) and a prescription-refill
scenario that tests whether the agent inappropriately answers a dosage/medical question
instead of deferring to a clinician.

## 5. Failure to handle interruption
**What it means here:** does their system break, go silent, or misbehave if the caller
starts talking before the agent finishes its turn.
**Architecture note, not yet resolved:** our bot currently always waits for the agent's
full turn-end (`speech_final`/`UtteranceEnd`) before replying — it does not currently
support deliberately barging in mid-agent-speech. Genuinely testing this category means
either building that capability into the bot, or handling it as a one-off manual test
rather than the bot's normal behavior. Decide before Step 4 which approach to use.
**How to probe:** once resolved, one deliberate scenario where the persona interjects
partway through the agent's turn.

## 6. Failure on ambiguous or unclear input
**What it means here:** the agent's response to a vague answer — does it ask a
sensible clarifying question, or silently guess/break?
**How to probe:** scenarios with intentionally vague answers ("sometime next week,"
"I'm not sure which insurance I have," "maybe Tuesday or Wednesday, whichever").

## 7. Audio dropout / garbled or truncated agent speech (added from real evidence, not in the original plan list)
**What it means here:** the agent's own utterance comes through incomplete or cut off
mid-sentence — distinct from a misheard word (#2), this is the agent's turn ending
before it finished speaking.
**Already seen, twice in one call:** *"Please provide your"* then *"Please provide"* —
two incomplete fragments in a row before the actual question ("please tell me your
date of birth") came through intact on the third attempt.
**How to probe:** no special scenario needed — same as latency, flag explicitly
whenever it happens rather than only if it's severe enough to be unmissable.

---

## Attribution discipline (carried from Step 2's log)

Before writing any finding into the final bug report, check it against the actual
recording audio, not just the Deepgram transcript — our own STT can introduce
artifacts (a transcript reading "As soon afternoon openings" was very likely
Deepgram mis-hearing "the soonest," not their system saying something broken).
Misattributing our own STT noise as their bug would undermine the whole report.

## Next: Step 4 scenario design

Each real call in Step 4 should be designed against a specific scenario (scheduling,
rescheduling, refill, hours/insurance question, edge case) *and* deliberately aimed at
one or more of the categories above — not 10 similar calls reverse-engineered into a
report afterward.
