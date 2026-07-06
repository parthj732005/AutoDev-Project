import json
import re
import subprocess
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import load_settings
from app.services.azure_devops import AzureDevOpsClient
from app.services.logger import log
from app.services.model_provider import get_provider

router = APIRouter()

META_FILE = "autodev_meta.json"

SETUP_SYSTEM = """You are a senior developer writing setup instructions for a project that has ALREADY been generated on disk.

Return a JSON array of setup steps. Each step has:
{
  "title": "short step title",
  "commands": ["command1", "command2"],
  "note": "optional tip or explanation"
}

CRITICAL RULES:
- The project files ALREADY EXIST on the user's machine at the given path. Do NOT suggest git clone.
- Only reference files that are listed in the provided file list.
- Start from: navigate to the folder, then set up and run.
- For FastAPI: use correct module path (e.g. uvicorn todo_api.main:app --reload)
- For React/Vite: the exact frontend directory is given below as "Frontend directory". Always `cd` into
  that exact path before running npm commands. Do NOT assume "src", "frontend", or "client" — use only
  the given path. If it says "(project root)", do not cd at all before running npm install/npm run dev.
- If Dockerfile exists: include docker-compose up --build as an ALTERNATIVE way to run
- If .env.example exists: include copying it to .env and filling in values
- If requirements.txt exists: pip install -r requirements.txt
- If seed.py or similar exists: include running it to initialize the database
- If tests/ folder exists: include pytest step
- Keep all commands copy-paste ready for Windows (use 'copy' not 'cp')
- Return ONLY the JSON array, no markdown, no explanation
"""


def _output_dir() -> Path:
    settings = load_settings()
    return Path(settings.get("output_directory", Path.home() / "autodev-projects"))


def _detect_frontend_dir(files: list[str]) -> str:
    """Find the real directory containing package.json instead of assuming a fixed folder name."""
    for f in files:
        normalized = f.replace("\\", "/")
        if normalized == "package.json":
            return "(project root)"
        if normalized.endswith("/package.json"):
            return normalized.rsplit("/package.json", 1)[0]
    return "(project root)"


_SAFE_PROJECT_NAME = re.compile(r"^[A-Za-z0-9_\-]+$")


def _load_meta(project_name: str) -> tuple[dict, Path]:
    # Strict allow-list (not just a traversal blocklist) — this value is later
    # interpolated into a shell=True subprocess command in open_in_vscode, so
    # it must never contain quotes, `&`, `;`, backticks, or other shell metachars.
    if not _SAFE_PROJECT_NAME.match(project_name):
        raise HTTPException(status_code=400, detail="Invalid project name")
    project_path = _output_dir() / project_name
    meta_path = project_path / META_FILE
    if not project_path.exists() or not meta_path.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return json.loads(meta_path.read_text(encoding="utf-8")), meta_path
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail=f"Project metadata for '{project_name}' is corrupted and could not be read",
        )


# ─── Generated projects ───────────────────────────────────────────────────────

@router.get("/generated")
def list_generated_projects():
    output_dir = _output_dir()
    if not output_dir.exists():
        return []
    projects = []
    for folder in sorted(output_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not folder.is_dir():
            continue
        meta_path = folder / META_FILE
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["path"] = str(folder)
            projects.append(meta)
        except Exception:
            continue
    return projects


@router.get("/generated/{project_name}")
def get_generated_project(project_name: str):
    meta, _ = _load_meta(project_name)
    project_path = _output_dir() / project_name
    meta["path"] = str(project_path)

    file_details = []
    for f in meta.get("files", []):
        fp = project_path / f
        if fp.exists():
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")
                file_details.append({
                    "path": f,
                    "size": fp.stat().st_size,
                    "lines": len(content.splitlines()),
                })
            except Exception:
                pass
    meta["file_details"] = file_details
    return meta


@router.post("/generated/{project_name}/setup-instructions")
async def get_setup_instructions(project_name: str):
    """Generate (or return cached) LLM setup instructions for a project."""
    meta, meta_path = _load_meta(project_name)

    # Return cached if already generated
    if meta.get("setup_instructions"):
        return {"instructions": meta["setup_instructions"]}

    settings = load_settings()
    provider = get_provider(settings)

    tech = meta.get("technologies", {})
    deps = meta.get("dependencies", {})
    features = meta.get("features", [])
    project_path = str(_output_dir() / project_name)
    all_files = meta.get("files", [])
    frontend_dir = _detect_frontend_dir(all_files) if tech.get("frontend", "none") != "none" else "n/a"

    prompt = f"""Generate setup instructions for this project:

Project name: {project_name}
Description: {meta.get("description", "")}
Project type: {meta.get("project_type", "")}
Backend: {tech.get("backend", "none")}
Frontend: {tech.get("frontend", "none")}
Frontend directory: {frontend_dir}
Database: {tech.get("database", "none")}
Backend dependencies: {deps.get("backend", [])}
Frontend dependencies: {deps.get("frontend", [])}
Features: {features}
Project path on disk: {project_path}
Files present: {all_files[:20]}

Generate step-by-step instructions to get this project running locally.
"""

    try:
        raw = await provider.complete(SETUP_SYSTEM, prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach the AI provider to generate setup instructions: {exc}",
        )

    match = re.search(r"\[[\s\S]*\]", raw)
    if not match:
        raise HTTPException(status_code=500, detail="LLM did not return valid setup instructions JSON")

    try:
        instructions = json.loads(match.group())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Setup instructions JSON is malformed: {exc}")

    # Cache in metadata
    meta["setup_instructions"] = instructions
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return {"instructions": instructions}


@router.post("/generated/{project_name}/open-vscode")
def open_in_vscode(project_name: str):
    meta, _ = _load_meta(project_name)
    project_path = _output_dir() / project_name
    try:
        # On Windows, `code` is a .cmd file — must use shell=True with a string
        subprocess.Popen(f'code "{project_path}"', shell=True)
        return {"status": "opened"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not open VS Code: {e}")


# ─── Azure DevOps (legacy) ────────────────────────────────────────────────────

class AzureProjectConfig(BaseModel):
    org: str
    project: str
    pat: str


@router.post("/ado/work-items")
def fetch_work_items(config: AzureProjectConfig):
    client = AzureDevOpsClient(org=config.org, project=config.project, pat=config.pat)
    try:
        work_items = client.get_work_items()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Azure DevOps: {exc}")

    try:
        return [
            {
                "id": item["id"],
                "type": item["fields"]["System.WorkItemType"],
                "title": item["fields"]["System.Title"],
                "description": item["fields"].get("System.Description", ""),
            }
            for item in work_items
        ]
    except KeyError as exc:
        raise HTTPException(
            status_code=502, detail=f"Unexpected Azure DevOps response format: missing {exc}"
        )


@router.post("/run")
def run_work_item(work_item: dict):
    log(f"Legacy /run called: {work_item.get('title', '')}")
    return {"status": "use /generate/ws for AI generation"}
