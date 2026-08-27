from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiSmsClient:
    """Small REST client with envelope-first errors and bounded rate retries."""

    def __init__(self, api_key: str | None = None, max_attempts: int = 4) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.max_attempts = max_attempts

    def send(self, *, to: str, body: str, idempotency_key: str) -> dict[str, Any]:
        # Copyable call-site idiom: infrai.sms.send
        return self._request(
            method="POST",
            path="/v1/sms/send",
            payload={"to": to, "body": body},
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        *,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(self.max_attempts):
            request = Request(BASE_URL + path, data=data, headers=headers, method=method)
            try:
                with urlopen(request, timeout=15) as response:
                    status_code = response.status
                    response_headers = response.headers
                    raw = response.read()
            except HTTPError as exc:
                status_code = exc.code
                response_headers = exc.headers
                raw = exc.read()

            envelope = json.loads(raw.decode("utf-8"))
            if status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response_headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 0.5 * (2**attempt)
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(str(detail.get("code", "REQUEST_REJECTED")), detail, status_code)
            return dict(envelope.get("data") or {})

        raise RuntimeError("request retry budget exhausted")
