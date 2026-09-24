async function checkedResponse(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status}).`);
  }
  return response;
}

async function postJson(url, data, signal) {
  const response = await checkedResponse(url, {
    method: "POST", signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return response.json();
}

export async function transcribeRecording(file, signal, onSegment) {
  if (!file) {
    const transcript = await postJson("/api/transcribe", { audio_id: "demo" }, signal);
    transcript.segments.forEach(onSegment);
    return;
  }

  const form = new FormData();
  form.append("audio", file);
  const response = await checkedResponse("/api/transcribe/upload", { method: "POST", body: form, signal });
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary;
      // A network chunk can contain part of an event or several events.
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        if (!frame.startsWith("data: ")) continue;
        const event = JSON.parse(frame.slice(6));
        if (event.type === "error") throw new Error(event.error);
        if (event.type === "segment") onSegment(event.segment);
        if (event.type === "done") completed = true;
      }
      if (done) break;
    }
    if (!completed) throw new Error("Transcription connection ended before completion.");
  } finally {
    reader.releaseLock();
  }
}

export function startCall({ audio, file, onTranscript, onDetection, onTime, onDone, onError }) {
  const controller = new AbortController();
  const { signal } = controller;
  const segments = [];
  const heard = [];
  let nextSegment = 0;
  let transcribed = false;
  let analyzing = false;
  let finished = false;

  function stop() {
    controller.abort();
    audio.pause();
    audio.removeEventListener("timeupdate", update);
    audio.removeEventListener("ended", update);
    audio.removeEventListener("error", playbackError);
  }

  function fail(error) {
    if (signal.aborted) return;
    stop();
    onError(error.message);
  }

  function playbackError() {
    fail(new Error("This recording could not be played. Try a WAV or MP3 file."));
  }

  async function update() {
    if (signal.aborted || finished) return;
    onTime(audio.currentTime);
    if (analyzing) return;
    analyzing = true;
    try {
      while (nextSegment < segments.length && !signal.aborted) {
        const segment = segments[nextSegment];
        // Whisper may finish before playback. Never analyse unheard segments.
        const end = Number.isFinite(audio.duration)
          ? Math.min(segment.end_seconds, audio.duration) : segment.end_seconds;
        if (end > audio.currentTime) break;
        heard.push(segment.text);
        nextSegment += 1;
        const text = heard.join(" ");
        onTranscript(text);
        const result = await postJson("/api/analyze", { transcript: text }, signal);
        if (signal.aborted) return;
        onDetection(result, end);
      }
      if (transcribed && audio.ended && nextSegment === segments.length) {
        finished = true;
        stop();
        onDone(heard.length > 0);
      }
    } catch (error) {
      fail(error);
    } finally {
      analyzing = false;
    }
  }

  audio.addEventListener("timeupdate", update);
  audio.addEventListener("ended", update);
  audio.addEventListener("error", playbackError);
  audio.currentTime = 0;
  // Start during the user's Accept click so browser autoplay rules allow it.
  audio.play().catch(fail);
  transcribeRecording(file, signal, (segment) => {
    if (signal.aborted) return;
    segments.push(segment);
    void update();
  }).then(() => {
    if (signal.aborted) return;
    transcribed = true;
    void update();
  }).catch(fail);
  return stop;
}
