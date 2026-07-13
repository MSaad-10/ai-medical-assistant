from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger

from app.db.database import get_db
from app.db.models import User
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# --- Pydantic Data Validation Schemas ---
class UserCreateSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique login identifier")
    password: str = Field(..., min_length=6, description="Raw login password")

class TokenResponseSchema(BaseModel):
    access_token: str
    token_type: str

# --- API Route Endpoints ---
@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreateSchema, db: Session = Depends(get_db)):
    """Validates user data input, hashes the password, and creates a record in SQLite."""
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        logger.warning(f"Registration rejected: Username '{user_data.username}' is already taken.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    hashed_pw = get_password_hash(user_data.password)
    new_user = User(username=user_data.username, hashed_password=hashed_pw)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"Successfully registered new user ID: {new_user.id} - Username: {new_user.username}")
    return {"message": "User registered successfully", "user_id": new_user.id}

@router.post("/token", response_model=TokenResponseSchema)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Verifies credentials against SQLite and provides an OAuth2 compliant JWT token."""
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for username: '{form_data.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    logger.info(f"Issued active JWT token for authenticated user: '{user.username}'")
    return {"access_token": access_token, "token_type": "bearer"}