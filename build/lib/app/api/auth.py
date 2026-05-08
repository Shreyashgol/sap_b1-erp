from fastapi import APIRouter, HTTPException

from app.operations.utils import create_jwt_token
from app.schema.auth import LoginResponse

router = APIRouter()

fake_users_db = {
    "user1": "pass123456",
}


@router.post("/login", response_model=LoginResponse)
def login(username: str, password: str):
    if username in fake_users_db and password == fake_users_db[username]:
        return LoginResponse(access_token=create_jwt_token(user_id=username))

    raise HTTPException(status_code=401, detail="Invalid credentials")
