from schemas import DetectionResult


def detect(transcript: str) -> DetectionResult:
    """Mock rule for wiring the app together"""
    warning = "bank" in transcript.lower()
    return DetectionResult(
        warning=warning,
        signals=["mock_bank_keyword"] if warning else [],
        reason="Mock: the transcript contains 'bank'." if warning else "",
    )
