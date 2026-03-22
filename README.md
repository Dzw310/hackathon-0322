# Think Step by Step

An interactive learning prototype for children. After a user asks a question, the system calls the OpenAI API, breaks the problem into multiple smaller steps, and guides the child through them one at a time:

- If the child is correct, the app moves on to the next step.
- If the child is incorrect, the app does not reveal the full answer immediately. It provides more specific hints and encourages the child to keep thinking.
- After all steps are completed, the app returns the full solution, the final answer, and learning feedback.

## Good Use Cases

- Elementary school math, logic, and word problems
- Simple science concept exploration
- Step-by-step guidance for writing or reading comprehension

## Project Structure

```text
hackathon-0322/
├── run.py
├── src/tutor_app/
│   ├── openai_client.py
│   ├── tutor_service.py
│   ├── server.py
│   ├── models.py
│   ├── schemas.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── styles.css
└── tests/
    └── test_tutor_service.py
```

## Core Design

### 1. Step-by-Step Decomposition

The backend first calls the OpenAI Responses API and asks the model to generate a structured learning plan:

- A reframed version of the problem
- An encouraging introduction
- Multiple reasoning steps
- For each step: a goal, a child-facing prompt, evaluation criteria, and a hint ladder
- A final reference answer

### 2. Interactive Step Evaluation

Each time the child submits an intermediate answer, the backend calls the model again to evaluate the current step:

- Whether the answer is correct
- Feedback for the child
- The next hint
- A short explanation

### 3. Final Summary

After all steps are completed, the backend makes one more model call to generate:

- The complete answer
- A recap of each step
- What the child did well
- What the child can improve next time

## Requirements

- Python 3.13+
- OpenAI API key

This project does not require any third-party Python packages for local development. It runs entirely on the Python standard library.

## Configuration

Copy the example environment file and fill it in:

```bash
cp .env.example .env
```

At minimum, set:

```bash
export OPENAI_API_KEY="your_key"
export OPENAI_MODEL="gpt-5.4"
export OPENAI_REASONING_EFFORT="medium"
```

If you care more about cost and speed, you can switch the model to `gpt-5-mini`.

## Run

```bash
python run.py
```

By default, the app starts at:

```text
http://127.0.0.1:8000
```

## API

### `POST /api/session`

Request:

```json
{
  "question": "If 12 candies are shared among 3 friends, how many does each friend get?"
}
```

Purpose: Creates a new step-by-step learning session and returns the first step.

### `POST /api/session/answer`

Request:

```json
{
  "sessionId": "session_id",
  "answer": "12 candies"
}
```

Purpose: Submits the current step answer and returns one of three states: continue, retry, or completed.

## Verification

Run the unit tests with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## OpenAI Integration Notes

This project uses the Responses API with structured outputs so the model can reliably return JSON. According to the official OpenAI documentation, the Responses API is the recommended interface for new projects. As of March 22, 2026, the official model docs recommend starting with `gpt-5.4`; if you care more about cost and latency, `gpt-5-mini` is a reasonable alternative.

References:

- https://developers.openai.com/api/docs/guides/text
- https://developers.openai.com/api/docs/models
