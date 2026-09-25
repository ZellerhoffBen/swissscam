import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlarmClock,
  AlertTriangle,
  BatteryFull,
  CircleUserRound,
  Grid3X3,
  Info,
  MessageCircle,
  MicOff,
  Phone,
  PhoneCall,
  PhoneOff,
  Plus,
  Signal,
  Video,
  Volume2,
  Wifi,
} from "lucide-react";
import { ShaderBackground } from "./ShaderBackground";
import { AlarmClock, AlertTriangle, BatteryFull, Camera, CircleUserRound, Flashlight, Grid3X3, MessageCircle, MicOff, Phone, Plus, Signal, Video, Volume2, Wifi } from "lucide-react";
import { startCall } from "./callSession";
import { CallCheck } from "./CallCheck";
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
    "Choose a recording or start the demo call.",
  );
  const [transcript, setTranscript] = useState("");
  const [detection, setDetection] = useState(null);
  const [riskHistory, setRiskHistory] = useState([]);
  const [analysisState, setAnalysisState] = useState("idle");
  const [phoneState, setPhoneState] = useState("home");
  const [elapsed, setElapsed] = useState(0);
  const [audioFile, setAudioFile] = useState(null);
  const [audioUrl, setAudioUrl] = useState("/audio/demo.wav");
  const [showScamWarning, setShowScamWarning] = useState(false);
  const audioRef = useRef(null);
  const transcriptRef = useRef(null);
  const [followTranscript, setFollowTranscript] = useState(true);
  const stopCallRef = useRef(null);

  useEffect(() => () => stopCallRef.current?.(), []);
  useEffect(
    () => () => {
      if (audioUrl.startsWith("blob:")) URL.revokeObjectURL(audioUrl);
    },
    [audioUrl],
  );

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
    setAnalysisState((state) => state === "processing" ? "stopped" : state);
    setShowScamWarning(false);
    setStatus(phoneState === "incoming" ? "Call declined." : "Call ended. Your analysis is kept below.");
  }

  function resetAnalysis() {
    setAnalysisState("idle");
    setTranscript("");
    setDetection(null);
    setRiskHistory([]);
    setElapsed(0);
    setShowScamWarning(false);
    setFollowTranscript(true);
  }

  function handleAudioUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    endCall();
    resetAnalysis();
    setPhoneState("home");
    setAudioFile(file);
    setAudioUrl(URL.createObjectURL(file));
    setStatus(`${file.name} is ready. Start a call to play and analyse it.`);
    event.target.value = "";
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
        "Achtung. Dieser Anruf könnte Betrug sein. Legen Sie jetzt auf. Teilen Sie keine Codes, Passwörter oder Bankdaten.",
      );
      message.lang = "de-CH";
      const message = new SpeechSynthesisUtterance("Warning. This call may be a scam. Hang up now. Do not send money or share personal information.");
      message.lang = "en-GB";
      message.rate = 0.85;
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
    setTranscript("");
    setDetection(null);
    setElapsed(0);
    setShowScamWarning(false);
    setStatus(
      "Playing and transcribing locally. Transcription may lag behind the audio.",
    );
    setStatus("Playing and transcribing locally. Transcription may lag behind the audio.");
    let warned = false;
    stopCallRef.current = startCall({
      audio: audioRef.current,
      file: audioFile,
      onTime: setElapsed,
      onTranscript: setTranscript,
      onDetection: (result, seconds) => {
        setDetection(result);
        setRiskHistory((history) => [...history, { seconds, score: result.score }]);
        // Dismissing a warning keeps analysis running without repeating the popup.
        if (result.warning && !warned) {
          warned = true;
          issueScamWarning();
        }
      },
      onDone: (hasSpeech) => {
        setAnalysisState("complete");
        setStatus(
          hasSpeech
            ? "Recording and analysis complete."
            : "No speech recognised in this recording.",
        );
      },
      onError: (message) => {
        setAnalysisState("error");
        setPhoneState("ended");
        setShowScamWarning(false);
        setStatus(`Analysis stopped: ${message}`);
      },
    });
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <img
            className="brand-logo"
            src="/swissscam-logo.png"
            alt="Swissscam"
          />
          <span>swissscam</span>
        </div>
      </header>
      <section className="intro">
        <h1>A quieter way to spot a risky call.</h1>
        <p className="lede">
          Play a recording and follow its transcript and scam warnings.
        </p>
        <div className="brand"><img className="brand-logo" src="/swissscam-logo.png" alt="Swissscam" /><span>swissscam</span></div>
      </header>
      <section className="intro">
        <h1>Spot suspicious calls early.</h1>
        <p className="lede">Play a recording and follow its transcript and scam warnings.</p>
      </section>
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
                  <div className="lock-date">Tuesday, 24 September</div>
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
                      <strong>Phone</strong>
                      <small>Tap to start incoming call demo</small>
                    </span>
                    <small>now</small>
                  </button>
                  <div className="lock-actions">
                    <button type="button" aria-label="Flashlight">
                      ◐
                    </button>
                    <button type="button" aria-label="Camera">
                      ●
                    </button>
                  </div>
                </div>
              )}
              {phoneState === "incoming" && (
                <div className="incoming-call">
                  <PhoneStatusBar />
                  <button
                    className="phone-info"
                    type="button"
                    aria-label="Contact information"
                  >
                    <Info />
                  </button>
                  <p className="phone-eyebrow">mobile</p>
                  <h2>Marlene</h2>
                  <div className="incoming-secondary">
                    <button type="button">
                      <span>
                        <MessageCircle />
                      </span>
                      <small>Message</small>
                    </button>
                    <button type="button">
                      <span>
                        <AlarmClock />
                      </span>
                      <small>Remind Me</small>
                    </button>
                  </div>
                  <div className="call-actions">
                    <button
                      type="button"
                      className="call-action call-decline"
                      onClick={endCall}
                    >
                      <span>
                        <PhoneOff />
                      </span>
                      <small>Decline</small>
                    </button>
                    <button
                      type="button"
                      className="call-action call-accept"
                      onClick={acceptCall}
                    >
                      <span>
                        <PhoneCall />
                      </span>
                      <small>Accept</small>
                    </button>
                  </div>
                </div>
              )}
              {phoneState === "active" && (
                <div className="active-call">
                  <PhoneStatusBar />
                  <div className="active-call-head">{formatTime(elapsed)}</div>
                  <h2>Marlene</h2>
                  <p className="phone-caption">mobile</p>
                  {showScamWarning && (
                    <div className="phone-scam-warning" role="alert">
                      <AlertTriangle />
                      <div>
                        <strong>Achtung: möglicher Betrug</strong>
                        <small>Teilen Sie keine Codes oder Bankdaten.</small>
                        <button
                          type="button"
                          className="warning-end-call"
                          onClick={endCall}
                        >
                          <PhoneOff />
                          Jetzt auflegen
                        </button>
                        <button
                          type="button"
                          className="warning-dismiss"
                          onClick={() => setShowScamWarning(false)}
                        >
                          Warnung schließen
                        </button>
                      </div>
                    </div>
                  )}
                  <div className="call-tools">
                    <button type="button">
                      <span>
                        <MicOff />
                      </span>
                      <small>mute</small>
                    </button>
                    <button type="button">
                      <span>
                        <Grid3X3 />
                      </span>
                      <small>keypad</small>
                    </button>
                    <button type="button">
                      <span>
                        <Volume2 />
                      </span>
                      <small>audio</small>
                    </button>
                    <button type="button">
                      <span>
                        <Plus />
                      </span>
                      <small>add call</small>
                    </button>
                    <button type="button">
                      <span>
                        <Video />
                      </span>
                      <small>FaceTime</small>
                    </button>
                    <button type="button">
                      <span>
                        <CircleUserRound />
                      </span>
                      <small>contacts</small>
                    </button>
                  </div>
                  <button
                    type="button"
                    className="end-call-button"
                    aria-label="End call"
                    onClick={endCall}
                  >
                    <PhoneOff />
                    <span>End call</span>
                  </button>
                </div>
              )}
              <div className="home-indicator" />
            </div>
          </div>
          <audio
            className="hidden-audio"
            ref={audioRef}
            src={audioUrl}
            aria-label="Selected call recording"
          />
        </div>
        <div className="insights-panel">
          <div className="analysis-header">
            <div>
              <p className="eyebrow">CALL NOTES</p>
              <h2>Conversation log</h2>
            </div>
            <label className="upload-audio">
              <input
                type="file"
                accept="audio/*"
                onChange={handleAudioUpload}
              />
              <span>＋ Add recording</span>
            </label>
            <span className={`analysis-state ${analysisState}`}>
              {
                {
                  idle: "Standby",
                  processing: "Processing",
                  complete: "Complete",
                  error: "Stopped",
                }[analysisState]
              }
            </span>
          </div>
          <p className="audio-source">
            Recording: {audioFile?.name || "demo.wav"}
          </p>
          <p className="status" role="status">
            {status}
          </p>
          <div className="insight-block">
            <div className="section-index">NOW</div>
            <div>
              <p className="label">TRANSCRIPT</p>
              <div className="transcript">
                {transcript ? (
                  transcript
                    .split(/\n{2,}/)
                    .filter(Boolean)
                    .map((segment, index) => (
                      <p key={`${segment}-${index}`}>{segment}</p>
                    ))
                ) : (
                  <p>The conversation will appear here when the call starts.</p>
                )}
              </div>
            </div>
          </div>
          <div
            className={`result ${detection?.warning ? "warning" : detection ? "clear" : "empty"}`}
          >
            <div className="section-index">STATUS</div>
            <div className="result-content">
              <p className="label">CALL CHECK</p>
              {detection ? (
                <>
                  <div className="risk-line">
                    <h2>
                      {detection.warning
                        ? "Pause before sharing"
                        : "No warning so far"}
                    </h2>
                  </div>
                  <p>
                    {detection.reason ||
                      "No warning from the model on the transcript so far. This does not guarantee the call is safe."}
                  </p>
                  {detection.signals?.length > 0 && (
                    <div className="signals">
                      {detection.signals.map((signal) => (
                        <span key={signal}>{signal.replace("_", " ")}</span>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <>
                  <h2>No notes yet</h2>
                  <p>
                    Accept the call to begin the live transcript and call check.
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      </section>
      <p className="disclaimer">
        Prototype trained on synthetic examples. A call without a warning may
        still be a scam.
      </p>
              {phoneState === "home" && <div className="phone-home">
                <PhoneStatusBar />
                <div className="lock-date">Thursday, 24 September</div>
                <div className="phone-time">9:41</div>
                <button className="incoming-notification" type="button" onClick={startIncomingCall}>
                  <span className="notification-icon"><Phone /></span>
                  <span><strong>Phone</strong><small>Tap to start a demo call</small></span><small>now</small>
                </button>
                <div className="lock-actions">
                  <button disabled aria-label="Flashlight (demo only)"><Flashlight /></button>
                  <button disabled aria-label="Camera (demo only)"><Camera /></button>
                </div>
              </div>}
              {phoneState === "incoming" && <div className="incoming-call">
                <PhoneStatusBar />
                <h2>Unknown caller</h2>
                <p className="phone-caption">Incoming call</p>
                <div className="incoming-secondary">
                  <button disabled title="Display only in this demo"><AlarmClock /><small>Remind Me</small></button>
                  <button disabled title="Display only in this demo"><MessageCircle /><small>Message</small></button>
                </div>
                <div className="call-actions">
                  <button type="button" className="call-action call-decline" onClick={endCall}><span><Phone className="hang-up" /></span><small>Decline</small></button>
                  <button type="button" className="call-action call-accept" onClick={acceptCall}><span><Phone /></span><small>Accept</small></button>
                </div>
              </div>}
              {(phoneState === "active" || phoneState === "ended") && <div className="active-call">
                <PhoneStatusBar />
                <h2>Unknown caller</h2>
                <p className="phone-caption">{phoneState === "ended" ? "Call ended" : formatTime(elapsed)}</p>
                {phoneState === "ended" && <p className="call-duration">{formatTime(elapsed)}</p>}
                {showScamWarning && <div className="phone-scam-warning" role="alert">
                  <AlertTriangle />
                  <div>
                    <strong>Potential scam detected</strong>
                    <small>Do not send money or share personal information.</small>
                    {phoneState === "active" && <button type="button" className="warning-end-call" onClick={endCall}><Phone className="hang-up" />End call</button>}
                    <button type="button" className="warning-dismiss" onClick={() => setShowScamWarning(false)}>Dismiss warning</button>
                  </div>
                </div>}
                {phoneState === "active" ? <>
                  <div className="call-tools">
                    {[[MicOff, "mute"], [Grid3X3, "keypad"], [Volume2, "audio"], [Plus, "add call"], [Video, "FaceTime"], [CircleUserRound, "contacts"]].map(([Icon, label]) =>
                      <button key={label} disabled title="Display only in this demo"><span><Icon /></span><small>{label}</small></button>
                    )}
                  </div>
                  <button type="button" className="end-call-button" aria-label="End call" onClick={endCall}><Phone className="hang-up" /></button>
                </> : <button type="button" className="new-call-button" onClick={startIncomingCall}><Phone />New demo call</button>}
              </div>}
              <div className="home-indicator" />
            </div>
          </div>
          <audio className="hidden-audio" ref={audioRef} src={audioUrl} onEnded={() => setPhoneState("ended")} aria-label="Selected call recording" />
        </div>
        <div className="insights-panel">
          <section className="transcript-card" aria-labelledby="transcript-title">
            <div className="card-header">
              <h2 id="transcript-title">Transcript</h2>
              <span className={`analysis-state ${analysisState}`}>{{ idle: "Standby", processing: "Processing", complete: "Complete", stopped: "Ended", error: "Stopped" }[analysisState]}</span>
            </div>
            <div className="recording-controls">
              <p className="audio-source" title={audioFile?.name || "demo.wav"}>{audioFile?.name || "demo.wav"}</p>
              <label className="upload-audio">
                <input type="file" accept="audio/*" onChange={handleAudioUpload} />
                <span>＋ Add recording</span>
              </label>
            </div>
            <p className="status" role="status">{status}</p>
            <div className="transcript-content">
              <p className="transcript" ref={transcriptRef} tabIndex={0} aria-label="Call transcript" onScroll={(event) => {
                const box = event.currentTarget;
                setFollowTranscript(box.scrollHeight - box.scrollTop - box.clientHeight < 24);
              }}>{transcript || "The transcript will appear here."}</p>
              {!followTranscript && <button className="transcript-latest" type="button" onClick={() => setFollowTranscript(true)}>Jump to latest ↓</button>}
            </div>
          </section>
          <CallCheck detection={detection} history={riskHistory} elapsed={elapsed} analysisState={analysisState} />
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
