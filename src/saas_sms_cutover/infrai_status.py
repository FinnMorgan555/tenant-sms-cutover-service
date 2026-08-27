from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .infrai_sms import BASE_URL, InfraiError


class InfraiStatusClient:
    def __init__(self, api_key: str | None = None, max_attempts: int = 4) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.max_attempts = max_attempts

    def status(self, message_id: str) -> dict[str, Any]:
        for attempt in range(self.max_attempts):
            request = Request(
                BASE_URL + f"/v1/sms/status/{message_id}",
                headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
                method="GET",
            )
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
