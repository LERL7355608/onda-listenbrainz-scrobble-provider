from __future__ import annotations

import asyncio
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SDK_ROOT = (
    Path(__file__).resolve().parents[2]
    / "onda"
    / "packages"
    / "onda_runtime_python"
    / "android"
    / "src"
    / "main"
    / "python"
)
sys.path.insert(0, str(SDK_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if "requests" not in sys.modules:
    sys.modules["requests"] = types.SimpleNamespace(
        RequestException=OSError,
        request=None,
    )

from onda_provider_sdk import ProviderRef, Track  # noqa: E402
from provider import Provider  # noqa: E402


class Context:
    def __init__(self, values):
        self.values = values

    def get_secret(self, name):
        return self.values.get(name)


class Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def track():
    return Track(
        source_ref=ProviderRef("dev.test.metadata", "track", "42"),
        title="Song",
        artists=("Artist",),
        album="Album",
        duration_ms=180000,
        isrc="USAAA0000001",
    )


class ProviderTests(unittest.TestCase):
    @patch("provider.requests.request")
    def test_configuration_validates_token_without_exposing_it(self, request):
        request.return_value = Response(
            payload={"valid": True, "user_name": "listener"}
        )
        result = asyncio.run(
            Provider(Context({"user_token": "secret"})).check_configuration()
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["details"]["usuario"], "listener")
        self.assertNotIn("secret", json.dumps(result))

    @patch("provider.requests.request")
    def test_now_playing_omits_timestamp(self, request):
        request.return_value = Response(payload={"status": "ok"})
        asyncio.run(
            Provider(Context({"user_token": "secret"})).now_playing(track(), 0)
        )
        body = request.call_args.kwargs["json"]
        self.assertEqual(body["listen_type"], "playing_now")
        self.assertNotIn("listened_at", body["payload"][0])

    @patch("provider.requests.request")
    def test_scrobble_uses_playback_start_timestamp(self, request):
        request.return_value = Response(payload={"status": "ok"})
        asyncio.run(
            Provider(Context({"user_token": "secret"})).scrobble(
                track(), "2026-09-20T12:00:00Z"
            )
        )
        body = request.call_args.kwargs["json"]
        self.assertEqual(body["listen_type"], "single")
        self.assertEqual(body["payload"][0]["listened_at"], 1789905600)
        metadata = body["payload"][0]["track_metadata"]
        self.assertEqual(metadata["track_name"], "Song")
        self.assertEqual(metadata["additional_info"]["duration_ms"], 180000)


if __name__ == "__main__":
    unittest.main()
