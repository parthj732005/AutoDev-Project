from fastapi import APIRouter, HTTPException

from app.config import load_settings, save_settings

router = APIRouter()

_MASKED_KEYS = ("openai_api_key", "anthropic_api_key", "gemini_api_key", "groq_api_key", "huggingface_api_key")


def _mask(settings: dict) -> dict:
    masked = settings.copy()
    for key in _MASKED_KEYS:
        val = masked.get(key, "")
        if val and len(val) > 8:
            masked[key] = val[:4] + "..." + val[-4:]
        elif val:
            masked[key] = "***"
    return masked


@router.get("/providers")
def get_available_providers():
    """Return every supported provider, flagging which ones are actually configured."""
    s = load_settings()
    providers = [
        {
            "value": "openai",
            "label": "OpenAI",
            "model": s.get("openai_model", "gpt-5.4-mini"),
            "configured": bool(s.get("openai_api_key")),
        },
        {
            "value": "anthropic",
            "label": "Anthropic",
            "model": s.get("anthropic_model", "claude-sonnet-5"),
            "configured": bool(s.get("anthropic_api_key")),
        },
        {
            "value": "groq",
            "label": "Groq",
            "model": s.get("groq_model", "llama-3.3-70b-versatile"),
            "configured": bool(s.get("groq_api_key")),
        },
        {
            "value": "huggingface",
            "label": "HuggingFace",
            "model": s.get("huggingface_model", "Qwen/Qwen3-Coder-30B-A3B-Instruct"),
            "configured": bool(s.get("huggingface_api_key")),
        },
        {
            "value": "ollama",
            "label": "Ollama (Local • Slow on CPU)",
            "model": s.get("ollama_model", "qwen2.5-coder:7b"),
            "configured": True,  # no API key required, only reachability at generation time
        },
    ]

    stored_default = s.get("provider", "openai")
    default_entry = next((p for p in providers if p["value"] == stored_default), None)
    if not default_entry or not default_entry["configured"]:
        # Fall back to the first configured provider so the UI never
        # defaults to a selection that will immediately fail.
        configured = next((p for p in providers if p["configured"]), None)
        stored_default = configured["value"] if configured else stored_default

    return {"providers": providers, "default": stored_default}


@router.get("/")
def get_settings():
    return _mask(load_settings())


@router.post("/")
def update_settings(body: dict):
    current = load_settings()
    # Don't overwrite with masked placeholder values
    for key in _MASKED_KEYS:
        incoming = body.get(key, "")
        if "..." in incoming or incoming == "***":
            body[key] = current.get(key, "")
    current.update(body)
    try:
        save_settings(current)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write settings file: {exc}")
    return {"status": "saved"}
