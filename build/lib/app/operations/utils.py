import importlib.util
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import JWT_ALGORITHM, JWT_EXPIRATION_MINUTES, JWT_SECRET

security = HTTPBearer()


def create_jwt_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    payload = {"sub": user_id, "exp": expire, "iat": datetime.utcnow()}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


@lru_cache(maxsize=None)
def load_agent_module(agent_name: str, agent_folder: str):
    agents_dir = Path(__file__).resolve().parents[1] / "agents"
    agent_path = agents_dir / agent_folder / f"{agent_name}.py"

    if not agent_path.exists():
        raise RuntimeError(f"Agent module not found: {agent_path}")

    module_name = f"app.agents.{agent_folder}.{agent_name}"
    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load agent module from {agent_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
