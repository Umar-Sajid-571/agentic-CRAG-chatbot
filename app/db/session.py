import os
import uuid
import sqlite3
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import List, Generator, Dict, Any

# Assuming Base and models are imported from schemas
from .schemas import Base, User, LongTermMemory, ChatTitle # Import ChatTitle

from dotenv import load_dotenv
load_dotenv()

POSTGRES_URL = os.getenv("POSTGRES_URL")
SQLITE_DB_PATH = "chat_history.db"
# --- Global Setup for SQLAlchemy ---
# Ye variables global hona zaroori hain takay main.py inhein import kar sakay
engine = create_engine(POSTGRES_URL) if POSTGRES_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None
# Base hum pehle hi schemas se import kar chukay hain (aapki line 10)
# --- Database Configuration ---
# POSTGRES_URL is expected to be in the .env file.
POSTGRES_URL = os.getenv("POSTGRES_URL")
SQLITE_DB_PATH = "chat_history.db" # For chat history

# --- PostgreSQL Connection ---
def get_postgres_conn() -> psycopg2.extensions.connection:
    """
    Establishes a connection to the PostgreSQL database.
    Requires POSTGRES_URL to be set in environment variables.
    """
    if not POSTGRES_URL:
        raise ValueError("POSTGRES_URL environment variable not set. Cannot connect to PostgreSQL.")
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        raise

# --- SQLite Connection for Chat History ---
def get_sqlite_conn() -> sqlite3.Connection:
    """
    Establishes a connection to the SQLite database for chat history.
    Creates the file if it does not exist.
    """
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON;") # Enable foreign key support for SQLite
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to SQLite: {e}")
        raise

# --- Database Initialization ---
def init_db():
    """
    Initializes the database by creating tables if they don't exist.
    Handles both PostgreSQL and SQLite.
    """
    # Initialize PostgreSQL DB
    if POSTGRES_URL:
        try:
            postgres_engine = create_engine(POSTGRES_URL)
            Base.metadata.create_all(bind=postgres_engine) # This will create all tables defined in schemas.py (User, LongTermMemory, ChatTitle)
            print("PostgreSQL tables created or already exist.")
        except Exception as e:
            print(f"Error initializing PostgreSQL database: {e}")
    else:
        print("POSTGRES_URL not set. Skipping PostgreSQL database initialization.")

    # Initialize SQLite DB for chat history
    try:
        sqlite_conn = get_sqlite_conn()
        # Define and create chat_history table for SQLite if it doesn't exist
        cursor = sqlite_conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        # Also create chat_titles table for SQLite if it's managed here
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_titles (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                thread_id TEXT NOT NULL
            );
        ''')
        sqlite_conn.commit()
        sqlite_conn.close()
        print("SQLite database and tables (chat_history, chat_titles) initialized or already exist.")
    except sqlite3.Error as e:
        print(f"Error initializing SQLite database tables: {e}")

# --- Isolation Logic Helper Functions ---

# PostgreSQL Helper Functions (using SQLAlchemy session for ORM capabilities)
def get_postgres_session() -> sessionmaker:
    """Creates a SQLAlchemy session factory for PostgreSQL."""
    if not POSTGRES_URL:
        raise ValueError("POSTGRES_URL not set.")
    engine = create_engine(POSTGRES_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal

def save_chat_title_pg(user_id: str, title: str, thread_id: str):
    """Saves a chat title to PostgreSQL, ensuring user_id isolation."""
    SessionLocal = get_postgres_session()
    session = SessionLocal()
    try:
        # Check if a chat title with the same thread_id for this user already exists
        existing_title = session.query(ChatTitle).filter(
            ChatTitle.user_id == user_id,
            ChatTitle.thread_id == thread_id
        ).first()

        if existing_title:
            existing_title.title = title
            session.commit()
            print(f"Updated chat title for user {user_id}, thread {thread_id}")
        else:
            new_chat_title = ChatTitle(
                id=str(uuid.uuid4()),
                user_id=user_id,
                title=title,
                thread_id=thread_id
            )
            session.add(new_chat_title)
            session.commit()
            print(f"Saved new chat title for user {user_id}, thread {thread_id}")
    except Exception as e:
        session.rollback()
        print(f"Error saving chat title for user {user_id}: {e}")
    finally:
        session.close()

def get_chat_titles_by_user_pg(user_id: str) -> List[Dict[str, Any]]:
    """Retrieves all chat titles for a given user_id from PostgreSQL."""
    SessionLocal = get_postgres_session()
    session = SessionLocal()
    try:
        chat_titles = session.query(ChatTitle).filter(ChatTitle.user_id == user_id).all()
        # Convert to list of dictionaries for easier handling
        return [
            {"id": str(ct.id), "user_id": str(ct.user_id), "title": ct.title, "thread_id": ct.thread_id}
            for ct in chat_titles
        ]
    except Exception as e:
        print(f"Error retrieving chat titles for user {user_id}: {e}")
        return []
    finally:
        session.close()

# SQLite Helper Functions
def save_chat_title_sqlite(user_id: str, title: str, thread_id: str):
    """Saves a chat title to SQLite, ensuring user_id isolation."""
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        # Check if a chat title with the same thread_id for this user already exists
        cursor.execute(
            "SELECT id FROM chat_titles WHERE user_id = ? AND thread_id = ?",
            (user_id, thread_id)
        )
        existing_title = cursor.fetchone()

        if existing_title:
            cursor.execute(
                "UPDATE chat_titles SET title = ? WHERE user_id = ? AND thread_id = ?",
                (title, user_id, thread_id)
            )
            print(f"Updated chat title in SQLite for user {user_id}, thread {thread_id}")
        else:
            new_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO chat_titles (id, user_id, title, thread_id) VALUES (?, ?, ?, ?)",
                (new_id, user_id, title, thread_id)
            )
            print(f"Saved new chat title in SQLite for user {user_id}, thread {thread_id}")
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error saving chat title in SQLite for user {user_id}: {e}")
    finally:
        conn.close()

def get_chat_titles_by_user_sqlite(user_id: str) -> List[Dict[str, Any]]:
    """Retrieves all chat titles for a given user_id from SQLite."""
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, user_id, title, thread_id FROM chat_titles WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        # Convert rows to list of dictionaries
        return [
            {"id": row[0], "user_id": row[1], "title": row[2], "thread_id": row[3]}
            for row in rows
        ]
    except sqlite3.Error as e:
        print(f"Error retrieving chat titles from SQLite for user {user_id}: {e}")
        return []
    finally:
        conn.close()


def get_db() -> Generator:
    """
    FastAPI dependency that provides a SQLAlchemy session for PostgreSQL.
    """
    if not SessionLocal:
        raise ValueError("POSTGRES_URL is not configured.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Note: The actual implementation of save_chat_title and thread-fetching functions
# would be in your application's service/handler layer, calling these DB functions
# and always passing the correct user_id.
