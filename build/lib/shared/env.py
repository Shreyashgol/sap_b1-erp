import os
from pathlib import Path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()

    if not key:
        return None

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]

    return key, value


def load_env_file(path: Path, override: bool = False):
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if override:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


def load_agent_env(current_file: str):
    current_path = Path(current_file).resolve()
    repo_root = current_path.parents[2]
    agent_root = current_path.parents[1]

    load_env_file(repo_root / ".env")
    load_env_file(agent_root / ".env", override=True)
