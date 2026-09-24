import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AlarmClock, AlertTriangle, BatteryFull, CircleUserRound, Grid3X3, Info, MessageCircle, MicOff, Phone, PhoneCall, PhoneOff, Plus, Signal, Video, Volume2, Wifi } from "lucide-react";
import { ShaderBackground } from "./ShaderBackground";
import { startCall } from "./callSession";
import { CallCheck } from "./CallCheck";
import "./styles.css";

function PhoneStatusBar() {
  return <div className="ios-status-bar"><span>9:41</span><div><Signal /><Wifi /><BatteryFull /></div></div>;
}

function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

function App() {
  const [status, setStatus] = useState("Choose a recording or start the demo call.");
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
  const stopCallRef = useRef(null);

  useEffect(() => () => stopCallRef.current?.(), []);
  useEffect(() => () => {
    if (audioUrl.startsWith("blob:")) URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  function endCall() {
    stopCallRef.current?.();
    stopCallRef.current = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setPhoneState("home");
    setAnalysisState("idle");
    setTranscript("");
    setDetection(null);
    setRiskHistory([]);
    setElapsed(0);
    setShowScamWarning(false);
    setStatus("Call ended. Start another demo when ready.");
  }

  function handleAudioUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    endCall();
    setAudioFile(file);
    setAudioUrl(URL.createObjectURL(file));
    setStatus(`${file.name} is ready. Start a call to play and analyse it.`);
    event.target.value = "";
  }

  function startIncomingCall() {
    setPhoneState("incoming");
    setStatus("Incoming call ready. Accept it to start the recording.");
  }

  function issueScamWarning() {
    setShowScamWarning(true);
    setStatus("Possible scam detected.");

    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const message = new SpeechSynthesisUtterance("Warning. This call may be a scam. Hang up now. Do not share codes, passwords or bank details.");
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
    setPhoneState("active");
    setAnalysisState("processing");
    setTranscript("");
    setDetection(null);
    setRiskHistory([]);
    setElapsed(0);
    setShowScamWarning(false);
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
        setStatus(hasSpeech ? "Recording and analysis complete." : "No speech recognised in this recording.");
      },
      onError: (message) => {
        setAnalysisState("error");
        setStatus(`Analysis stopped: ${message}`);
      },
    });
  }

  return (
    <main className="shell">
      <ShaderBackground />
      <div className="page-noise" aria-hidden="true" />
      <header className="topbar">
        <div className="brand"><img className="brand-logo" src="/swissscam-logo.png" alt="Swissscam" /><span>swissscam</span></div>
        
      </header>
      <section className="intro">
       
        <h1>Spot suspicious calls early.</h1>
        <p className="lede">Play a recording and follow its transcript and scam warnings.</p>
      </section>
      <section className="workspace" aria-label="Call analysis workspace">
        <div className="call-panel">
          <div className="phone-frame">
            <span className="phone-side phone-side-left-one" /><span className="phone-side phone-side-left-two" /><span className="phone-side phone-side-right" />
            <div className="phone-screen">
              <div className="dynamic-island" />
              {phoneState === "home" && <div className="phone-home">
                <PhoneStatusBar /><div className="lock-date">Thursday, 24 September</div><div className="phone-time">9:41</div>
                <button className="incoming-notification" type="button" onClick={startIncomingCall}><span className="notification-icon"><Phone /></span><span><strong>Phone</strong><small>Tap to start incoming call demo</small></span><small>now</small></button>
                <div className="lock-actions"><button type="button" aria-label="Flashlight">◐</button><button type="button" aria-label="Camera">●</button></div>
              </div>}
              {phoneState === "incoming" && <div className="incoming-call">
                <PhoneStatusBar /><button className="phone-info" type="button" aria-label="Contact information"><Info /></button><p className="phone-eyebrow">mobile</p><h2>Marlene</h2>
                <div className="incoming-secondary"><button type="button"><span><MessageCircle /></span><small>Message</small></button><button type="button"><span><AlarmClock /></span><small>Remind Me</small></button></div>
                <div className="call-actions"><button type="button" className="call-action call-decline" onClick={endCall}><span><PhoneOff /></span><small>Decline</small></button><button type="button" className="call-action call-accept" onClick={acceptCall}><span><PhoneCall /></span><small>Accept</small></button></div>
              </div>}
              {phoneState === "active" && <div className="active-call">
                <PhoneStatusBar /><div className="active-call-head">{formatTime(elapsed)}</div><h2>Marlene</h2><p className="phone-caption">mobile</p>
                {showScamWarning && <div className="phone-scam-warning" role="alert"><AlertTriangle /><div><strong>Potential scam detected</strong><small>Do not share codes or bank details.</small><button type="button" className="warning-end-call" onClick={endCall}><PhoneOff />End call</button><button type="button" className="warning-dismiss" onClick={() => setShowScamWarning(false)}>Dismiss warning</button></div></div>}
                <div className="call-tools"><button type="button"><span><MicOff /></span><small>mute</small></button><button type="button"><span><Grid3X3 /></span><small>keypad</small></button><button type="button"><span><Volume2 /></span><small>audio</small></button><button type="button"><span><Plus /></span><small>add call</small></button><button type="button"><span><Video /></span><small>FaceTime</small></button><button type="button"><span><CircleUserRound /></span><small>contacts</small></button></div><button type="button" className="end-call-button" aria-label="End call" onClick={endCall}><PhoneOff /><span>End call</span></button>
              </div>}
              <div className="home-indicator" />
            </div>
          </div>
          <audio className="hidden-audio" ref={audioRef} src={audioUrl} aria-label="Selected call recording" />
        </div>
        <div className="insights-panel">
          <div className="analysis-header"><div><p className="eyebrow">CALL NOTES</p><h2>Conversation log</h2></div><label className="upload-audio"><input type="file" accept="audio/*" onChange={handleAudioUpload} /><span>＋ Add recording</span></label><span className={`analysis-state ${analysisState}`}>{{ idle: "Standby", processing: "Processing", complete: "Complete", error: "Stopped" }[analysisState]}</span></div>
          <p className="audio-source">Recording: {audioFile?.name || "demo.wav"}</p>
          <p className="status" role="status">{status}</p>
          <div className="insight-block"><div className="section-index">NOW</div><div><p className="label">TRANSCRIPT</p><p className="transcript">{transcript || "The conversation will appear here when the call starts."}</p></div></div>
          <CallCheck detection={detection} history={riskHistory} elapsed={elapsed} analysisState={analysisState} />
        </div>
      </section>
      <p className="disclaimer">Prototype trained on synthetic examples. A call without a warning may still be a scam.</p>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<StrictMode><App /></StrictMode>);
