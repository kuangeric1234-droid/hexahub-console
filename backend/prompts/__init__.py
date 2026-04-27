from pathlib import Path

_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a prompt template from backend/prompts/<name>.md"""
    path = _DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
