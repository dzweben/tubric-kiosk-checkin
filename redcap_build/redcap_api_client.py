"""
Minimal REDCap API client using only the Python standard library.

This module is intentionally small and script-friendly:
- No external dependencies.
- No automatic network calls unless invoked by a script.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import urllib.error


class RedcapApiError(RuntimeError):
    pass


def read_token(token_path: str) -> str:
    with open(token_path, "r", encoding="utf-8") as f:
        token = f.read().strip()
    if not token:
        raise RedcapApiError("API token file is empty.")
    return token


def _post_form(api_url: str, payload: dict) -> str:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(api_url, data=data)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RedcapApiError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RedcapApiError(f"URL error: {exc.reason}") from exc


def import_metadata(api_url: str, token: str, csv_text: str) -> str:
    payload = {
        "token": token,
        "content": "metadata",
        "format": "csv",
        "data": csv_text,
        "returnFormat": "json",
    }
    return _post_form(api_url, payload)


def import_records(api_url: str, token: str, csv_text: str, *, overwrite: str = "normal") -> str:
    payload = {
        "token": token,
        "content": "record",
        "format": "csv",
        "type": "flat",
        "data": csv_text,
        "overwriteBehavior": overwrite,
        "returnFormat": "json",
    }
    return _post_form(api_url, payload)


def summarize_response(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return "(empty response)"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if isinstance(data, dict):
        return json.dumps(data, indent=2)
    return raw
