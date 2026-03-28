from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from api.database import get_db, init_users_table
from api.auth_utils import hash_password, verify_password, create_access_token

router = APIRouter()
init_users_table()

class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(req: LoginRequest):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (req.email,)).fetchone()
    if not row or not verify_password(req.password, row["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": req.email, "user_id": row["id"]})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/signup")
def signup(req: SignupRequest):
    hashed = hash_password(req.password)
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO users (email, password) VALUES (?, ?)", (req.email, hashed))
            conn.commit()
    except Exception:
        raise HTTPException(status_code=400, detail="Email already registered")
    token = create_access_token({"sub": req.email})
    return {"access_token": token, "token_type": "bearer", "message": "Account created"}
