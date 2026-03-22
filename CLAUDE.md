# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Think Step by Step** — An AI-powered interactive tutor for children. Given a question, it calls OpenAI to decompose it into 2–6 guided steps. The child answers one step at a time; wrong answers receive escalating hints rather than the answer. After all steps pass, a full summary is generated.

## Requirements

- Python 3.13+
- No third-party packages — stdlib only

## Setup & Run

```bash
cp .env.example .env   # fill in OPENAI_API_KEY
python run.py          # starts at http://127.0.0.1:8000
```

## Tests

```bash
# All tests
PYTHONPATH=src python -m unittest discover -s tests -v

# Single test
PYTHONPATH=src python -m unittest tests.test_tutor_service.ClassName.test_method -v
```

## Architecture

The server uses Python's built-in `http.server` (no framework). `run.py` prepends `src/` to `sys.path` so all imports resolve as `tutor_app.*`.

**Request flow:**
```
Browser → TutorRequestHandler (server.py)
            → TutorService (tutor_service.py)
                → OpenAIResponsesClient (openai_client.py)
```

**Three LLM calls per session:**
1. `create_session` → `_generate_plan()` — produces a `LearningPlan` with 2–6 `TutorStep` objects
2. `submit_answer` (each attempt) → `_evaluate_step()` — returns `is_correct`, `feedback_to_child`, `next_hint`
3. `submit_answer` (on final correct step) → `_generate_final_feedback()` — returns recap, strengths, tips

All three use `OpenAIResponsesClient.create_structured_response()` with strict JSON schemas defined in `schemas.py`.

**Testability:** `TutorService` depends on the `StructuredLLMClient` protocol, not the concrete `OpenAIResponsesClient`. Inject a mock that implements `create_structured_response()` — no patching needed.

**Sessions** are in-memory (`dict` + `threading.Lock`) and lost on restart.

**`config.py`** parses `.env` using `os.environ.setdefault` — existing env vars are never overwritten.

## Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | — | Required |
| `OPENAI_MODEL` | `gpt-5.4` | Use `gpt-5-mini` for lower cost/latency |
| `OPENAI_REASONING_EFFORT` | `medium` | Passed to Responses API |
| `PORT` | `8000` | HTTP listen port |

## API Endpoints

| Method | Path | Returns |
|---|---|---|
| `POST` | `/api/session` | Session + first step (`status: "ready"`) |
| `POST` | `/api/session/answer` | `step_advanced`, `try_again`, or `completed` |
| `GET` | `/api/health` | `{"status": "ok"}` |
