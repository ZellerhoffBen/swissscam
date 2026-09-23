# swissscam

A local scam-call detector that warns people when a conversation shows signs of social engineering. Built with elderly and vulnerable users in mind.

Working plan for our three-person hackathon team. This describes what we intend to build, not what already works.

## Goal

Show a simulated English phone call, analyse the conversation as it unfolds, and display a clear warning before the victim shares sensitive information.

Our main demo: a fake bank employee claims to help recover an account and pressures the victim to share a one-time code. This connects our idea to the Swisscom challenge on identity fraud and account recovery.

## Scope

**Build:**

- One simple call screen: start, end, transcript, warning.
- Incremental analysis of the conversation so far.
- Local detection of suspicious requests and manipulation.
- A short explanation and the choice to end or continue the call.
- Two demo conversations: a scam and a similar legitimate bank call.

**Leave out:** real phone integration, user accounts, databases, automatic reporting, number reputation, deepfake voice detection, and multiple languages.

English is our demo language. Swiss German support is future work. Local means running on our demo laptop; phone performance is not yet proven.

## How it works

```text
Simulated call
      |
      v
Transcript arrives in small chunks
      |
      v
Local detector reads the conversation so far
      |
      v
Call screen updates; a warning appears if needed
```

Start with scripted transcript chunks to connect the whole flow. Then add locally transcribed audio from a staged call. Keep transcript replay as a clearly labelled fallback.

The detector must only see text that has already arrived. Warnings must come from its output, not from a scenario name or a preset timer.

Example warning:

> Possible scam. The caller is pressuring you to share a one-time code.
>
> End call · Continue

Use large, readable controls and plain language. Keep the transcript for the demo; do not make users read it to understand a warning. No warning does not mean a call is safe.

## Small, shared interface

```python
detect(transcript_history) -> {
    "warning": True,
    "signals": ["urgency", "otp_request"],
    "reason": "The caller is pressuring you to share a one-time code."
}
```

`transcript_history` contains the conversation so far, with speaker labels where available. No numeric probability is needed for the first version.

Start with readable rules to make the pipeline work. Then try one small local text classifier and compare it with that baseline. Choose the model together; training a model from scratch is not required. A bank greeting or the word “urgent” alone should not trigger a warning.

## Proposed structure

Keep the existing Python project. Use a small browser UI with one local Python backend; choose libraries together before implementation.

```text
main.py          # Local app entry point
detector.py      # Conversation analysis
transcription.py # Local speech-to-text, added after replay works
web/             # Call screen and its styling
data/            # Demo scripts and training examples
evaluation/      # Separate test conversations and results
```

These are planned files. Create them only when needed. No separate services, database, or deployment setup.

## Build order and ownership

| Step | Done when |
| --- | --- |
| 1. Agree on the demo | Both scripts and the first dangerous request are written down. |
| 2. Connect the flow | Transcript replay → detector → warning → end/continue works. |
| 3. Improve detection | A local model is compared with the rules on separate examples. |
| 4. Add audio | A staged call is transcribed locally and feeds the same detector. |
| 5. Prepare the pitch | Both demo cases work, results are recorded, and limitations are clear. |

Suggested ownership: one person on UI, one on detection/data, one on the call flow/audio/integration. Agree on the interface first and integrate early. Everyone should be able to explain the full flow.

If time gets tight, stop adding features and finish the working path. Reserve the final 2–3 hours for testing, the pitch, and submission.

## Check whether it works

Use a small, separate set of scam and legitimate conversations, including legitimate security calls. Keep related scripts and paraphrases in the same split; do not train on demo/test scripts.

Record:

- Scams detected / scams tested.
- Legitimate calls incorrectly warned / legitimate calls tested.
- When the first warning appears: before or after the victim reveals a code or agrees to pay.

Report counts and limitations, not just accuracy. A few successful examples are a demo, not proof of real-world reliability. Test the full audio path separately if it is implemented.

The [phone-scam dataset](https://huggingface.co/datasets/menaattia/phone-scam-dataset) is a candidate starting point. Check its provenance, licence, labels, and duplicates before using it. Add realistic account-recovery examples and difficult legitimate calls.

For the challenge: explain how consented, labelled internal fraud examples could improve coverage and reduce false alarms. Access to Swisscom data is not assumed.

## Privacy

Process demo audio and transcripts locally, without external inference services. Keep live conversation data in memory and clear it when the session ends; do not log it by default.

Use fictional scripts and staged recordings with everyone's consent. Local processing does **not** automatically make recording or analysis lawful. A real product needs a separate legal review; see the [Swiss FDPIC guidance on recording conversations](https://www.edoeb.admin.ch/en/recording-conversations).

## Working rules

- KISS / YAGNI: build only what the demo needs.
- Prefer small functions, clear names, and familiar tools.
- Keep changes small and integrate frequently.
- Read and understand AI-generated code before keeping it.
- Add a dependency or abstraction only when it solves a current problem.
- Be explicit about what is simulated, measured, and still unproven.

## Before we start

Agree on ownership, write the two demo scripts, and choose the simplest shared stack. Ask the Swisscom mentors to confirm the account-recovery scenario fits their expectations and verify submission requirements at kickoff.

Reference: [Swiss AI Weeks challenges](https://ai-weeks.ch/2026/challenges).
