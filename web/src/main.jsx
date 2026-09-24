import { StrictMode, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AlarmClock, BatteryFull, CircleUserRound, Grid3X3, Info, MessageCircle, MicOff, Phone, PhoneCall, PhoneOff, Plus, Signal, Video, Volume2, Wifi } from "lucide-react";
import { ShaderBackground } from "./ShaderBackground";
import "./styles.css";

async function postJson(url, data) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error(`Request failed (${response.status}).`);
  return response.json();
}

function PhoneStatusBar() {
  return <div className="ios-status-bar"><span>9:41</span><div><Signal /><Wifi /><BatteryFull /></div></div>;
}

function App() {
  const [status, setStatus] = useState("Ready to inspect the demo call.");
  const [transcript, setTranscript] = useState("");
  const [detection, setDetection] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [phoneState, setPhoneState] = useState("home");
  const audioRef = useRef(null);

  async function analyzeDemo() {
    setIsAnalyzing(true);
    setTranscript("");
    setDetection(null);
    try {
      setStatus("Transcribing the call…");
      const transcription = await postJson("/api/transcribe", { audio_id: "demo" });
      setTranscript(transcription.text);
      setStatus("Checking the conversation for scam signals…");
      const result = await postJson("/api/analyze", { transcript: transcription.text });
      setDetection(result);
      setStatus("Analysis complete. Review the explanation below.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  function startIncomingCall() {
    setPhoneState("incoming");
    setStatus("Incoming call ready. Accept it to start the demo.");
  }

  function acceptCall() {
    setPhoneState("active");
    setStatus("Call connected. Analyze the conversation when ready.");
    audioRef.current?.play().catch(() => {
      setStatus("Call connected. Press play below to hear the demo recording.");
    });
    analyzeDemo();
  }

  function endCall() {
    setPhoneState("home");
    setStatus("Call ended. Start another demo when ready.");
    setIsAnalyzing(false);
  }

  return (
    <main className="shell">
      <ShaderBackground />
      <div className="page-noise" aria-hidden="true" />
      <header className="topbar">
        <div className="brand"><img className="brand-logo" src="/swissscam-logo.png" alt="Swissscam" /><span>swissscam</span></div>
        
      </header>
      <section className="intro">
        <p className="eyebrow">CALL MONITOR</p>
        <h1>A quieter way to spot a risky call.</h1>
        <p className="lede">Play the prepared call, then see the conversation become a clear, explainable safety signal.</p>
      </section>
      <section className="workspace" aria-label="Call analysis workspace">
        <div className="call-panel">
          <div className="phone-frame">
            <span className="phone-side phone-side-left-one" /><span className="phone-side phone-side-left-two" /><span className="phone-side phone-side-right" />
            <div className="phone-screen">
              <div className="dynamic-island" />
              {phoneState === "home" && <div className="phone-home">
                <PhoneStatusBar /><div className="lock-date">Tuesday, 24 September</div><div className="phone-time">9:41</div>
                <button className="incoming-notification" type="button" onClick={startIncomingCall}><span className="notification-icon"><Phone /></span><span><strong>Phone</strong><small>Tap to start incoming call demo</small></span><small>now</small></button>
                <div className="lock-actions"><button type="button" aria-label="Flashlight">◐</button><button type="button" aria-label="Camera">●</button></div>
              </div>}
              {phoneState === "incoming" && <div className="incoming-call">
                <PhoneStatusBar /><button className="phone-info" type="button" aria-label="Contact information"><Info /></button><p className="phone-eyebrow">mobile</p><h2>Marlene</h2>
                <div className="incoming-secondary"><button type="button"><span><MessageCircle /></span><small>Message</small></button><button type="button"><span><AlarmClock /></span><small>Remind Me</small></button></div>
                <div className="call-actions"><button type="button" className="call-action call-decline" onClick={endCall}><span><PhoneOff /></span><small>Decline</small></button><button type="button" className="call-action call-accept" onClick={acceptCall}><span><PhoneCall /></span><small>Accept</small></button></div>
              </div>}
              {phoneState === "active" && <div className="active-call">
                <PhoneStatusBar /><div className="active-call-head">00:18</div><h2>Marlene</h2><p className="phone-caption">mobile</p>
                <div className="call-tools"><button type="button"><span><MicOff /></span><small>mute</small></button><button type="button"><span><Grid3X3 /></span><small>keypad</small></button><button type="button"><span><Volume2 /></span><small>audio</small></button><button type="button"><span><Plus /></span><small>add call</small></button><button type="button"><span><Video /></span><small>FaceTime</small></button><button type="button"><span><CircleUserRound /></span><small>contacts</small></button></div><button type="button" className="end-call-button" onClick={endCall}><PhoneOff /><span>End call</span></button>
              </div>}
              <div className="home-indicator" />
            </div>
          </div>
          <audio className="hidden-audio" ref={audioRef} src="/audio/demo.wav" aria-label="Prepared demo recording" />
        </div>
        <div className="insights-panel">
          <div className="analysis-header"><p className="eyebrow">BEHIND THE CALL</p><h2>What the model sees.</h2><span className={`analysis-state ${isAnalyzing ? "processing" : detection ? "complete" : "idle"}`}>{isAnalyzing ? "Analyzing" : detection ? "Updated" : "Waiting for call"}</span></div>
          <div className="insight-block"><div className="section-index">01</div><div><p className="label">LIVE TRANSCRIPT</p><p className="transcript">{transcript || "The conversation appears here as soon as the call is accepted."}</p></div></div>
          <div className={`result ${detection?.warning ? "warning" : detection ? "clear" : "empty"}`}>
            <div className="section-index">02</div><div className="result-content"><p className="label">RISK ASSESSMENT</p>
            {detection ? <><h2>{detection.warning ? "Possible scam detected" : "No warning detected"}</h2><p>{detection.reason || "No suspicious signals were found in this conversation."}</p>{detection.signals?.length > 0 && <div className="signals">{detection.signals.map((signal) => <span key={signal}>{signal}</span>)}</div>}</> : <><h2>Waiting for a signal</h2><p>Accept the demo call to start transcription and analysis automatically.</p></>}</div>
          </div>
        </div>
      </section>
      <p className="disclaimer">Demo output only. This prototype is not a real safety assessment.</p>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<StrictMode><App /></StrictMode>);