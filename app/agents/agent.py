"""The ERP agent: plan, pick tools, execute, then reason over the results.

The flow per request is the classic agent loop, driven manually so we can capture
what happened and report it back:

    user message
        │
        ▼
    identify intent ──▶ select ERP tool(s) ──▶ fetch data ──▶ generate response

Gemini decides which tools to call via native function calling. We run each call
against the registry, hand the result back, and let the model compose the final
answer — looping until it stops asking for tools or we hit the step cap.
"""

import json
import logging
from dataclasses import dataclass, field

import google.generativeai as genai

from app.config import get_settings
from app.services import erp, llm
from app.tools import registry

log = logging.getLogger("app.agent")


SYSTEM_TEMPLATE = """You are the School ERP Assistant. You help a {role} interact \
with the school ERP in plain language.

Context for this conversation:
- Today's date is {today} ({weekday}).
- You are answering about {name}, class {klass} (student id on file).

How to work:
- Decide the user's intent, then call the ERP tool(s) that answer it. Never invent
  numbers — every fact must come from a tool result.
- A single request may need several tools (e.g. "my attendance, maths marks and any
  pending fees"). Call all of them, then combine the answer.
- If a tool reports nothing was found, say so plainly instead of guessing.
- If the request is outside school ERP topics (attendance, marks, fees, homework,
  timetable), briefly say what you can help with.
- Keep answers short, direct and friendly. Lead with the number or the answer."""


@dataclass
class AgentResult:
    intent: str
    plan: list[str]
    tools_used: list[str]
    response: str
    status: str
    data: dict = field(default_factory=dict)


def _system_prompt(student: dict, role: str) -> str:
    return SYSTEM_TEMPLATE.format(
        role=role,
        today=erp.today().isoformat(),
        weekday=erp.today().strftime("%A"),
        name=student["name"],
        klass=student["class"],
    )


def _to_history(turns: list[dict]) -> list[dict]:
    """Replay prior turns so follow-ups like 'which is highest?' have context."""
    history = []
    for t in turns:
        history.append({"role": "user", "parts": [t["message"]]})
        history.append({"role": "model", "parts": [t["response"]]})
    return history


def _function_calls(response):
    try:
        parts = response.candidates[0].content.parts
    except (IndexError, AttributeError):
        return []
    return [p.function_call for p in parts if p.function_call and p.function_call.name]


def _final_text(response) -> str:
    try:
        text = response.text
        if text and text.strip():
            return text.strip()
    except Exception:  # .text raises when the last part is a function_call
        pass
    return "Sorry, I couldn't put together an answer for that one."


def _run_tool(name: str, call_args) -> dict:
    args = {key: call_args[key] for key in call_args}
    fn = registry.DISPATCH[name]
    try:
        return fn(**args)
    except TypeError:
        # model passed an unexpected/empty arg — fall back to a no-arg call
        return fn()


def _intent(tools_used: list[str]) -> str:
    intents = []
    for name in tools_used:
        label = registry.INTENT_BY_TOOL.get(name, "Unknown")
        if label not in intents:
            intents.append(label)
    if not intents:
        return "General"
    if len(intents) == 1:
        return intents[0]
    return "Multiple"


def _status(tools_used: list[str], results: dict) -> str:
    if not tools_used:
        return "OK"
    if len(set(tools_used)) > 1:
        return "OK"
    first = results.get(tools_used[0], {})
    if first.get("found") is False:
        return "Not Found"
    return first.get("status", "OK")


def _plan(intent: str, tools_used: list[str]) -> list[str]:
    if not tools_used:
        return [
            "Understand the request",
            "Identify intent: General",
            "No ERP tool matched — respond with guidance",
        ]
    return [
        "Understand the request",
        f"Identify intent: {intent}",
        f"Select ERP tool(s): {', '.join(tools_used)}",
        "Fetch data from the ERP",
        "Generate the response",
    ]


def run(message: str, student_id: str, role: str, prior_turns: list[dict]) -> AgentResult:
    student = erp.get_student(student_id)  # raises RecordNotFound for a bad id
    token = registry.subject_student.set(student_id)
    try:
        model = llm.build_model(_system_prompt(student, role), registry.TOOLS)
        chat = model.start_chat(history=_to_history(prior_turns))

        tools_used: list[str] = []
        results: dict = {}

        response = _send(chat, message)
        for _ in range(get_settings().max_agent_steps):
            calls = _function_calls(response)
            if not calls:
                break

            reply_parts = []
            for call in calls:
                result = _run_tool(call.name, call.args)
                tools_used.append(call.name)
                results[call.name] = result
                log.info("tool %s -> found=%s", call.name, result.get("found"))
                reply_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=call.name,
                            response={"result": json.loads(json.dumps(result, default=str))},
                        )
                    )
                )
            response = _send(chat, reply_parts)

        intent = _intent(tools_used)
        return AgentResult(
            intent=intent,
            plan=_plan(intent, tools_used),
            tools_used=tools_used,
            response=_final_text(response),
            status=_status(tools_used, results),
            data=results,
        )
    finally:
        registry.subject_student.reset(token)


def _send(chat, content):
    """Send to Gemini, turning any transport/model failure into an LLMError."""
    from app.utils.exceptions import LLMError

    try:
        return chat.send_message(content)
    except Exception as exc:
        raise LLMError(str(exc)) from exc
