import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AlarmClock, AlertTriangle, BatteryFull, CircleUserRound, Grid3X3, Info, MessageCircle, MicOff, Phone, PhoneCall, PhoneOff, Plus, Signal, Video, Volume2, Wifi } from "lucide-react";
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

const mockTranscriptSegments = [
  { text: "Hello, this is your bank calling about a security check.", confidence: 18, signals: [] },
  { text: "We noticed unusual activity and need to verify your account immediately.", confidence: 42, signals: ["urgency"] },
  { text: "Please read me the verification code we just sent to your phone.", confidence: 78, signals: ["urgency", "otp_request"] },
  { text: "Do not share this call with anyone or your account could be blocked.", confidence: 94, signals: ["urgency", "otp_request", "isolation"] },
];

function App() {
  const [status, setStatus] = useState("Ready to inspect the demo call.");
  const [transcript, setTranscript] = useState("");
  const [detection, setDetection] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [phoneState, setPhoneState] = useState("home");
  const [mockStep, setMockStep] = useState(0);
  const [confidence, setConfidence] = useState(0);
  const [audioUrl, setAudioUrl] = useState("/audio/demo.wav");
  const [showScamWarning, setShowScamWarning] = useState(false);
  const audioRef = useRef(null);

  useEffect(() => {
    if (phoneState !== "active" || !isAnalyzing) return undefined;
    const timer = window.setInterval(() => {
      setMockStep((step) => {
        const nextStep = Math.min(step + 1, mockTranscriptSegments.length);
        const segment = mockTranscriptSegments[nextStep - 1];
        if (segment) {
          setTranscript(mockTranscriptSegments.slice(0, nextStep).map(({ text }) => text).join(" "));
          setConfidence(segment.confidence);
          setShowScamWarning(segment.confidence >= 70);
          setDetection({
            warning: segment.confidence >= 70,
            signals: segment.signals,
            reason: segment.confidence >= 70 ? "The caller is creating pressure and asking for a one-time verification code." : "The conversation is still being monitored for suspicious patterns.",
          });
        }
        if (nextStep >= mockTranscriptSegments.length) {
          setIsAnalyzing(false);
          setStatus("Live mock analysis complete.");
          window.clearInterval(timer);
        }
        return nextStep;
      });
    }, 2200);
    return () => window.clearInterval(timer);
  }, [isAnalyzing, phoneState]);

  function handleAudioUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setAudioUrl(URL.createObjectURL(file));
    setStatus(`${file.name} is ready for the mock call.`);
  }

  function analyzeDemo() {
    setIsAnalyzing(true);
    setTranscript("");
    setDetection(null);
    setConfidence(0);
    setMockStep(0);
    setShowScamWarning(false);
    setStatus("Listening and transcribing live…");
  }

  function startIncomingCall() {
    setPhoneState("incoming");
    setStatus("Incoming call ready. Accept it to start the demo.");
  }

  function acceptCall() {
    setPhoneState("active");
    setStatus("Call connected. Analyze the conversation when ready.");
    audioRef.current?.play().catch(() => {
      setStatus("Call connected. Audio playback is unavailable in this browser.");
    });
    window.setTimeout(analyzeDemo, 350);
  }

  function endCall() {
    setPhoneState("home");
    setStatus("Call ended. Start another demo when ready.");
    setIsAnalyzing(false);
    setMockStep(0);
    setShowScamWarning(false);
  }

  return (
    <main className="shell">
      <ShaderBackground />
      <div className="page-noise" aria-hidden="true" />
      <header className="topbar">
        <div className="brand"><img className="brand-logo" src="/swissscam-logo.png" alt="Swissscam" /><span>swissscam</span></div>
        
      </header>
      <section className="intro">
       
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
                {showScamWarning && <div className="phone-scam-warning" role="alert"><AlertTriangle /><div><strong>Possible scam</strong><small>Never share verification codes.</small></div><button type="button" onClick={() => setShowScamWarning(false)} aria-label="Dismiss warning">×</button></div>}
                <div className="call-tools"><button type="button"><span><MicOff /></span><small>mute</small></button><button type="button"><span><Grid3X3 /></span><small>keypad</small></button><button type="button"><span><Volume2 /></span><small>audio</small></button><button type="button"><span><Plus /></span><small>add call</small></button><button type="button"><span><Video /></span><small>FaceTime</small></button><button type="button"><span><CircleUserRound /></span><small>contacts</small></button></div><button type="button" className="end-call-button" onClick={endCall}><PhoneOff /><span>End call</span></button>
              </div>}
              <div className="home-indicator" />
            </div>
          </div>
          <audio className="hidden-audio" ref={audioRef} src={audioUrl} aria-label="Selected call recording" />
        </div>
        <div className="insights-panel">
          <div className="analysis-header"><div><p className="eyebrow">CALL NOTES</p><h2>Conversation log</h2></div><label className="upload-audio"><input type="file" accept="audio/*" onChange={handleAudioUpload} /><span>＋ Add recording</span></label><span className={`analysis-state ${isAnalyzing ? "processing" : detection ? "complete" : "idle"}`}>{isAnalyzing ? "Listening" : detection ? "Up to date" : "Standby"}</span></div>
          <div className="insight-block"><div className="section-index">NOW</div><div><p className="label">TRANSCRIPT</p><p className="transcript">{transcript || "The conversation will appear here when the call starts."}</p></div></div>
          <div className={`result ${detection?.warning ? "warning" : detection ? "clear" : "empty"}`}>
            <div className="section-index">STATUS</div><div className="result-content"><p className="label">CALL CHECK</p>
            {detection ? <><div className="risk-line"><h2>{detection.warning ? "Pause before sharing" : "No concern yet"}</h2><strong>{confidence}%</strong></div><div className="confidence-track"><span style={{ width: `${confidence}%` }} /></div><p>{detection.warning ? "This caller is applying pressure and asking for a one-time code." : "The call is being checked as new speech comes in."}</p>{detection.signals?.length > 0 && <div className="signals">{detection.signals.map((signal) => <span key={signal}>{signal.replace("_", " ")}</span>)}</div>}</> : <><h2>No notes yet</h2><p>Accept the call to begin the live transcript and call check.</p></>}</div>
          </div>
        </div>
      </section>
      <p className="disclaimer">Demo output only. This prototype is not a real safety assessment.</p>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<StrictMode><App /></StrictMode>);