from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import requests

from onda_provider_sdk import ProviderError, ScrobbleProvider, Track


API_ROOT = "https://api.listenbrainz.org/1"
REQUEST_TIMEOUT = (10, 20)


class Provider(ScrobbleProvider):
    def __init__(self, context: Any) -> None:
        self.context = context

    async def check_configuration(self) -> dict[str, Any]:
        token = self._token(required=False)
        if not token:
            return {
                "success": False,
                "message": "Falta el token de usuario de ListenBrainz.",
            }

        payload = await asyncio.to_thread(
            self._request_json,
            "GET",
            f"{API_ROOT}/validate-token",
            token,
            None,
        )
        if not payload.get("valid"):
            return {"success": False, "message": "El token no es válido."}
        return {
            "success": True,
            "message": "Cuenta de ListenBrainz conectada.",
            "details": {"usuario": str(payload.get("user_name", ""))},
        }

    async def now_playing(self, track: Track, position_ms: int) -> None:
        del position_ms
        await self._submit("playing_now", track)

    async def scrobble(self, track: Track, played_at: str) -> None:
        await self._submit("single", track, listened_at=_unix_timestamp(played_at))

    async def _submit(
        self,
        listen_type: str,
        track: Track,
        *,
        listened_at: int | None = None,
    ) -> None:
        listen: dict[str, Any] = {"track_metadata": _track_metadata(track)}
        if listened_at is not None:
            listen["listened_at"] = listened_at
        body = {"listen_type": listen_type, "payload": [listen]}
        await asyncio.to_thread(
            self._request_json,
            "POST",
            f"{API_ROOT}/submit-listens",
            self._token(),
            body,
        )

    def _token(self, *, required: bool = True) -> str | None:
        value = self.context.get_secret("user_token")
        token = str(value).strip() if value else ""
        if required and not token:
            raise ProviderError(
                "AUTH_REQUIRED", "Configura el token de ListenBrainz."
            )
        return token or None

    @staticmethod
    def _request_json(
        method: str,
        url: str,
        token: str,
        body: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            response = requests.request(
                method,
                url,
                headers={
                    "Authorization": f"Token {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=body,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(
                "NETWORK_ERROR",
                "No se pudo contactar a ListenBrainz.",
                retryable=True,
            ) from exc

        if response.status_code == 401:
            raise ProviderError("AUTH_INVALID", "El token de ListenBrainz no es válido.")
        if response.status_code == 429:
            raise ProviderError(
                "RATE_LIMITED",
                "ListenBrainz limitó temporalmente las solicitudes.",
                retryable=True,
            )
        if response.status_code >= 500:
            raise ProviderError(
                "SERVICE_UNAVAILABLE",
                "ListenBrainz no está disponible temporalmente.",
                retryable=True,
            )
        if response.status_code >= 400:
            raise ProviderError(
                "SUBMISSION_REJECTED",
                f"ListenBrainz rechazó la solicitud ({response.status_code}).",
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(
                "INVALID_RESPONSE", "ListenBrainz devolvió una respuesta inválida."
            ) from exc
        return payload if isinstance(payload, dict) else {}


def _track_metadata(track: Track) -> dict[str, Any]:
    if not track.title.strip() or not track.artists:
        raise ProviderError("INVALID_TRACK", "La canción no tiene título o artista.")

    additional: dict[str, Any] = {
        "media_player": "ONDA",
        "submission_client": "ONDA",
    }
    if track.duration_ms and track.duration_ms > 0:
        additional["duration_ms"] = track.duration_ms
    if track.isrc:
        additional["isrc"] = track.isrc
    recording_mbid = _first_external_ref(
        track, "recording_mbid", "musicbrainz_recording", "musicbrainz"
    )
    if recording_mbid:
        additional["recording_mbid"] = recording_mbid

    metadata: dict[str, Any] = {
        "artist_name": ", ".join(track.artists),
        "track_name": track.title,
        "additional_info": additional,
    }
    if track.album:
        metadata["release_name"] = track.album
    return metadata


def _first_external_ref(track: Track, *keys: str) -> str | None:
    for key in keys:
        value = track.external_refs.get(key)
        if value:
            return value
    return None


def _unix_timestamp(value: str) -> int:
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ProviderError("INVALID_TIMESTAMP", "La fecha de reproducción no es válida.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())
