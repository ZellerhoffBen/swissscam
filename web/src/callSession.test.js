import assert from "node:assert/strict";
import { setImmediate } from "node:timers/promises";
import test from "node:test";
import { startCall, transcribeRecording } from "./callSession.js";

// Playback and network timing are controlled; no Whisper download is needed.
class Recording extends EventTarget {
  currentTime = 0;
  duration = 4;
  ended = false;
  paused = true;
  async play() { this.paused = false; }
  pause() { this.paused = true; }
  tick(seconds) {
    this.currentTime = seconds;
    this.ended = seconds >= this.duration;
    this.dispatchEvent(new Event(this.ended ? "ended" : "timeupdate"));
  }
}

const segments = [
  { text: "Hello from your bank.", start_seconds: 0, end_seconds: 2 },
  { text: "Read me your code.", start_seconds: 2, end_seconds: 4 },
];
const json = (data) => new Response(JSON.stringify(data));
const callbacks = () => ({ onTranscript() {}, onDetection() {}, onTime() {}, onDone() {}, onError: assert.fail });
const flush = async () => { await setImmediate(); await setImmediate(); };

test("only heard segments reach the model, in order, with accumulated text", async (t) => {
  const requests = [];
  let releaseFirst;
  t.mock.method(globalThis, "fetch", async (url, options) => {
    if (url === "/api/transcribe") return json({ segments });
    requests.push(JSON.parse(options.body).transcript);
    if (requests.length === 1) await new Promise((resolve) => { releaseFirst = resolve; });
    return json({ warning: requests.length > 1, signals: [], reason: "" });
  });
  const audio = new Recording();
  const results = [];
  const timestamps = [];
  const stop = startCall({ audio, ...callbacks(), onDetection: (result, seconds) => {
    results.push(result);
    timestamps.push(seconds);
  } });
  t.after(stop);
  await flush();
  assert.deepEqual(requests, []);
  audio.tick(1);
  assert.deepEqual(requests, []);
  audio.tick(2);
  await flush();
  assert.deepEqual(requests, [segments[0].text]);
  audio.tick(4);
  await flush();
  assert.equal(requests.length, 1, "do not send overlapping analysis requests");
  releaseFirst();
  await flush();
  assert.deepEqual(requests, [segments[0].text, segments.map((s) => s.text).join("\n\n")]);
  assert.deepEqual(results.map((r) => r.warning), [false, true]);
  assert.deepEqual(timestamps, [2, 4], "history uses transcript timestamps, not late response arrival times");
});

test("ending a call discards a late model response and stops playback", async (t) => {
  let release;
  let updates = 0;
  t.mock.method(globalThis, "fetch", async (url) => {
    if (url === "/api/transcribe") return json({ segments });
    await new Promise((resolve) => { release = resolve; });
    return json({ warning: true });
  });
  const audio = new Recording();
  const stop = startCall({ audio, ...callbacks(), onDetection: () => { updates += 1; } });
  await flush();
  audio.tick(2);
  await flush();
  stop();
  release();
  audio.tick(4);
  await flush();
  assert.equal(updates, 0);
  assert.equal(audio.paused, true);
});

test("transcription can finish after playback without losing the last analysis", async (t) => {
  let release;
  let done = false;
  const requests = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    if (url === "/api/transcribe") {
      await new Promise((resolve) => { release = resolve; });
      return json({ segments });
    }
    requests.push(JSON.parse(options.body).transcript);
    return json({ warning: false });
  });
  const audio = new Recording();
  const stop = startCall({ audio, ...callbacks(), onDone: (hasSpeech) => { done = hasSpeech; } });
  t.after(stop);
  audio.tick(4);
  assert.equal(done, false);
  release();
  await flush();
  assert.equal(requests.length, 2);
  assert.equal(done, true);
});

test("upload parses split UTF-8 events and ignores future cumulative text", async (t) => {
  const file = new File(["audio fixture"], "call.wav");
  const event = { type: "segment", text: "Future text must not be displayed", segment: { ...segments[0], text: "Grüezi" } };
  const bytes = new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\ndata: {"type":"done"}\n\n`);
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "/api/transcribe/upload");
    assert.equal(options.body.get("audio").name, "call.wav");
    return new Response(new ReadableStream({ start(controller) {
      for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
      controller.close();
    } }));
  });
  const received = [];
  await transcribeRecording(file, new AbortController().signal, (s) => received.push(s));
  assert.deepEqual(received, [event.segment]);
});

test("failed or interrupted transcription is not reported as complete", async (t) => {
  const file = new File(["invalid"], "bad.wav");
  t.mock.method(globalThis, "fetch", async () => new Response('data: {"type":"error","error":"Invalid audio"}\n\n'));
  await assert.rejects(transcribeRecording(file, new AbortController().signal, assert.fail), /Invalid audio/);
  globalThis.fetch = async () => new Response("");
  await assert.rejects(transcribeRecording(file, new AbortController().signal, assert.fail), /before completion/);
});

test("an analysis error stops playback and reports a visible error", async (t) => {
  t.mock.method(globalThis, "fetch", async (url) => url === "/api/transcribe"
    ? json({ segments }) : new Response('{"detail":"Classifier unavailable"}', { status: 503 }));
  const audio = new Recording();
  let error = "";
  const stop = startCall({ audio, ...callbacks(), onError: (message) => { error = message; } });
  t.after(stop);
  await flush();
  audio.tick(2);
  await flush();
  assert.equal(error, "Classifier unavailable");
  assert.equal(audio.paused, true);
});
