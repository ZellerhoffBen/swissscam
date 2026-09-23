from pathlib import Path


def transcribe(audio_path: Path) -> str:
    """Mock: replace the fixed text with local speech recognition here."""
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)
    return "Hello, this is your bank. Please share your verification code."
