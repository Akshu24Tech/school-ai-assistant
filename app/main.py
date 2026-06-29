import logging

from fastapi import FastAPI

from app.api import chat
from app.config import get_settings
from app.utils.exceptions import register_exception_handlers
from app.utils.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("app")

app = FastAPI(
    title=settings.app_name,
    description=(
        "An AI assistant that lets students, teachers and parents query a school "
        "ERP in plain language. It plans, picks the right ERP tool(s) via function "
        "calling, fetches mock data and returns a structured answer with the plan "
        "it followed and the tools it used."
    ),
    version="1.0.0",
)

register_exception_handlers(app)
app.include_router(chat.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


log.info("%s ready", settings.app_name)
