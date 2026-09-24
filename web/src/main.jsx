import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AlarmClock, AlertTriangle, BatteryFull, CircleUserRound, Grid3X3, Info, MessageCircle, MicOff, Phone, PhoneCall, PhoneOff, Plus, Signal, Video, Volume2, Wifi } from "lucide-react";
import { ShaderBackground } from "./ShaderBackground";
import { startCall } from "./callSession";
import "./styles.css";

function PhoneStatusBar() {
  return <div className="ios-status-bar"><span>9:41</span><div><Signal /><Wifi /><BatteryFull /></div></div>;
}

function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

function App() {
  const [status, setStatus] = useState("Wählen Sie eine Aufnahme oder starten Sie den Demo-Anruf.");
  const [transcript, setTranscript] = useState("");
  const [detection, setDetection] = useState(null);
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
    setElapsed(0);
    setShowScamWarning(false);
    setStatus("Anruf beendet. Sie können die Demo erneut starten.");
  }

  function handleAudioUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    endCall();
    setAudioFile(file);
    setAudioUrl(URL.createObjectURL(file));
    setStatus(`${file.name} ist bereit. Starten Sie den Anruf, um die Aufnahme zu analysieren.`);
    event.target.value = "";
  }

  function startIncomingCall() {
    setPhoneState("incoming");
    setStatus("Eingehender Anruf. Nehmen Sie ihn an, um die Aufnahme zu starten.");
  }

  function issueScamWarning() {
    audioRef.current?.pause();
    setShowScamWarning(true);
    setStatus("Möglicher Betrug erkannt. Der Anruf wurde pausiert.");

    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const message = new SpeechSynthesisUtterance("Achtung. Dieser Anruf könnte Betrug sein. Legen Sie jetzt auf. Teilen Sie keine Codes, Passwörter oder Bankdaten.");
      message.lang = "de-CH";
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
    setElapsed(0);
    setShowScamWarning(false);
    setStatus("Anruf läuft. Die Transkription kann dem Ton leicht verzögert folgen.");
    let warned = false;
    stopCallRef.current = startCall({
      audio: audioRef.current,
      file: audioFile,
      onTime: setElapsed,
      onTranscript: setTranscript,
      onDetection: (result) => {
        setDetection(result);
        // Dismissing a warning keeps analysis running without repeating the popup.
        if (result.warning && !warned) {
          warned = true;
          issueScamWarning();
        }
      },
      onDone: (hasSpeech) => {
        setAnalysisState("complete");
        setStatus(hasSpeech ? "Aufnahme und Analyse abgeschlossen." : "In dieser Aufnahme wurde keine Sprache erkannt.");
      },
      onError: (message) => {
        setAnalysisState("error");
        setStatus(`Analyse gestoppt: ${message}`);
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
       
        <h1>Verdächtige Anrufe frühzeitig erkennen.</h1>
        <p className="lede">Spielen Sie eine Aufnahme ab und verfolgen Sie Transkript und Betrugswarnungen in Echtzeit.</p>
      </section>
      <section className="workspace" aria-label="Call analysis workspace">
        <div className="call-panel">
          <div className="phone-frame">
            <span className="phone-side phone-side-left-one" /><span className="phone-side phone-side-left-two" /><span className="phone-side phone-side-right" />
            <div className="phone-screen">
              <div className="dynamic-island" />
              {phoneState === "home" && <div className="phone-home">
                <PhoneStatusBar /><div className="lock-date">Donnerstag, 24. September</div><div className="phone-time">9:41</div>
                <button className="incoming-notification" type="button" onClick={startIncomingCall}><span className="notification-icon"><Phone /></span><span><strong>Telefon</strong><small>Tippen, um die Demo zu starten</small></span><small>jetzt</small></button>
                <div className="lock-actions"><button type="button" aria-label="Flashlight">◐</button><button type="button" aria-label="Camera">●</button></div>
              </div>}
              {phoneState === "incoming" && <div className="incoming-call">
                <PhoneStatusBar /><button className="phone-info" type="button" aria-label="Kontaktinformationen"><Info /></button><p className="phone-eyebrow">Mobil</p><h2>Marlene</h2>
                <div className="incoming-secondary"><button type="button"><span><MessageCircle /></span><small>Nachricht</small></button><button type="button"><span><AlarmClock /></span><small>Erinnern</small></button></div>
                <div className="call-actions"><button type="button" className="call-action call-decline" onClick={endCall}><span><PhoneOff /></span><small>Ablehnen</small></button><button type="button" className="call-action call-accept" onClick={acceptCall}><span><PhoneCall /></span><small>Annehmen</small></button></div>
              </div>}
              {phoneState === "active" && <div className="active-call">
                <PhoneStatusBar /><div className="active-call-head">{formatTime(elapsed)}</div><h2>Marlene</h2><p className="phone-caption">Mobil</p>
                {showScamWarning && <div className="phone-scam-warning" role="alert"><AlertTriangle /><div><strong>Achtung: möglicher Betrug</strong><small>Teilen Sie keine Codes oder Bankdaten.</small><button type="button" className="warning-end-call" onClick={endCall}><PhoneOff />Jetzt auflegen</button><button type="button" className="warning-dismiss" onClick={() => setShowScamWarning(false)}>Warnung schließen</button></div></div>}
                <div className="call-tools"><button type="button"><span><MicOff /></span><small>Stumm</small></button><button type="button"><span><Grid3X3 /></span><small>Tastatur</small></button><button type="button"><span><Volume2 /></span><small>Audio</small></button><button type="button"><span><Plus /></span><small>Hinzufügen</small></button><button type="button"><span><Video /></span><small>FaceTime</small></button><button type="button"><span><CircleUserRound /></span><small>Kontakte</small></button></div><button type="button" className="end-call-button" aria-label="Anruf beenden" onClick={endCall}><PhoneOff /><span>Anruf beenden</span></button>
              </div>}
              <div className="home-indicator" />
            </div>
          </div>
          <audio className="hidden-audio" ref={audioRef} src={audioUrl} aria-label="Selected call recording" />
        </div>
        <div className="insights-panel">
          <div className="analysis-header"><div><p className="eyebrow">ANRUFANALYSE</p><h2>Gesprächsprotokoll</h2></div><label className="upload-audio"><input type="file" accept="audio/*" onChange={handleAudioUpload} /><span>＋ Aufnahme wählen</span></label><span className={`analysis-state ${analysisState}`}>{{ idle: "Bereit", processing: "Analyse läuft", complete: "Abgeschlossen", error: "Gestoppt" }[analysisState]}</span></div>
          <p className="audio-source">Aufnahme: {audioFile?.name || "demo.wav"}</p>
          <p className="status" role="status">{status}</p>
          <div className="insight-block"><div className="section-index">LIVE</div><div><p className="label">TRANSKRIPT</p><p className="transcript">{transcript || "Das Gespräch erscheint hier, sobald der Anruf beginnt."}</p></div></div>
          <div className={`result ${detection?.warning ? "warning" : detection ? "clear" : "empty"}`}>
            <div className="section-index">STATUS</div><div className="result-content"><p className="label">ANRUF-CHECK</p>
            {detection ? <><div className="risk-line"><h2>{detection.warning ? "Vorsicht beim Teilen von Daten" : "Bisher keine Warnung"}</h2></div><p>{detection.warning ? "Das Gespräch ähnelt bekannten Betrugsmustern. Legen Sie auf und prüfen Sie den Anrufer über eine offizielle Nummer." : "Bisher wurde kein verdächtiges Muster erkannt. Das bedeutet nicht, dass der Anruf sicher ist."}</p>{detection.signals?.length > 0 && <div className="signals">{detection.signals.map((signal) => <span key={signal}>{signal.replace("_", " ")}</span>)}</div>}</> : <><h2>Noch keine Analyse</h2><p>Nehmen Sie den Anruf an, um Transkript und Prüfung zu starten.</p></>}</div>
          </div>
        </div>
      </section>
      <p className="disclaimer">Demo-Prototyp mit synthetischen Trainingsbeispielen. Keine Warnung ist keine Sicherheitsgarantie.</p>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<StrictMode><App /></StrictMode>);
