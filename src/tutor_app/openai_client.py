from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request


class OpenAIClientError(RuntimeError):
    """Base error for OpenAI client failures."""


class ConfigurationError(OpenAIClientError):
    """Raised when required environment configuration is missing."""


class APIRequestError(OpenAIClientError):
    """Raised when the OpenAI API request fails."""


@dataclass(slots=True)
class OpenAIResponsesClient:
    api_key: str | None
    model: str = "gpt-5.4"
    reasoning_effort: str = "medium"
    timeout_seconds: int = 90
    endpoint: str = "https://api.openai.com/v1/responses"

    @classmethod
    def from_env(cls) -> "OpenAIResponsesClient":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
            reasoning_effort=os.getenv("OPENAI_REASONING_EFFORT", "medium"),
        )

    def create_structured_response(
        self,
        *,
        schema_name: str,
        schema: dict[str, Any],
        input_messages: list[dict[str, Any]],
        instructions: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise ConfigurationError(
                "Missing OPENAI_API_KEY. Set it in your environment before asking a question."
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "input": input_messages,
            "reasoning": {"effort": reasoning_effort or self.reasoning_effort},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }

        if instructions:
            payload["instructions"] = instructions

        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise APIRequestError(
                f"OpenAI API request failed with status {exc.code}: {details}"
            ) from exc
        except error.URLError as exc:
            raise APIRequestError(f"Unable to reach OpenAI API: {exc.reason}") from exc

        raw_text = self._extract_output_text(response_payload)
        if not raw_text:
            raise APIRequestError("OpenAI API returned no text output.")

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            preview = raw_text[:400]
            raise APIRequestError(
                f"Structured output could not be parsed as JSON. Raw output: {preview}"
            ) from exc

    def _extract_output_text(self, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        text_chunks: list[str] = []
        for item in payload.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    text = content.get("text")
                    if isinstance(text, str):
                        text_chunks.append(text)
                    elif isinstance(content.get("value"), str):
                        text_chunks.append(content["value"])
            elif isinstance(item.get("text"), str):
                text_chunks.append(item["text"])

        return "".join(text_chunks).strip()

