# Demo / screen-recording script

A ~17-minute walkthrough covering the five required segments: project overview,
architecture, code walkthrough, API demonstration, and the AI workflow.

## Pre-flight (before recording)

- Terminal: `cd` into the project, activate the venv, confirm `.env` has `GEMINI_API_KEY`.
- Run `uvicorn app.main:app --reload` and wait for "School ERP Assistant ready".
- Open tabs: `http://localhost:8000/docs`, the GitHub repo, the editor.
- Do one dry run with recording off — the API demo queries depend on each other.
- "Today" is pinned to **Mon 2025-11-10**, so "this month" / "tomorrow" stay correct.

---

## 1. Project overview (0:00–2:00)

> An AI School ERP Assistant. Students, teachers and parents ask in plain English —
> "what's my attendance this month", "show my maths marks and any pending fees" — and
> it answers from the school ERP data. It's a real agent, not canned replies: it works
> out the intent, decides which ERP tools to call, runs them, and writes the answer.
> Every number comes from data, nothing is hardcoded. Stack: Python, FastAPI, Gemini
> with native function calling. Mock data is JSON; memory and logs are SQLite.

Show the top of the README.

## 2. Architecture (2:00–5:00)

Open `docs/architecture.md`, show the diagram.

> One endpoint, `POST /chat`. A request: validate, load recent conversation from memory,
> then the agent loop. Gemini identifies intent and returns a function call, we dispatch
> it to the matching ERP tool, the tool reads mock data, we hand the result back. It can
> call several tools in a row. When it stops asking, its final text is the answer. Then
> we save the turn and write an audit log row.

Two design decisions to call out:

> One — I drive the function-calling loop manually, not auto-mode, so I can return the
> plan and the exact tools used, and cap the steps so it can't spin forever. Two — the
> student id is bound server-side, never passed by the model, so it can't read another
> student's record by guessing an id.

## 3. Code walkthrough (5:00–9:30)

About 45s each:

1. `app/tools/registry.py` — the tools the model sees; docstrings are the descriptions
   (prompt engineering). None take a student id.
2. `app/agents/agent.py` — `run()`: system prompt with role + today, chat seeded with
   prior turns (memory), then the loop. Intent, status and plan are derived after.
3. `app/services/erp.py` — the data layer; all arithmetic (percentages, averages,
   pending fees) lives here so tools stay thin.
4. `app/memory/store.py` — conversation memory in SQLite, replayed into the model.
5. `app/utils/audit.py` — per-request log: query, intent, tools, time, response, timestamp.

## 4. API demonstration (9:30–14:30)

At `localhost:8000/docs`, `POST /chat` → "Try it out". Run in order:

1. Single tool + intent
   `{"message":"Show my attendance for this month.","student_id":"S101"}`
   → Attendance, status Average, plan + one tool, 87.5% from the data.

2. Best/worst reasoning
   `{"message":"Which subject has my highest marks?","student_id":"S101"}`
   → different tool chosen automatically.

3. Multi-step (bonus) — emphasise
   `{"message":"Show my attendance, my Mathematics marks, and any pending fees.","student_id":"S101"}`
   → intent Multiple, three tools, one combined answer.

4. Memory — copy `session_id` from #3, then:
   `{"message":"And which of those subjects should I focus on?","student_id":"S101","session_id":"<paste>"}`
   → resolves from context without repeating.

5. Academic summary (bonus) — weaker student
   `{"message":"Summarize my academic performance this semester.","student_id":"S102"}`
   → strong/weak subjects, attendance, overall.

6. Error handling
   `{"message":"   ","student_id":"S101"}` → 400.
   `{"message":"my marks","student_id":"S999"}` → 404.

7. `GET /chat/history` — paste the session_id from #3/#4 → the conversation reads back.

## 5. AI workflow (14:30–16:30)

On the multi-step response, point at `plan` and `data`.

> The model identifies intent, selects ERP tools via function calling, the app runs them
> against mock data, the model reasons over the results and writes the answer. `plan`
> shows the path it took; `data` shows the raw tool output it reasoned from. Nothing is a
> black box, nothing is hardcoded.

## Close (16:30–17:00)

> A real tool-calling agent: conversation memory, structured responses, full logging and
> error handling, plus the multi-step and academic-summary bonuses. On GitHub, runs with
> one uvicorn command. Thanks for watching.

### Tips

- If a Gemini call lags, narrate the architecture while it returns — dead air looks worse.
- The API demo order matters: #4 needs the `session_id` from #3.
