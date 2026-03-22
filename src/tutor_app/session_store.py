from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict
from typing import Any, Protocol
from urllib import error, request

from tutor_app.models import AttemptRecord, LearningPlan, TutorSession, TutorStep


class SessionStore(Protocol):
    def get(self, session_id: str) -> TutorSession | None: ...
    def set(self, session: TutorSession) -> None: ...


class InMemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[str, TutorSession] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> TutorSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def set(self, session: TutorSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session


def _session_to_json(session: TutorSession) -> str:
    return json.dumps(asdict(session), ensure_ascii=False)


def _session_from_dict(data: dict[str, Any]) -> TutorSession:
    plan_data = data["plan"]
    steps = [TutorStep(**s) for s in plan_data["steps"]]
    plan = LearningPlan(**{**plan_data, "steps": steps})
    history = [AttemptRecord(**r) for r in data["history"]]
    return TutorSession(
        session_id=data["session_id"],
        question=data["question"],
        plan=plan,
        current_step_index=data["current_step_index"],
        history=history,
        is_complete=data["is_complete"],
        final_feedback=data.get("final_feedback"),
    )


class UpstashSessionStore:
    SESSION_TTL = 3600  # 1 hour

    def __init__(self, url: str, token: str) -> None:
        self._url = url.rstrip("/")
        self._token = token

    @classmethod
    def from_env(cls) -> "UpstashSessionStore":
        return cls(
            url=os.environ["KV_REST_API_URL"],
            token=os.environ["KV_REST_API_TOKEN"],
        )

    def get(self, session_id: str) -> TutorSession | None:
        result = self._cmd("GET", f"session:{session_id}")
        if not result:
            return None
        return _session_from_dict(json.loads(result))

    def set(self, session: TutorSession) -> None:
        self._cmd("SET", f"session:{session.session_id}", _session_to_json(session), "EX", self.SESSION_TTL)

    def _cmd(self, *args: Any) -> Any:
        body = json.dumps(list(args)).encode("utf-8")
        req = request.Request(
            self._url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())["result"]
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Upstash error {exc.code}: {details}") from exc
