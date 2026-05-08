from pathlib import Path
import sys


def ensure_repo_root_on_path(current_file: str) -> Path:
    repo_root = Path(current_file).resolve().parents[2]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    return repo_root
