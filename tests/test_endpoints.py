"""Endpoint tests. The agent is stubbed so these don't hit Gemini — they cover the
API contract, memory wiring and error handling."""

from fastapi.testclient import TestClient

from app import main
from app.agents import agent
from app.agents.agent import AgentResult

client = TestClient(main.app)


def _stub_result(text="Your attendance is 93.1%.", intent="Attendance",
                 tools=("get_attendance",), status="Good"):
    return AgentResult(
        intent=intent,
        plan=["Understand the request", f"Identify intent: {intent}"],
        tools_used=list(tools),
        response=text,
        status=status,
        data={},
    )


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_chat_returns_structured_response(monkeypatch):
    monkeypatch.setattr(agent, "run", lambda *a, **k: _stub_result())

    r = client.post("/chat", json={"message": "Show my attendance", "student_id": "S101"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "Attendance"
    assert body["status"] == "Good"
    assert body["tools_used"] == ["get_attendance"]
    assert body["session_id"]  # a session id always comes back
    assert "execution_ms" in body


def test_empty_message_is_rejected(monkeypatch):
    monkeypatch.setattr(agent, "run", lambda *a, **k: _stub_result())
    r = client.post("/chat", json={"message": "   ", "student_id": "S101"})
    assert r.status_code == 400


def test_invalid_student_is_404(monkeypatch):
    # let the real agent.run boot so it raises RecordNotFound on the bad id
    r = client.post("/chat", json={"message": "my marks", "student_id": "S999"})
    assert r.status_code == 404


def test_history_round_trips(monkeypatch):
    monkeypatch.setattr(agent, "run", lambda *a, **k: _stub_result(text="first answer"))
    first = client.post("/chat", json={"message": "show marks", "student_id": "S101"}).json()
    session_id = first["session_id"]

    monkeypatch.setattr(agent, "run",
                        lambda *a, **k: _stub_result(text="second answer", intent="Marks"))
    client.post("/chat", json={"message": "highest?", "student_id": "S101",
                               "session_id": session_id})

    hist = client.get("/chat/history", params={"session_id": session_id}).json()
    assert hist["session_id"] == session_id
    assert [t["message"] for t in hist["turns"]] == ["show marks", "highest?"]
