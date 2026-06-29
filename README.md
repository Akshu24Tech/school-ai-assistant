# School ERP Assistant

An AI assistant that lets **students, teachers and parents** talk to a school ERP in
plain language. Ask "what's my attendance this month?" or "show my maths marks and any
pending fees" and it works out what you mean, calls the right ERP service(s), and
answers from the data — never from a hardcoded script.

Under the hood it's a small **agent**: Gemini plans the request, picks ERP tools using
native function calling, the app runs them against mock data, and the model composes
the final answer. The structured response includes the plan it followed and the tools
it used, so you can see how it reasoned.

## What it does

- **Natural-language chat** — `POST /chat`, one endpoint for every kind of question
- **Real tool calling** — the model chooses from five ERP tools; nothing is keyword-matched
- **Agent planning** — every answer carries the `plan` the agent followed and `tools_used`
- **Conversation memory** — follow-ups like "which subject is highest?" resolve in context
- **Structured responses** — `intent`, `response`, `status`, `plan`, `tools_used`, `data`
- **Multi-step requests** — one message can trigger several tools and a combined answer
- **History API** — `GET /chat/history` reads any session's thread back
- **Audit logging** — every request logged with intent, tools, timing and timestamp
- **Graceful errors** — empty input, unknown student, missing records and model failures

### The five ERP tools

| Tool | Answers questions like |
|------|------------------------|
| Attendance | "What's my attendance percentage?" · "How many classes did I miss?" |
| Marks | "Show my Mathematics marks" · "Which subject is my best?" |
| Fee status | "Have I paid this month?" · "How much is pending?" |
| Homework | "What's due tomorrow?" · "Show pending homework" |
| Timetable | "What's my first class today?" · "Tomorrow's timetable" |

Plus two bonus reports built on top: **academic performance summary** and **parent
progress report**.

## How it works

```
POST /chat
   │
   ▼
identify intent ──▶ select ERP tool(s) ──▶ fetch data ──▶ generate response
   (Gemini)            (function call)       (mock ERP)        (Gemini)
                            │  ▲
                            ▼  │  loop until no more tool calls
                        run tool, return result
```

The agent runs the loop manually (function calling, not auto-mode) so it can record
the plan and the exact tools used, and so a confused model can't spin forever — there's
a hard step cap. Past turns for the session are replayed into the model for context.

More detail, with the request/response flow, is in [docs/architecture.md](docs/architecture.md).

## Project layout

```
app/
  main.py              # app setup, router wiring, health check
  config.py            # settings loaded from .env
  api/chat.py          # POST /chat and GET /chat/history
  agents/agent.py      # the plan → select → execute → respond loop
  services/
    erp.py             # read-only access + arithmetic over the mock data
    llm.py             # Gemini client / model builder
  tools/registry.py    # the ERP tools the model can call + dispatch
  memory/store.py      # conversation memory (SQLite)
  models/schemas.py    # request/response models
  utils/               # logging, exceptions, auth, audit log
mock_data/             # attendance / marks / fees / homework / timetable (+ students)
tests/                 # ERP unit tests + endpoint tests
```

## Setup

Needs Python 3.11+ and a Gemini API key ([aistudio.google.com](https://aistudio.google.com/app/apikey)).

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt

copy .env.example .env          # then paste your GEMINI_API_KEY into .env
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

## Using it

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show my attendance for this month.", "student_id": "S101"}'
```

```json
{
  "intent": "Attendance",
  "response": "Your attendance this month is 87.5% — 7 of 8 classes. You missed Nov 4.",
  "status": "Average",
  "plan": [
    "Understand the request",
    "Identify intent: Attendance",
    "Select ERP tool(s): get_attendance",
    "Fetch data from the ERP",
    "Generate the response"
  ],
  "tools_used": ["get_attendance"],
  "session_id": "0f1c...",
  "execution_ms": 1240
}
```

Pass the returned `session_id` back on the next call to keep context:

```bash
# turn 1
{"message": "Show my marks", "student_id": "S101"}
# turn 2 — resolves "highest" against turn 1, no need to repeat "marks"
{"message": "Which subject is highest?", "student_id": "S101", "session_id": "<from turn 1>"}
```

Try a multi-step one:

```json
{"message": "Show my attendance, my Mathematics marks, and any pending fees.", "student_id": "S101"}
```

### Sample data

Two students ship with the repo: `S101` (Aarav, strong) and `S102` (Diya, some weak
subjects and pending fees). The assistant treats **2025-11-10 (a Monday)** as "today"
so "tomorrow" and "this month" answers stay stable while you demo — change `TODAY` in
`.env` to move the clock.

## Error handling

| Case | Result |
|------|--------|
| Empty message | `400` with a clear error |
| Unknown student id | `404` |
| No records for the query | tool returns "nothing found"; the assistant says so |
| Off-topic question | assistant explains what it can help with |
| Gemini call fails | `502`, logged |
| Anything unexpected | `500`, logged with a stack trace |

## Logging

Two SQLite logs are written under `data/` (plus a rotating file log in `logs/`):

- **audit** — every request: query, intent, tools used, execution time, response, timestamp
- **memory** — every conversation turn, keyed by session

## Tests

```bash
pytest
```

The ERP tests check the arithmetic (percentages, averages, day-relative lookups);
the endpoint tests stub the model so they cover the API contract, memory and error
handling without calling Gemini.

## Notes

- Mock ERP data only (JSON) — no real ERP integration, as specified.
- No hardcoded answers: the model decides which tool(s) to call and every number is
  derived from the data.
- `gemini-2.5-flash` by default; change `GEMINI_MODEL` in `.env`.
