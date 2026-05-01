from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta
from jose import JWTError, jwt 
import uuid

from app.db.session import get_db
from app.db.schemas import User # Assuming User model is in schemas.py
from app.core.security import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM # Import security constants
from pydantic import BaseModel

router = APIRouter()

# Pydantic models for request bodies
class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserLogin(BaseModel):
    username: str
    password: str

@router.post("/signup", response_model=dict, status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new user.
    """
    # Check if username already exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Hash the password
    hashed_password = get_password_hash(user.password)

    # Create new user instance
    new_user = User(username=user.username, password_hash=hashed_password)
    # Add user to the database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Return user ID and success message
    return {"message": "User created successfully", "user_id": new_user.id}

@router.post("/login", response_model=Token)
def login_for_access_token(
    user_credentials: UserLogin, db: Session = Depends(get_db)
):
    """
    Authenticates a user and returns an access token.
    """
    db_user = db.query(User).filter(User.username == user_credentials.username).first()
    if not db_user or not verify_password(user_credentials.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    # The 'sub' (subject) typically identifies the user, which is their ID in this case.
    # The expiration delta is already configured in app.core.security as ACCESS_TOKEN_EXPIRE_MINUTES
    access_token_expires = timedelta(minutes=30) # This should ideally be configured globally or from app.core.security
    access_token = create_access_token(
        data={"sub": str(db_user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Dependency to get the current logged-in user ---
async def get_current_user(
    request: Request, # Request object to get headers
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current logged-in user.
    Fetches user from database based on JWT token in Authorization header.
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Header missing")

        if " " in auth_header:
            scheme, token = auth_header.split(" ", 1)
        else:
            scheme, token = "bearer", auth_header
            
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid scheme")

        # Decode token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"DEBUG: Decoded Payload: {payload}")
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Fetch user from database
        # Ensure User model has 'id' and it's an integer type for comparison
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValueError: # For cases where user_id cannot be converted to int
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e: # Catch other potential errors like header parsing
        # Log the error for debugging in a real application
        print(f"An error occurred during authentication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred during authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        )
