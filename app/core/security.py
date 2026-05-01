import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from dotenv import load_dotenv
load_dotenv()

# --- JWT Configuration ---
# It's highly recommended to load these from environment variables
# For demonstration, using placeholders. In a real app, use `os.environ.get("JWT_SECRET_KEY")` etc.
# Ensure you change "your-super-secret-key-change-me" to a strong, unique key in production.
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-super-secret-key-change-me")
print(f"DEBUG: Backend using SECRET_KEY: {SECRET_KEY}")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30)) # Token expiration time

# Initialize password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Creates an access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Optional: Token Verification Function ---
# This function can be used to verify tokens, e.g., in dependency injection for protected routes.
# def verify_access_token(token: str) -> str:
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Could not validate credentials",
#                 headers={"WWW-Authenticate": "Bearer"},
#             )
#         return username
#     except JWTError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Could not validate credentials",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
