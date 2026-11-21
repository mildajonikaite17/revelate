"""Dependency-free transport and durable, secret-safe state for practice runs.

Only the Python standard library is used, so the agent runs on a clean Python
install with nothing to `pip install`. The transport talks only to the fixed
revel8 simulator host and never follows redirects that could carry the key.
"""

from __future__ import annotations

import json
import os
import re
import socket
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable


API_BASE = "https://target-api.apps.01.cf.eu01.stackit.cloud/v1"
_SSL_CONTEXT = None


def build_ssl_context() -> "ssl.SSLContext":
    """Trust the operating-system certificate store, so TLS works behind a corporate
    HTTPS-inspection proxy (whose root CA Windows already trusts but Python does not).
    Falls back to Python's default CAs if the OS store cannot be read. Set the
    REVELATE_INSECURE_SSL environment variable only as a last resort to skip verification.
    """
    if os.environ.get("REVELATE_INSECURE_SSL"):
        return ssl._create_unverified_context()
    context = ssl.create_default_context()
    if sys.platform == "win32":
        try:
            pem = []
            for store in ("ROOT", "CA"):
                try:
                    for cert, encoding, trust in ssl.enum_certificates(store):
                        if encoding == "x509_asn" and trust:
                            pem.append(ssl.DER_cert_to_PEM_cert(cert))
                except (OSError, ssl.SSLError, ValueError):
                    continue
            if pem:
                try:
                    context.load_verify_locations(cadata="".join(pem))
                except (ssl.SSLError, ValueError, OSError):
                    pass
        except Exception:
            pass
    return context


def ssl_context() -> "ssl.SSLContext":
    global _SSL_CONTEXT
    if _SSL_CONTEXT is None:
        _SSL_CONTEXT = build_ssl_context()
    return _SSL_CONTEXT
_PATH = re.compile(r"^/[A-Za-z0-9_/-]+$")
_SESSION_ACTION = re.compile(r"^/sessions/[A-Za-z0-9_-]+/(messages|pages|conversations|events)$")
_CONVERSATION_ACTION = re.compile(r"^/conversations/[A-Za-z0-9_-]+/(turns|end)$")
_RETRY_STATUSES = {429, 502, 503, 504}
Transport = Callable[[str, str, "dict[str, str]", "bytes | None", float], "tuple[int, dict[str, str], bytes]"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class APIError(Exception):
    """A sanitized API failure; an uncertain write must keep its pending record."""

    def __init__(self, message: str, status: int = 0, uncertain: bool = False, retryable: bool = False) -> None:
        self.status = int(status)
        self.uncertain = bool(uncertain)
        self.retryable = bool(retryable)
        self.message = str(message)
        super().__init__(self.message)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _urllib_transport(method: str, url: str, headers: "dict[str, str]", body: "bytes | None", timeout: float) -> "tuple[int, dict[str, str], bytes]":
    opener = urllib.request.build_opener(_NoRedirect(), urllib.request.HTTPSHandler(context=ssl_context()))
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(request, timeout=timeout) as response:
            return int(response.status), dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        try:
            return int(exc.code), dict(exc.headers.items()), exc.read()
        finally:
            exc.close()


class TargetAPI:
    """Talk only to the fixed simulator host, with conservative bounded retries."""

    def __init__(self, team_key: str, transport: "Transport | None" = None, timeout: float = 120,
                 max_attempts: int = 2, sleep: "Callable[[float], None]" = time.sleep) -> None:
        if not isinstance(team_key, str) or not team_key.strip() or "\r" in team_key or "\n" in team_key:
            raise ValueError("A non-empty TEAM KEY without line breaks is required.")
        if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts must be an integer from 1 to 5.")
        if timeout <= 0:
            raise ValueError("timeout must be positive.")
        self._team_key = team_key.strip()
        self.transport = transport if transport is not None else _urllib_transport
        self.timeout = float(timeout)
        self.max_attempts = max_attempts
        self.sleep = sleep

    def _safe(self, message: Any) -> str:
        return str(message).replace(self._team_key, "[KEY HIDDEN]")

    @staticmethod
    def _retry_delay(headers: "dict[str, str]", attempt: int) -> float:
        value = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
        if value is not None:
            try:
                return min(10.0, max(0.0, float(value)))
            except (TypeError, ValueError, OverflowError):
                try:
                    date = parsedate_to_datetime(str(value))
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=timezone.utc)
                    return min(10.0, max(0.0, (date - datetime.now(timezone.utc)).total_seconds()))
                except (TypeError, ValueError, OverflowError):
                    pass
        return min(5.0, float(2 ** (attempt - 1)))

    def request(self, method: str, path: str, payload: Any = None, idempotency_key: "str | None" = None) -> "dict[str, Any] | list[Any]":
        method = str(method).upper()
        if method not in {"GET", "POST"}:
            raise ValueError("Only GET and POST requests are supported.")
        if not isinstance(path, str) or not _PATH.fullmatch(path) or "//" in path:
            raise ValueError("Use a relative simulator API path without a host or query string.")
        if method == "GET" and payload is not None:
            raise ValueError("GET requests cannot include a JSON body.")
        if method == "POST":
            if path.startswith("/sessions"):
                if path == "/sessions":
                    if not isinstance(payload, dict) or payload.get("scenario_id") != "practice":
                        raise ValueError("Only scenario_id='practice' may be created.")
                elif not _SESSION_ACTION.fullmatch(path):
                    raise ValueError("Unsupported session operation.")
            elif path.startswith("/conversations"):
                if not _CONVERSATION_ACTION.fullmatch(path):
                    raise ValueError("Unsupported conversation operation.")
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not idempotency_key or "\r" in idempotency_key or "\n" in idempotency_key:
                raise ValueError("Invalid idempotency key.")
        body = None
        if payload is not None:
            body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        headers = {"Authorization": "Bearer " + self._team_key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        safe_retry = method == "GET" or (method == "POST" and idempotency_key is not None and path != "/sessions")
        url = API_BASE + path
        for attempt in range(1, self.max_attempts + 1):
            response_headers: "dict[str, str]" = {}
            try:
                status, response_headers, data = self.transport(method, url, dict(headers), body, self.timeout)
            except (TimeoutError, socket.timeout, urllib.error.URLError, ConnectionError, OSError) as exc:
                error = APIError(self._safe("Target API connection failed: " + str(exc)), status=0, uncertain=True, retryable=safe_retry)
            except Exception as exc:
                raise APIError(self._safe("Target API transport failed: " + str(exc)), status=0, uncertain=(method == "POST"), retryable=False) from None
            else:
                status = int(status)
                if 200 <= status < 300:
                    if not data or not data.strip():
                        return {}
                    try:
                        result = json.loads(data.decode("utf-8-sig"))
                    except (UnicodeError, ValueError, AttributeError):
                        raise APIError("Target API returned invalid JSON.", status=status, uncertain=(method == "POST")) from None
                    if not isinstance(result, (dict, list)):
                        raise APIError("Target API returned an unexpected JSON value.", status=status, uncertain=(method == "POST"))
                    return result
                detail = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else str(data)
                detail = self._safe(detail)[:2000]
                if 300 <= status < 400:
                    message = "Target API redirect refused (HTTP " + str(status) + ")."
                else:
                    message = "Target API HTTP " + str(status) + (": " + detail if detail else ".")
                error = APIError(message, status=status, uncertain=(method == "POST" and status >= 500),
                                 retryable=(safe_retry and status in _RETRY_STATUSES))
            if error.retryable and attempt < self.max_attempts:
                self.sleep(self._retry_delay(response_headers, attempt))
                continue
            raise error from None
        raise AssertionError("Unreachable request loop.")


class RunStore:
    """Atomic same-directory JSON saves; a configured secret is refused, never written."""

    def __init__(self, path: "str | os.PathLike[str]", secrets: "tuple[str, ...]" = ()) -> None:
        self.path = Path(path)
        self.secrets = tuple(secret for secret in secrets if isinstance(secret, str) and secret)

    def exists(self) -> bool:
        return self.path.is_file()

    def _check_secrets(self, state: Any, serialized: str) -> None:
        def inspect(value: Any) -> bool:
            if isinstance(value, str):
                return any(secret in value for secret in self.secrets)
            if isinstance(value, dict):
                return any(inspect(key) or inspect(item) for key, item in value.items())
            if isinstance(value, (list, tuple)):
                return any(inspect(item) for item in value)
            return False
        if inspect(state) or any(secret in serialized for secret in self.secrets):
            raise ValueError("Refusing state that contains a configured secret. No state was changed.")

    def load(self) -> "dict[str, Any]":
        text = self.path.read_text(encoding="utf-8-sig")
        state = json.loads(text)
        if not isinstance(state, dict):
            raise ValueError("The saved run must be a JSON object.")
        self._check_secrets(state, text)
        return state

    def save(self, state: "dict[str, Any]") -> None:
        if not isinstance(state, dict):
            raise ValueError("Run state must be a dictionary.")
        text = json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        self._check_secrets(state, text)
        data = text.encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="." + self.path.name + ".", suffix=".tmp", dir=str(self.path.parent))
        try:
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            stream = os.fdopen(fd, "wb")
            fd = -1
            with stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
            # Directory fsync is best-effort; opening directories is not portable to Windows.
            try:
                directory = os.open(str(self.path.parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except OSError:
                pass
        finally:
            if fd != -1:
                os.close(fd)
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
