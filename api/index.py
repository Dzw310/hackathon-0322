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
from tutor_app.content_filter import ContentFilterError  # noqa: E402
from tutor_app.openai_client import OpenAIClientError  # noqa: E402
from tutor_app.session_store import UpstashSessionStore  # noqa: E402
from tutor_app.tutor_service import TutorService  # noqa: E402

load_local_env(ROOT / ".env")

STATIC_DIR = ROOT / "public"

_service: TutorService | None = None


def _get_service() -> TutorService:
    global _service
    if _service is None:
        try:
            store = UpstashSessionStore.from_env()
        except KeyError:
            from tutor_app.session_store import InMemoryStore
            store = InMemoryStore()
        _service = TutorService(store=store)
    return _service


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/api/leaderboard":
            result = _get_service().get_leaderboard()
            self._send_json(HTTPStatus.OK, {"leaderboard": result})
            return
        if parsed.path == "/dashboard":
            self._serve_file(STATIC_DIR / "dashboard.html")
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()

            if parsed.path == "/api/register":
                result = _get_service().register_user(
                    username=payload.get("username", ""),
                    display_name=payload.get("displayName", ""),
                    age_group=payload.get("ageGroup", "8-10"),
                )
                self._send_json(HTTPStatus.OK, {"user": result})
                return

            if parsed.path == "/api/login":
                result = _get_service().login_user(username=payload.get("username", ""))
                self._send_json(HTTPStatus.OK, {"user": result})
                return

            if parsed.path == "/api/session":
                result = _get_service().create_session(
                    question=payload.get("question", ""),
                    user_id=payload.get("userId"),
                    age_group=payload.get("ageGroup", "8-10"),
                )
                self._send_json(HTTPStatus.OK, result)
                return

            if parsed.path == "/api/session/answer":
                result = _get_service().submit_answer(
                    payload.get("sessionId", ""),
                    payload.get("answer", ""),
                )
                self._send_json(HTTPStatus.OK, result)
                return

            if parsed.path == "/api/user/stats":
                result = _get_service().get_user_stats(payload.get("userId", ""))
                self._send_json(HTTPStatus.OK, result)
                return

            if parsed.path == "/api/user/summary":
                result = _get_service().generate_learning_summary(payload.get("userId", ""))
                self._send_json(HTTPStatus.OK, result)
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        except ContentFilterError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "blocked": True})
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except KeyError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except OpenAIClientError as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body is not valid JSON."})
        except Exception as exc:  # noqa: BLE001
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _serve_file(self, file_path: Path) -> None:
        import mimetypes
        if not file_path.exists() or not file_path.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        content_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
