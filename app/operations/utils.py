import importlib.util
from functools import lru_cache
from pathlib import Path


def verify_jwt_token():
    """Bypassed authentication for guest access."""
    return "guest"


@lru_cache(maxsize=None)
def load_agent_module(agent_name: str, agent_folder: str):
    agents_dir = Path(__file__).resolve().parents[1] / "agents"
    folder_parts = Path(agent_folder)
    agent_path = agents_dir / folder_parts / f"{agent_name}.py"

    if not agent_path.exists():
        raise RuntimeError(f"Agent module not found: {agent_path}")

    module_folder = ".".join(folder_parts.parts)
    module_name = f"app.agents.{module_folder}.{agent_name}"
    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load agent module from {agent_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
