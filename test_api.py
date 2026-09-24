"""Check the API wiring without downloading Whisper during unit tests."""

import json
import unittest
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from schemas import TranscriptSegment
from transcription import _transcribe_segments

SEGMENTS = [
    TranscriptSegment(text="Hello, this is your bank.", start_seconds=0, end_seconds=2),
    TranscriptSegment(text="Move your savings to my safe account and keep this call secret. "
                           "Read the bank login password and verification code to me now.",
                      start_seconds=2, end_seconds=6),
]


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        _transcribe_segments.cache_clear()

    def tearDown(self) -> None:
        self.client.close()
        _transcribe_segments.cache_clear()

    def test_demo_cutoff_and_real_classifier(self) -> None:
        with patch("transcription.transcribe_stream", return_value=iter(SEGMENTS)):
            early = self.client.post("/api/transcribe", json={"audio_id": "demo", "up_to_seconds": 1})
            self.assertEqual(early.json(), {"text": "", "segments": []})
            complete = self.client.post("/api/transcribe", json={"audio_id": "demo"})
        self.assertEqual(complete.json()["segments"][-1]["end_seconds"], 6)
        result = self.client.post("/api/analyze", json={"transcript": complete.json()["text"]})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["warning"])
        self.assertEqual(result.json()["signals"], [])

    def test_upload_events_and_temporary_file_cleanup(self) -> None:
        paths = []

        def transcribe_fixture(path: Path) -> Iterator[TranscriptSegment]:
            paths.append(path)
            self.assertEqual(path.read_bytes(), b"audio fixture")
            yield from SEGMENTS

        with patch("main.transcribe_stream", side_effect=transcribe_fixture):
            response = self.client.post("/api/transcribe/upload", files={"audio": ("call.wav", b"audio fixture")})
        self.assertEqual(response.status_code, 200)
        events = [json.loads(frame.removeprefix("data: ")) for frame in response.text.strip().split("\n\n")]
        self.assertEqual([event["type"] for event in events], ["segment", "segment", "done"])
        self.assertEqual(events[0]["text"], SEGMENTS[0].text)
        self.assertFalse(paths[0].exists())

    def test_upload_failure_is_an_error_event_not_success(self) -> None:
        paths = []

        def fail(path: Path) -> Iterator[TranscriptSegment]:
            paths.append(path)
            raise ValueError("Invalid recording")

        with patch("main.transcribe_stream", side_effect=fail), self.assertLogs("main", level="ERROR"):
            response = self.client.post("/api/transcribe/upload", files={"audio": ("bad.wav", b"invalid")})
        event = json.loads(response.text.removeprefix("data: "))
        self.assertEqual(event["type"], "error")
        self.assertFalse(paths[0].exists())

    def test_invalid_requests_are_rejected(self) -> None:
        self.assertEqual(self.client.post("/api/transcribe", json={"audio_id": "unknown"}).status_code, 404)
        self.assertEqual(self.client.post("/api/analyze", json={"transcript": ""}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
