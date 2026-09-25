import demo from "./demo.js";

// Replay saved pipeline output against audio time; this performs no live inference.
export function startCall({ audio, onTranscript, onDetection, onTime, onDone, onError }) {
  let nextSegment = 0;
  let stopped = false;
  const heard = [];

  function stop() {
    stopped = true;
    audio.pause();
    audio.removeEventListener("timeupdate", update);
    audio.removeEventListener("ended", update);
    audio.removeEventListener("error", playbackError);
  }

  function fail() {
    if (stopped) return;
    stop();
    onError("The demo recording could not be played. Please try again.");
  }

  function playbackError() {
    fail();
  }

  function update() {
    if (stopped) return;
    onTime(audio.currentTime);
    while (nextSegment < demo.segments.length && !stopped) {
      const segment = demo.segments[nextSegment];
      const end = Number.isFinite(audio.duration)
        ? Math.min(segment.end_seconds, audio.duration) : segment.end_seconds;
      if (end > audio.currentTime) break;
      nextSegment += 1;
      heard.push(segment.text);
      onTranscript(heard.join("\n\n"));
      onDetection(segment.detection, end);
    }
    if (!stopped && audio.ended) {
      stop();
      onDone();
    }
  }

  audio.addEventListener("timeupdate", update);
  audio.addEventListener("ended", update);
  audio.addEventListener("error", playbackError);
  audio.currentTime = 0;
  // Keep playback inside the Accept click to respect browser autoplay rules.
  audio.play().catch(fail);
  return stop;
}
