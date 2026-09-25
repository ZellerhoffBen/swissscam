"""Check the API wiring without downloading Whisper during unit tests."""

import json
import unittest
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.api import app
from backend.schemas import TranscriptSegment
from backend.transcription import _transcribe_segments, transcribe_stream

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
        with patch("backend.transcription.transcribe_stream", return_value=iter(SEGMENTS)):
            early = self.client.post("/api/transcribe", json={"audio_id": "demo", "up_to_seconds": 1})
            self.assertEqual(early.json(), {"text": "", "segments": []})
            complete = self.client.post("/api/transcribe", json={"audio_id": "demo"})
        self.assertEqual(complete.json()["segments"][-1]["end_seconds"], 6)
        result = self.client.post("/api/analyze", json={"transcript": complete.json()["text"]})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["warning"])
        self.assertGreaterEqual(result.json()["score"], result.json()["threshold"])
        self.assertEqual(result.json()["signals"], [])

    def test_upload_events_and_temporary_file_cleanup(self) -> None:
        paths = []

        def transcribe_fixture(path: Path) -> Iterator[TranscriptSegment]:
            paths.append(path)
            self.assertEqual(path.read_bytes(), b"audio fixture")
            yield from SEGMENTS

        with patch("backend.api.transcribe_stream", side_effect=transcribe_fixture):
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

        with patch("backend.api.transcribe_stream", side_effect=fail), self.assertLogs("backend.api", level="ERROR"):
            response = self.client.post("/api/transcribe/upload", files={"audio": ("bad.wav", b"invalid")})
        event = json.loads(response.text.removeprefix("data: "))
        self.assertEqual(event["type"], "error")
        self.assertFalse(paths[0].exists())

    def test_invalid_requests_are_rejected(self) -> None:
        self.assertEqual(self.client.post("/api/transcribe", json={"audio_id": "unknown"}).status_code, 404)
        self.assertEqual(self.client.post("/api/analyze", json={"transcript": ""}).status_code, 422)

    def test_word_timed_updates_preserve_text_and_the_final_short_chunk(self) -> None:
        words = [SimpleNamespace(word=text, start=start, end=end) for text, start, end in
                 [("Hello", 0, 1), (" there.", 1, 3.2), (" Read", 3.3, 4), (" the code.", 4, 5)]]
        segment = SimpleNamespace(words=words, text="Hello there. Read the code.", start=0, end=5)
        with patch("backend.transcription._load_model") as model:
            model.return_value.transcribe.return_value = ([segment], None)
            updates = list(transcribe_stream(Path("data/audio/possible_scam.m4a")))
        self.assertEqual([s.text for s in updates], ["Hello there.", "Read the code."])
        self.assertEqual([s.end_seconds for s in updates], [3.2, 5])
        self.assertEqual(updates[1].start_seconds, 3.3)


if __name__ == "__main__":
    unittest.main()
