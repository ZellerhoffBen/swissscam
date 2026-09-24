function timeLabel(seconds) {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

export function CallCheck({ detection, history, elapsed, analysisState }) {
  const score = detection?.score;
  const threshold = detection?.threshold ?? 0.95;
  const warning = detection?.warning ?? false;
  const title = detection
    ? warning ? "Potential scam detected" : "No warning so far"
    : { idle: "Ready to analyse", processing: "Listening for speech…",
        complete: "No speech recognised", error: "Analysis stopped" }[analysisState];
  const thresholdLabel = Math.round(threshold * 100);
  // The chart starts at the first measurement, never at an invented zero score.
  const endTime = Math.max(elapsed, history.at(-1)?.seconds ?? 0, 1);
  const x = (seconds) => 6 + (seconds / endTime) * 388;
  const y = (value) => 6 + (1 - value) * 88;
  const path = history.map((point, index) => index === 0
    ? `M ${x(point.seconds)} ${y(point.score)}`
    : `H ${x(point.seconds)} V ${y(point.score)}`).join(" ");

  return (
    <div className={`result ${warning ? "warning" : detection ? "clear" : "empty"}`}>
      <div className="section-index">STATUS</div>
      <div className="result-content">
        <p className="label">CALL CHECK</p>
        <div className="risk-readout">
          <h2>{title}</h2>
          <div className="risk-value"><span>Risk score</span><strong>
            {score == null ? "—" : Math.floor(score * 100)}<small> / 100</small>
          </strong></div>
        </div>
        <div className="risk-meter" role={score == null ? undefined : "meter"}
          aria-label="Model risk score" aria-valuemin={0} aria-valuemax={100}
          aria-valuenow={score == null ? undefined : Math.floor(score * 100)}>
          <span className="risk-meter-fill" style={{ width: `${(score ?? 0) * 100}%` }} />
          <span className="risk-meter-threshold" style={{ left: `${threshold * 100}%` }} />
        </div>
        <div className="risk-scale"><span>0</span><span>Warning threshold: {thresholdLabel}</span><span>100</span></div>

        <div className="risk-history-heading"><span>Call history</span><span>{history.length} {history.length === 1 ? "check" : "checks"}</span></div>
        <div className="risk-chart">
          <svg viewBox="0 0 400 100" preserveAspectRatio="none" role="img"
            aria-label={`Risk score history: ${history.length} checks. Warning threshold ${thresholdLabel}.`}>
            <line className="risk-chart-threshold" x1="6" x2="394" y1={y(threshold)} y2={y(threshold)} />
            {history.length > 0 && <path className="risk-chart-line" d={path} />}
            {history.map((point, index) => <circle key={index} cx={x(point.seconds)} cy={y(point.score)}
              r="3" className={point.score >= threshold ? "risk-point warning" : "risk-point"}>
              <title>{timeLabel(point.seconds)} — risk score {(point.score * 100).toFixed(1)}</title>
            </circle>)}
          </svg>
          {!history.length && <span className="risk-chart-empty">{analysisState === "processing"
            ? "Waiting for the first transcript segment" : "Scores appear as speech is analysed"}</span>}
        </div>
        <div className="risk-scale"><span>0:00</span><span>{timeLabel(elapsed)}</span></div>
        {detection && <div className="risk-reason">
          <h3>{warning ? "Scam reason" : "Assessment"}</h3>
          <p>{detection.reason || "No warning on the text analysed so far. The call may still be a scam."}</p>
        </div>}
      </div>
    </div>
  );
}
