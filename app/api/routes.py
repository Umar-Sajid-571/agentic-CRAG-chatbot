from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.db.session import SessionLocal, engine
from app.db.schemas import User # Assuming User model is in schemas.py
import uuid

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Create router
router = APIRouter()

# Function to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register", summary="Register a new user")
async def register_user(
    username: str,
    password: str,
    db: Session = Depends(get_db)
):
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already registered")

    # Hash the password
    hashed_password = pwd_context.hash(password)

    # Create new user instance
    new_user = User(
        id=uuid.uuid4(), # Generate new UUID for the user ID
        username=username,
        password_hash=hashed_password
    )

    # Add user to the database session and commit
    db.add(new_user)
    db.commit()
    db.refresh(new_user) # Refresh to get the generated ID

    return {"message": "User registered successfully", "user_id": str(new_user.id)}

