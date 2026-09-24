"""
Minimal REDCap API client using only the Python standard library.

This module is intentionally small and script-friendly:
- No external dependencies.
- No automatic network calls unless invoked by a script.
"""

from __future__ import annotations

import json
import mimetypes
import os
import uuid
import urllib.parse
import urllib.request
import urllib.error

# Keep the kiosk responsive if REDCap is slow or unreachable.
DEFAULT_TIMEOUT = 20


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
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
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


def _post_multipart(api_url: str, fields: dict, file_field: str, file_path: str) -> str:
    boundary = "----TubricBoundary" + uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode("utf-8")
    ctype = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    with open(file_path, "rb") as f:
        content = f.read()
    body += (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
        f"filename=\"{os.path.basename(file_path)}\"\r\nContent-Type: {ctype}\r\n\r\n"
    ).encode("utf-8")
    body += content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(api_url, data=bytes(body))
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RedcapApiError(f"HTTP {exc.code}: {body_text}") from exc
    except urllib.error.URLError as exc:
        raise RedcapApiError(f"URL error: {exc.reason}") from exc


def import_file(api_url: str, token: str, record: str, field: str, file_path: str,
                *, event: str = "", repeat_instance: str = "") -> str:
    """Upload a file into a REDCap 'file' (or signature) field for one record."""
    fields = {
        "token": token,
        "content": "file",
        "action": "import",
        "record": record,
        "field": field,
        "returnFormat": "json",
    }
    if event:
        fields["event"] = event
    if repeat_instance:
        fields["repeat_instance"] = repeat_instance
    return _post_multipart(api_url, fields, "file", file_path)


def export_records(
    api_url: str,
    token: str,
    *,
    fields: list[str] | None = None,
    filter_logic: str | None = None,
    format: str = "json",
    export_repeating: bool = True,
) -> str:
    payload: dict[str, str] = {
        "token": token,
        "content": "record",
        "format": format,
        "type": "flat",
        "rawOrLabel": "raw",
        "returnFormat": "json",
        "exportRepeatingInstruments": "true" if export_repeating else "false",
    }
    if fields:
        payload["fields"] = ",".join(fields)
    if filter_logic:
        payload["filterLogic"] = filter_logic
    return _post_form(api_url, payload)


def export_report(
    api_url: str,
    token: str,
    report_id: str,
    *,
    format: str = "json",
    export_repeating: bool = True,
) -> str:
    payload: dict[str, str] = {
        "token": token,
        "content": "report",
        "format": format,
        "report_id": str(report_id),
        "returnFormat": "json",
        "exportRepeatingInstruments": "true" if export_repeating else "false",
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
