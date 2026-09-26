import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlarmClock,
  AlertTriangle,
  BatteryFull,
  Camera,
  CircleUserRound,
  Flashlight,
  Grid3X3,
  Info,
  MessageCircle,
  MicOff,
  Phone,
  Plus,
  Signal,
  Video,
  Volume2,
  Wifi,
  X,
} from "lucide-react";
import { startCall } from "./callSession";
import { CallCheck } from "./CallCheck";
import demo from "./demo";
import "./styles.css";

function PhoneStatusBar() {
  return (
    <div className="ios-status-bar">
      <span>9:41</span>
      <div>
        <Signal />
        <Wifi />
        <BatteryFull />
      </div>
    </div>
  );
}

function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

function App() {
  const [status, setStatus] = useState(
    "Start the demo on the phone. Sound on.",
  );
  const [transcript, setTranscript] = useState([]);
  const [detection, setDetection] = useState(null);
  const [riskHistory, setRiskHistory] = useState([]);
  const [analysisState, setAnalysisState] = useState("idle");
  const [phoneState, setPhoneState] = useState("home");
  const [elapsed, setElapsed] = useState(0);
  const [showScamWarning, setShowScamWarning] = useState(false);
  const audioRef = useRef(null);
  const transcriptRef = useRef(null);
  const [followTranscript, setFollowTranscript] = useState(true);
  const stopCallRef = useRef(null);

  useEffect(() => {
    // Start loading system voices before the call reaches a warning.
    window.speechSynthesis?.getVoices();
    return () => stopCallRef.current?.();
  }, []);

  useEffect(() => {
    if (followTranscript && transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [transcript, followTranscript, detection]);

  function endCall() {
    stopCallRef.current?.();
    stopCallRef.current = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setPhoneState(phoneState === "incoming" ? "home" : "ended");
    setAnalysisState((state) => (state === "processing" ? "stopped" : state));
    setShowScamWarning(false);
    setStatus(
      phoneState === "incoming"
        ? "Call declined. Start the demo to try again."
        : "Call ended. Your transcript and results remain below.",
    );
  }

  function resetAnalysis() {
    setAnalysisState("idle");
    setTranscript([]);
    setDetection(null);
    setRiskHistory([]);
    setElapsed(0);
    setShowScamWarning(false);
    setFollowTranscript(true);
  }

  function startIncomingCall() {
    stopCallRef.current?.();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    resetAnalysis();
    setPhoneState("incoming");
    setStatus("Incoming call ready. Accept it to start the recording.");
  }

  function issueScamWarning() {
    setShowScamWarning(true);
    setStatus("Possible scam detected.");

    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const message = new SpeechSynthesisUtterance(
        "Warning, this call may be a scam.",
      );
      message.lang = "en-US";
      const voice = window.speechSynthesis.getVoices().find((voice) => voice.name === "Samantha");
      if (voice) message.voice = voice;
      window.speechSynthesis.speak(message);
    }

    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const context = new AudioContext();
    [0, 0.32, 0.64].forEach((offset) => {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, context.currentTime + offset);
      gain.gain.exponentialRampToValueAtTime(
        0.16,
        context.currentTime + offset + 0.02,
      );
      gain.gain.exponentialRampToValueAtTime(
        0.0001,
        context.currentTime + offset + 0.24,
      );
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(context.currentTime + offset);
      oscillator.stop(context.currentTime + offset + 0.25);
    });
  }

  function acceptCall() {
    stopCallRef.current?.();
    resetAnalysis();
    setPhoneState("active");
    setAnalysisState("processing");
    setStatus("Playing the recording with saved transcript and model results.");
    let warned = false;
    stopCallRef.current = startCall({
      demo,
      audio: audioRef.current,
      onTime: setElapsed,
      onTranscript: setTranscript,
      onDetection: (result, seconds) => {
        setDetection(result);
        setRiskHistory((history) => [
          ...history,
          { seconds, score: result.score },
        ]);
        // Dismissing a warning keeps playback running without repeating the popup.
        if (result.warning && !warned) {
          warned = true;
          issueScamWarning();
        }
      },
      onDone: () => {
        setAnalysisState("complete");
        setStatus(
          "Demo complete. Explore the transcript and results, or replay the call.",
        );
      },
      onError: (message) => {
        setAnalysisState("error");
        setPhoneState("ended");
        setShowScamWarning(false);
        setStatus(message);
      },
    });
  }

  // Keep consecutive updates from the same speaker in one readable turn.
  const turns = [];
  for (const segment of transcript) {
    if (turns.at(-1)?.speaker === segment.speaker) {
      turns.at(-1).text += " " + segment.text;
    } else {
      turns.push({ ...segment });
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <img className="brand-logo" src="/swissscam-logo.png" alt="" />
          <h1>swissscam</h1>
        </div>
        <button
          className="about-button"
          type="button"
          popoverTarget="about-demo"
        >
          <Info size={17} aria-hidden="true" />
          About this demo
        </button>
        <div
          className="about-panel"
          id="about-demo"
          popover="auto"
          aria-labelledby="about-title"
        >
          <div className="about-heading">
            <h2 id="about-title">About swissscam</h2>
            <button
              type="button"
              popoverTarget="about-demo"
              popoverTargetAction="hide"
              aria-label="Close info"
            >
              <X size={18} />
            </button>
          </div>
          <p>
            A hackathon prototype that detects suspicious requests during phone
            calls with machine learning.
          </p>
          <p>
            Local Whisper Model turns call audio into text. A local Machine
            Learning classifier checks the conversation for suspicious requests
            and triggers a warning.
          </p>
          <p>
            {demo.source_note}{" "}
            <a href={demo.source_url}>Original recording and context</a>.
          </p>
          <a href="https://github.com/ZellerhoffBen/swissscam">
            View project on GitHub <span aria-hidden="true">↗</span>
          </a>
        </div>
      </header>
      <section className="workspace" aria-label="Call analysis workspace">
        <div className="call-panel">
          <div className="phone-frame">
            <span className="phone-side phone-side-left-one" />
            <span className="phone-side phone-side-left-two" />
            <span className="phone-side phone-side-right" />
            <div className="phone-screen">
              <div className="dynamic-island" />
              {phoneState === "home" && (
                <div className="phone-home">
                  <PhoneStatusBar />
                  <div className="lock-date">Thursday, 24 September</div>
                  <div className="phone-time">9:41</div>
                  <button
                    className="incoming-notification"
                    type="button"
                    onClick={startIncomingCall}
                  >
                    <span className="notification-icon">
                      <Phone />
                    </span>
                    <span>
                      <strong>Start demo</strong>
                      <small>
                        {Math.round(demo.duration_seconds)}-second excerpt ·
                        Sound on
                      </small>
                    </span>
                    <small>Tap</small>
                  </button>
                  <div className="lock-actions">
                    <button disabled aria-label="Flashlight (demo only)">
                      <Flashlight />
                    </button>
                    <button disabled aria-label="Camera (demo only)">
                      <Camera />
                    </button>
                  </div>
                </div>
              )}
              {phoneState === "incoming" && (
                <div className="incoming-call">
                  <PhoneStatusBar />
                  <h2>Unknown caller</h2>
                  <p className="phone-caption">Incoming call</p>
                  <div className="incoming-secondary">
                    <button disabled title="Display only in this demo">
                      <AlarmClock />
                      <small>Remind Me</small>
                    </button>
                    <button disabled title="Display only in this demo">
                      <MessageCircle />
                      <small>Message</small>
                    </button>
                  </div>
                  <div className="call-actions">
                    <button
                      type="button"
                      className="call-action call-decline"
                      onClick={endCall}
                    >
                      <span>
                        <Phone className="hang-up" />
                      </span>
                      <small>Decline</small>
                    </button>
                    <button
                      type="button"
                      className="call-action call-accept"
                      onClick={acceptCall}
                    >
                      <span>
                        <Phone />
                      </span>
                      <small>Accept</small>
                    </button>
                  </div>
                </div>
              )}
              {(phoneState === "active" || phoneState === "ended") && (
                <div className="active-call">
                  <PhoneStatusBar />
                  <h2>Unknown caller</h2>
                  <p className="phone-caption">
                    {phoneState === "ended"
                      ? analysisState === "complete"
                        ? "Demo complete"
                        : "Call ended"
                      : formatTime(elapsed)}
                  </p>
                  {phoneState === "ended" && (
                    <p className="call-duration">{formatTime(elapsed)}</p>
                  )}
                  {showScamWarning && (
                    <div className="phone-scam-warning" role="alert">
                      <AlertTriangle />
                      <div>
                        <strong>Potential scam detected</strong>
                        <small>
                          Do not send money or share personal information.
                        </small>
                        {phoneState === "active" && (
                          <button
                            type="button"
                            className="warning-end-call"
                            onClick={endCall}
                          >
                            <Phone className="hang-up" />
                            End call
                          </button>
                        )}
                        <button
                          type="button"
                          className="warning-dismiss"
                          onClick={() => setShowScamWarning(false)}
                        >
                          Dismiss warning
                        </button>
                      </div>
                    </div>
                  )}
                  {phoneState === "active" ? (
                    <>
                      <div className="call-tools">
                        {[
                          [MicOff, "mute"],
                          [Grid3X3, "keypad"],
                          [Volume2, "audio"],
                          [Plus, "add call"],
                          [Video, "FaceTime"],
                          [CircleUserRound, "contacts"],
                        ].map(([Icon, label]) => (
                          <button
                            key={label}
                            disabled
                            title="Display only in this demo"
                          >
                            <span>
                              <Icon />
                            </span>
                            <small>{label}</small>
                          </button>
                        ))}
                      </div>
                      <button
                        type="button"
                        className="end-call-button"
                        aria-label="End call"
                        onClick={endCall}
                      >
                        <Phone className="hang-up" />
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="new-call-button"
                      onClick={startIncomingCall}
                    >
                      <Phone />
                      Replay demo
                    </button>
                  )}
                </div>
              )}
              <div className="home-indicator" />
            </div>
          </div>
          <audio
            className="hidden-audio"
            ref={audioRef}
            src={demo.audio}
            preload="metadata"
            onEnded={() => setPhoneState("ended")}
            aria-label="Prerecorded demo call"
          />
        </div>
        <div className="insights-panel">
          <section
            className="transcript-card"
            aria-labelledby="transcript-title"
          >
            <div className="card-header">
              <h2 id="transcript-title">Transcript</h2>
              <span className={`analysis-state ${analysisState}`}>
                {
                  {
                    idle: "Standby",
                    processing: "Playing",
                    complete: "Complete",
                    stopped: "Ended",
                    error: "Stopped",
                  }[analysisState]
                }
              </span>
            </div>
            <p className="demo-note">
              <strong>Real call excerpt</strong>
            </p>
            <p className="status" role="status">
              {status}
            </p>
            <div className="transcript-content">
              <div
                className="transcript"
                ref={transcriptRef}
                tabIndex={0}
                aria-label="Call transcript"
                onScroll={(event) => {
                  const box = event.currentTarget;
                  setFollowTranscript(
                    box.scrollHeight - box.scrollTop - box.clientHeight < 24,
                  );
                }}
              >
                {turns.length ? (
                  turns.map((turn, index) => (
                    <div
                      className={`transcript-turn ${turn.speaker.toLowerCase()}`}
                      key={index}
                    >
                      <span className="transcript-speaker">{turn.speaker}</span>
                      <p>{turn.text}</p>
                    </div>
                  ))
                ) : (
                  <p className="transcript-placeholder">
                    Hear a suspicious call and follow its transcript and risk
                    score here.
                  </p>
                )}
              </div>
              {!followTranscript && (
                <button
                  className="transcript-latest"
                  type="button"
                  onClick={() => setFollowTranscript(true)}
                >
                  Jump to latest ↓
                </button>
              )}
            </div>
          </section>
          <CallCheck
            detection={detection}
            history={riskHistory}
            elapsed={elapsed}
            analysisState={analysisState}
          />
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
