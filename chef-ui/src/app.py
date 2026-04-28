"""Chef UI — Chainlit application entry point.

Handles authentication, session management, and user messages.
Delegates Step Functions orchestration to :mod:`sfn_client` and
uses JSON-structured logging from :mod:`logging_config`.
"""

import uuid
import json
from os import getenv
from pathlib import Path

import chainlit as cl

from logging_config import get_logger
from sfn_client import StepFunctionsClient

# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_DEFAULT_LANG = "es"


def _detect_language() -> str:
    """Return the best matching template language from the browser's Accept-Language header.

    Uses cl.context.session.language (Chainlit 2.5.5+), which exposes the primary
    BCP 47 tag (e.g. "es-419", "en-US") pre-parsed from the Accept-Language header.
    Falls back to _DEFAULT_LANG when the session context is unavailable or no matching
    template folder exists for the detected language code.
    """
    try:
        # .language is a single BCP 47 tag, e.g. "es-419" or "en-US"
        lang_tag: str = cl.context.session.language
        code = lang_tag.split("-")[0].lower()
        logger.info("Detecting user language", extra={"lang_tag": lang_tag, "code": code})
        if (_TEMPLATES_DIR / code).is_dir():
            return code
    except Exception:
        pass
    return _DEFAULT_LANG


def _load_template(name: str, lang: str) -> str:
    path = _TEMPLATES_DIR / lang / name
    if not path.exists():
        path = _TEMPLATES_DIR / _DEFAULT_LANG / name
    return path.read_text(encoding="utf-8")


def _load_messages(lang: str) -> dict:
    path = _TEMPLATES_DIR / lang / "messages.json"
    if not path.exists():
        path = _TEMPLATES_DIR / _DEFAULT_LANG / "messages.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _render(template: str, **kwargs: str) -> str:
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", value)
    return template

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STATE_MACHINE_ARN: str | None = getenv("ORCHESTRATION_STATE_MACHINE_ARN", "arn:aws:states:eu-central-1:741881499996:stateMachine:HelloWorldStateMachine17A15ADF-GcLB0vd0jRgH")
AWS_REGION: str = getenv("AWS_REGION", "eu-central-1")

logger = get_logger(__name__)

# Shared Step Functions client (boto3 clients are thread-safe).
_sfn = StepFunctionsClient(region=AWS_REGION)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@cl.password_auth_callback
def auth_callback(username: str, password: str) -> cl.User | None:
    """Validate credentials against ``CHEF_UI_USER`` / ``CHEF_UI_PASSWORD`` env vars.

    Args:
        username: Username submitted by the user.
        password: Password submitted by the user.

    Returns:
        Authenticated :class:`cl.User` on success, ``None`` on failure.
    """
    if (username, password) == (getenv("CHEF_UI_USER"), getenv("CHEF_UI_PASSWORD")):
        logger.info("User authenticated", extra={"username": username})
        return cl.User(identifier=username)

    logger.warning("Authentication failed", extra={"username": username})
    return None


# ---------------------------------------------------------------------------
# Chat lifecycle
# ---------------------------------------------------------------------------


@cl.on_chat_start
async def on_start() -> None:
    """Initialise a new chat session with a unique session ID."""
    # Use two concatenated UUIDs so the ID is long enough for any downstream
    # service that enforces a minimum length (e.g. AgentCore: ≥33 chars).
    session_id = uuid.uuid4().hex + uuid.uuid4().hex
    lang = _detect_language()
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("lang", lang)

    msgs = _load_messages(lang)
    logger.info("Chat session started", extra={"session_id": session_id, "lang": lang})
    await cl.Message(msgs["chat"]["greeting"]).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    session_id: str = cl.user_session.get("session_id")
    lang: str = cl.user_session.get("lang", _DEFAULT_LANG)
    msgs = _load_messages(lang)

    logger.info(
        "Received user message",
        extra={"session_id": session_id, "message_length": len(message.content)},
    )

    if not STATE_MACHINE_ARN:
        await cl.Message(content=msgs["errors"]["noStateMachineArn"]).send()
        return

    try:
        # 1. Start Step Function
        execution_arn = _sfn.start_execution(
            state_machine_arn=STATE_MACHINE_ARN,
            session_id=session_id,
            prompt=message.content,
        )

        # 2. Show a "Thinking" state to the user
        msg = cl.Message(content=msgs["chat"]["thinking"])
        await msg.send()

        # 3. Poll for result
        execution = await _sfn.poll_until_complete(execution_arn)
        raw_answer = _sfn.extract_result(execution)

        if not raw_answer:
            await cl.Message(content=msgs["errors"]["noResult"]).send()
            return

        # 4. Handle JSON parsing from the Pass State (FinalOutput)
        # We expect raw_answer to be a dict containing 'result' and 'full_response'
        try:
            # If extract_result returns a string, parse it. If it's already a dict, use it.
            data = json.loads(raw_answer) if isinstance(raw_answer, str) else raw_answer
            result = data.get("result", {})
            
            # --- CASE A: Chef Suggestions ---
            if "suggestions" in result:
                suggestions_list = "".join(
                    f"* {item}\n" for item in result["suggestions"]
                )
                content = _render(
                    _load_template("chef_suggestions.md", lang),
                    suggestions_list=suggestions_list,
                )
                await cl.Message(content=content).send()

            # --- CASE B: Nutritionist Final Recipe ---
            elif "recipe_title" in result:
                nutri = result.get("nutrition_summary", {})
                if nutri:
                    rows = "".join(
                        f"| {i.get('item')} | {i.get('calories')} | {i.get('protein')} | {i.get('fat')} |\n"
                        for i in nutri.get("breakdown", [])[:10]
                    )
                else:
                    rows = ""

                content = _render(
                    _load_template("nutritionist_recipe.md", lang),
                    recipe_title=result.get("recipe_title", "Receta sin título"),
                    instructions=result.get("instructions", ""),
                    total_calories=str(nutri.get("total_calories", "N/A")),
                    rows=rows,
                    final_message=result.get("final_message", ""),
                )
                await cl.Message(content=content).send()

            # --- CASE C: Fallback to raw response ---
            else:
                await cl.Message(content=str(result)).send()

        except Exception as parse_err:
            logger.error(f"Parsing error: {parse_err}")
            await cl.Message(content=msgs["errors"]["parseError"].format(raw_answer=raw_answer)).send()

    except Exception:
        logger.exception("Unexpected error in workflow", extra={"session_id": session_id})
        await cl.Message(content=msgs["errors"]["connectionError"]).send()
