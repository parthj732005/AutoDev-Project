import asyncio
import json
import os
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agents.base_agent import AgentEvent
from app.config import load_settings
from app.services.orchestrator import Orchestrator
from app.services.project_generator import ProjectGenerator

router = APIRouter()

_CHITCHAT_RE = re.compile(
    r"^(hi|hello|hey|yo|sup|hola|howdy|good\s*(morning|afternoon|evening)|"
    r"how\s*are\s*you|what'?s\s*up|thanks?|thank\s*you|ok(ay)?|test(ing)?)[\s!.,?]*$",
    re.IGNORECASE,
)


def _looks_like_project_prompt(prompt: str) -> bool:
    if _CHITCHAT_RE.match(prompt.strip()):
        return False
    if len(prompt.split()) < 3:
        return False
    return True


def _check_output_dir(output_dir: str) -> str | None:
    """Verify the configured output directory exists and is writable
    BEFORE spending any LLM calls on generation. Returns an error message,
    or None if the directory is fine."""
    path = Path(output_dir).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"Cannot create output directory '{path}': {exc}. Check the path in Settings."
    if not os.access(path, os.W_OK):
        return f"Output directory '{path}' is not writable. Check permissions or change it in Settings."
    return None


@router.websocket("/ws")
async def generate_ws(websocket: WebSocket):
    await websocket.accept()

    # Tracks the folder this run creates, so we can clean it up on failure —
    # but only if THIS run created it (never delete a pre-existing project
    # just because a same-named regeneration attempt failed).
    project_path_to_cleanup: Path | None = None

    try:
        raw = await websocket.receive_text()
        payload = json.loads(raw)
        prompt = payload.get("prompt", "").strip()
        provider_override = payload.get("provider")  # optional override from UI

        if not prompt:
            await websocket.send_json(
                {"agent": "System", "event": "error", "message": "Prompt is empty."}
            )
            return

        if not _looks_like_project_prompt(prompt):
            await websocket.send_json(
                {
                    "agent": "System",
                    "event": "error",
                    "message": (
                        "That doesn't look like a project description. Try something like: "
                        "\"Build a REST API for a todo app with FastAPI and SQLite.\""
                    ),
                }
            )
            return

        settings = load_settings()
        output_dir = settings.get("output_directory", "~/autodev-projects")
        dir_error = _check_output_dir(output_dir)
        if dir_error:
            await websocket.send_json(
                {"agent": "System", "event": "error", "message": dir_error}
            )
            return

        generation_logs: list[dict] = []

        async def emit(event: AgentEvent):
            event_dict = event.to_dict()
            generation_logs.append(event_dict)
            try:
                await websocket.send_json(event_dict)
            except Exception:
                pass

        orchestrator = Orchestrator(emit=emit, provider_override=provider_override)

        # Race the actual generation against a listener for a client cancel
        # signal (explicit {"action": "cancel"} message OR the socket closing).
        # Without this, clicking "Cancel" only closed the browser's side of the
        # socket — the backend kept running the LLM call to completion anyway,
        # which is exactly why CPU/Ollama stayed busy for minutes after Stop.
        generation_task = asyncio.ensure_future(orchestrator.run(prompt))
        cancel_watch_task = asyncio.ensure_future(websocket.receive_text())

        done, _ = await asyncio.wait(
            {generation_task, cancel_watch_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if generation_task not in done:
            # Client cancelled (explicit message) or disconnected — actually
            # cancel the in-flight asyncio task. This interrupts whatever
            # await point the agent is stuck on, including a pending HTTP
            # request to a provider (Ollama, Groq, etc.), instead of letting
            # it run to completion in the background.
            generation_task.cancel()
            try:
                await generation_task
            except (asyncio.CancelledError, Exception):
                pass
            try:
                await websocket.send_json(
                    {
                        "agent": "System",
                        "event": "cancelled",
                        "message": "Generation cancelled — no project was saved.",
                    }
                )
            except Exception:
                pass
            return

        cancel_watch_task.cancel()
        try:
            await cancel_watch_task
        except (asyncio.CancelledError, Exception):
            pass
        result = generation_task.result()

        generator = ProjectGenerator(output_dir)
        requested_name = result["plan"].get("project_name", "autodev_project")
        project_name = generator.resolve_unique_name(requested_name)
        if project_name != requested_name:
            await websocket.send_json(
                {
                    "agent": "System",
                    "event": "log",
                    "message": f"A project named '{requested_name}' already exists — saving this one as '{project_name}' instead.",
                }
            )
        # Keep the plan sent back to the UI in sync with the folder actually used.
        result["plan"]["project_name"] = project_name

        # resolve_unique_name() guarantees this folder doesn't exist yet, so it's
        # always safe (and always correct) to track it for cleanup-on-failure.
        project_path_to_cleanup = Path(output_dir).expanduser() / project_name

        repair_report = result.get("repair_report", {"attempted": [], "repaired": [], "reverted": []})

        project_path, written_files, skipped_files = generator.generate(
            project_name,
            result["files"],
            result["plan"],
            result["validation_report"],
            result.get("consistency_report", {}),
            generation_logs,
            repair_report,
        )

        # Generation completed successfully — nothing to clean up.
        project_path_to_cleanup = None

        message = f"Project saved to {project_path}"
        if repair_report["repaired"]:
            message += f" ({len(repair_report['repaired'])} file(s) auto-repaired)"
        if skipped_files:
            message += f" ({len(skipped_files)} file(s) skipped due to invalid names — see details)"

        await websocket.send_json(
            {
                "agent": "System",
                "event": "completed",
                "message": message,
                "data": {
                    "project_path": project_path,
                    "files": written_files,
                    "skipped_files": skipped_files,
                    "plan": result["plan"],
                    "validation_report": result["validation_report"],
                    "valid": result["valid"],
                    "consistency_report": result.get("consistency_report", {}),
                    "repair_report": repair_report,
                },
            }
        )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        # Generation failed after a fresh project folder was created —
        # remove the partial/orphaned output so it never lingers on disk
        # or shows up in the Projects list without valid metadata.
        if project_path_to_cleanup is not None:
            shutil.rmtree(project_path_to_cleanup, ignore_errors=True)
        try:
            await websocket.send_json(
                {"agent": "System", "event": "error", "message": str(exc)}
            )
        except Exception:
            pass
