import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AlarmClock, AlertTriangle, BatteryFull, Camera, CircleUserRound, Flashlight, Grid3X3, MessageCircle, MicOff, Phone, Plus, Signal, Video, Volume2, Wifi } from "lucide-react";
import { startCall } from "./callSession";
import { CallCheck } from "./CallCheck";
import demo from "./demo";
import "./styles.css";

function PhoneStatusBar() {
  return <div className="ios-status-bar"><span>9:41</span><div><Signal /><Wifi /><BatteryFull /></div></div>;
}

function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

function App() {
  const [status, setStatus] = useState("Tap the phone notification to start the demo.");
  const [transcript, setTranscript] = useState("");
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

  useEffect(() => () => stopCallRef.current?.(), []);

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
      gain.gain.exponentialRampToValueAtTime(0.16, context.currentTime + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + offset + 0.24);
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
      audio: audioRef.current,
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
      onDone: () => {
        setAnalysisState("complete");
        setStatus("Demo complete. Start a new demo call to replay it.");
      },
      onError: (message) => {
        setAnalysisState("error");
        setPhoneState("ended");
        setShowScamWarning(false);
        setStatus(message);
      },
    });
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand"><img className="brand-logo" src="/swissscam-logo.png" alt="Swissscam" /><span>swissscam</span></div>
      </header>
      <section className="intro">
        <h1>Spot suspicious calls early.</h1>
        <p className="lede">Play a prerecorded call and follow the saved transcript and scam warnings.</p>
      </section>
      <section className="workspace" aria-label="Call analysis workspace">
        <div className="call-panel">
          <div className="phone-frame">
            <span className="phone-side phone-side-left-one" /><span className="phone-side phone-side-left-two" /><span className="phone-side phone-side-right" />
            <div className="phone-screen">
              <div className="dynamic-island" />
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
          <audio className="hidden-audio" ref={audioRef} src={demo.audio} preload="metadata" onEnded={() => setPhoneState("ended")} aria-label="Prerecorded demo call" />
        </div>
        <div className="insights-panel">
          <section className="transcript-card" aria-labelledby="transcript-title">
            <div className="card-header">
              <h2 id="transcript-title">Transcript</h2>
              <span className={`analysis-state ${analysisState}`}>{{ idle: "Standby", processing: "Playing", complete: "Complete", stopped: "Ended", error: "Stopped" }[analysisState]}</span>
            </div>
            <p className="demo-note"><strong>Prerecorded demo</strong> · Saved results, no live analysis.</p>
            <p className="status" role="status">{status}</p>
            <div className="transcript-content">
              <div className="transcript" ref={transcriptRef} tabIndex={0} aria-label="Call transcript" onScroll={(event) => {
                const box = event.currentTarget;
                setFollowTranscript(box.scrollHeight - box.scrollTop - box.clientHeight < 24);
              }}>
                {transcript ? transcript.split(/\n{2,}/).filter(Boolean).map((segment, index) => (
                  <p key={index}>{segment}</p>
                )) : <p>The transcript will appear here.</p>}
              </div>
              {!followTranscript && <button className="transcript-latest" type="button" onClick={() => setFollowTranscript(true)}>Jump to latest ↓</button>}
            </div>
          </section>
          <CallCheck detection={detection} history={riskHistory} elapsed={elapsed} analysisState={analysisState} />
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<StrictMode><App /></StrictMode>);
