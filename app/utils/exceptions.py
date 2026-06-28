import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.erp import RecordNotFound

log = logging.getLogger("app.errors")


class EmptyRequest(Exception):
    """Raised when the chat message is blank after trimming."""


class LLMError(Exception):
    """Raised when a Gemini call fails for any reason."""


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(EmptyRequest)
    async def handle_empty(request: Request, exc: EmptyRequest):
        log.warning("empty request on %s", request.url.path)
        return JSONResponse(status_code=400, content={"error": "Message cannot be empty."})

    @app.exception_handler(RecordNotFound)
    async def handle_not_found(request: Request, exc: RecordNotFound):
        log.warning("record not found on %s: %s", request.url.path, exc)
        return JSONResponse(status_code=404, content={"error": str(exc)})

    @app.exception_handler(LLMError)
    async def handle_llm_error(request: Request, exc: LLMError):
        log.error("Gemini call failed on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=502,
            content={"error": "The assistant is unavailable right now. Please try again."},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        log.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "Something went wrong on our side."},
        )
