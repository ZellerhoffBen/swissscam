import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { setImmediate } from "node:timers/promises";
import test from "node:test";
import demo from "./demo.js";
import { startCall } from "./callSession.js";

class Recording extends EventTarget {
  currentTime = 0;
  duration = demo.segments.at(-1).end_seconds + 1;
  ended = false;
  paused = true;
  async play() { this.ended = false; this.paused = false; }
  pause() { this.paused = true; }
  tick(seconds) {
    this.currentTime = seconds;
    this.ended = seconds >= this.duration;
    this.dispatchEvent(new Event(this.ended ? "ended" : "timeupdate"));
  }
}

const callbacks = () => ({ onTranscript() {}, onDetection() {}, onTime() {}, onDone() {}, onError: assert.fail });

test("saved results match the shipped audio and have ordered timestamps", () => {
  const audio = readFileSync(new URL("../public" + demo.audio, import.meta.url));
  assert.equal(createHash("sha256").update(audio).digest("hex"), demo.audio_sha256);
  let end = 0;
  for (const segment of demo.segments) {
    assert.ok(segment.text.trim());
    assert.ok(segment.end_seconds > end);
    assert.ok(segment.detection.score >= 0 && segment.detection.score <= 1);
    assert.equal(segment.detection.warning, segment.detection.score >= segment.detection.threshold);
    end = segment.end_seconds;
  }
  assert.ok(demo.segments.some((s) => s.detection.warning));
});

test("replays only heard segments, keeps playing after a warning, and finishes once", (t) => {
  t.mock.method(globalThis, "fetch", () => assert.fail("Static playback must not call an API"));
  const audio = new Recording();
  const results = [];
  let transcript = "";
  let completed = 0;
  const stop = startCall({ audio, ...callbacks(),
    onTranscript: (text) => { transcript = text; },
    onDetection: (result, seconds) => results.push({ result, seconds }),
    onDone: () => { completed += 1; },
  });
  t.after(stop);
  audio.tick(demo.segments[0].end_seconds - 0.01);
  assert.equal(results.length, 0);
  const warningIndex = demo.segments.findIndex((s) => s.detection.warning);
  audio.tick(demo.segments[warningIndex].end_seconds);
  assert.equal(results.length, warningIndex + 1);
  assert.equal(audio.paused, false);
  assert.equal(completed, 0);
  audio.tick(audio.duration);
  assert.equal(results.length, demo.segments.length);
  assert.equal(transcript, demo.segments.map((s) => s.text).join("\n\n"));
  assert.deepEqual(results.map((r) => r.seconds), demo.segments.map((s) => s.end_seconds));
  audio.tick(audio.duration);
  assert.equal(completed, 1);
  assert.equal(audio.paused, true);
});

test("end call removes listeners and a new call starts at the beginning", () => {
  const audio = new Recording();
  let updates = 0;
  const options = { audio, ...callbacks(), onDetection: () => { updates += 1; } };
  const stop = startCall(options);
  audio.tick(demo.segments[0].end_seconds);
  stop();
  audio.tick(audio.duration);
  assert.equal(updates, 1);
  assert.equal(audio.paused, true);
  const stopReplay = startCall(options);
  assert.equal(audio.currentTime, 0);
  audio.tick(demo.segments[0].end_seconds);
  assert.equal(updates, 2);
  stopReplay();
});

test("playback failures stop the demo; stale failures after stop are ignored", async () => {
  const audio = new Recording();
  let errors = 0;
  audio.play = () => Promise.reject(new Error("Playback blocked"));
  const options = { audio, ...callbacks(), onError: () => { errors += 1; } };
  startCall(options);
  await setImmediate();
  assert.equal(errors, 1);
  assert.equal(audio.paused, true);
  const stop = startCall(options);
  stop();
  await setImmediate();
  assert.equal(errors, 1);
});
