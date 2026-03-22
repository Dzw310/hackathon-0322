from __future__ import annotations

import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tutor_app.config import load_local_env  # noqa: E402
from tutor_app.openai_client import OpenAIClientError  # noqa: E402
from tutor_app.session_store import UpstashSessionStore  # noqa: E402
from tutor_app.tutor_service import TutorService  # noqa: E402

load_local_env(ROOT / ".env")

_service = TutorService(store=UpstashSessionStore.from_env())


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/session":
                result = _service.create_session(payload.get("question", ""))
                self._send_json(HTTPStatus.OK, result)
                return
            if parsed.path == "/api/session/answer":
                result = _service.submit_answer(
                    payload.get("sessionId", ""),
                    payload.get("answer", ""),
                )
                self._send_json(HTTPStatus.OK, result)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except KeyError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except OpenAIClientError as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "请求体不是合法 JSON。"})
        except Exception as exc:  # noqa: BLE001
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
