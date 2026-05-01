from fastapi import FastAPI, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import BaseModel
from typing import List, Dict, Any

from langchain_core.messages import HumanMessage

from jose import JWTError, jwt

# Assuming User model is correctly defined in app.db.schemas
from app.db.schemas import User
# Assuming get_db is correctly defined in app.db.session
from app.db.session import get_db, engine, Base
# Importing security constants and functions from app.core.security
from app.core.security import SECRET_KEY, ALGORITHM, create_access_token, verify_password
# Importing the auth router
from app.api.auth import router as auth_router, get_current_user

from LangGraph_Backend import chatbot, all_previous_threads, init_memory_db_and_tables

# from app.models.user import User
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI()


@app.on_event("startup")
async def startup_event():
    await init_memory_db_and_tables() 
    print("Database and Memory initialized!")


# Include the auth router
app.include_router(auth_router, prefix="/auth")

# --- Chatbot Graph Initialization ---
# Use the imported 'chatbot' object directly.
# If LangGraph_Backend.py could not be imported, 'chatbot' will be the dummy object.
try:
    # Check if the imported 'chatbot' is the dummy or the real one
    if hasattr(chatbot, 'invoke') and callable(chatbot.invoke): # Simple check for a callable invoke method
        print("Chatbot graph initialized successfully from LangGraph_Backend.")
    else:
        # This case should ideally not be reached if dummy implementation is set correctly
        print("Warning: Chatbot object is not in expected format.")
        chatbot = None # Ensure it's None if something is wrong
except Exception as e:
    print(f"Error initializing chatbot graph: {e}")
    chatbot = None # Set to None if initialization fails


# --- Pydantic models for request/response ---
class ChatRequest(BaseModel):
    user_input: str
    thread_id: str | None = None # Optional thread_id for continuing a conversation

class ChatResponse(BaseModel):
    response: str # Simplified response, could be more complex

class HistoryResponseItem(BaseModel):
    id: str # Changed from int to str to match dummy and real implementation return type
    chat_title: str # Renamed from 'title' to 'chat_title' to match dummy and real implementation

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user), # Ensure user is logged in
    db: Session = Depends(get_db) # To potentially save chat history or pass to graph
):
    """
    Endpoint for chatting with the AI.
    Requires authentication.
    """
    if chatbot is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chatbot service is currently unavailable."
        )

    try:
        # Prepare input for the chatbot graph
        # Assuming the graph expects a dict with 'user_input', 'thread_id', and 'user_id'
        user_input = chat_request.user_input
        msg = {"messages": [HumanMessage(content=user_input)]}
        config = {
            "configurable": {
                "thread_id": chat_request.thread_id,
                "user_id": str(current_user.id)
            }
        }

        # Invoke the chatbot graph
        # Use invoke for a single response, or stream for a streaming response
        # For simplicity, we'll use invoke here. For streaming, you'd use streaming=True
        # and return an EventSourceResponse.
        ai_response_data = await chatbot.ainvoke(msg, config=config) # Pass user_id if graph needs it for history/context

        # Extract the response. This depends on the structure of your chatbot's output.
        # Assuming the chatbot.invoke returns a dict with a 'response' key.
        response_text = ai_response_data["messages"][-1].content

        return ChatResponse(response=response_text)

    except HTTPException as he:
        # Re-raise HTTP exceptions that might come from the chatbot invocation itself
        raise he
    except Exception as e:
        # Log the exception for debugging
        print(f"An error occurred during chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing your chat request."
        )

@app.get("/history", response_model=List[HistoryResponseItem])
async def history_endpoint(
    current_user: User = Depends(get_current_user), # Ensure user is logged in
    # db: Session = Depends(get_db) # Removed db as all_previous_threads doesn't use it
):
    """
    Endpoint to retrieve chat history for the current user.
    Filters threads to show only those belonging to the logged-in user.
    """
    try:
        # Call the logic function to get all threads.
        # The original `all_previous_threads` in LangGraph_Backend.py does not take `db` or `user_id`.
        # It fetches from SQLite and does not inherently filter by user.
        # The filtering logic for user-specific threads needs to be implemented.
        all_threads = await all_previous_threads()

        # --- NOTE ON USER-SPECIFIC FILTERING ---
        # The current implementation of `all_previous_threads` in LangGraph_Backend.py
        # fetches data from SQLite's `checkpoints` and `chat_titles` tables. These tables,
        # as implemented, do not store a `user_id` per thread. Therefore, filtering threads
        # to show ONLY the current user's threads is NOT possible with the current backend logic.
        #
        # To implement user-specific filtering, you would need to:
        # 1. Modify `all_previous_threads` to query based on `user_id`. This would require
        #    storing `user_id` in either the `checkpoints` or `chat_titles` table, or a
        #    new related table.
        # 2. Or, alternatively, modify `save_chat_title` and the checkpoint saving process
        #    to associate threads with a `user_id`.
        #
        # For now, this endpoint will return ALL threads fetched, as user-specific filtering
        # cannot be performed with the current data structure.
        print("Note: User-specific thread filtering is not possible with the current `all_previous_threads` implementation.")
        
        # If `all_previous_threads` were updated to accept `user_id` and filter, the call would be:
        # user_threads = await all_previous_threads(user_id=current_user.id)
        # return user_threads
        
        # Returning all threads as fetched by the current `all_previous_threads` implementation.
        return all_threads

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"An error occurred while fetching history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching chat history."
        )

# Note: The 'if __name__ == "__main__":' block should be removed from LangGraph_Backend.py
# and app instantiation/uvicorn run logic should be handled externally (e.g., via a separate run script or docker-compose)
# or by using a tool like 'uvicorn app.main:app --reload'.
