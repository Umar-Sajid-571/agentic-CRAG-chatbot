import streamlit as st
import requests
import os
import uuid

# Backend URL - assuming it's running on localhost:8000
BACKEND_URL = "http://127.0.0.1:8000"

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="LG ChatBot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# GLOBAL CSS  –  clean, modern, ChatGPT-like
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* ── Layout & UI Fixes ── */
[data-testid="stSidebar"] { border-right: 1px solid #2a2a2a; }
#MainMenu, footer, header[data-testid="stHeader"] {
    background: transparent !important;
}

/* Background Watermark */
[data-testid="stAppViewContainer"]::before {
    content: "🤖LG CHATBOT";
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 5rem;
    font-weight: bold;
    color: rgba(255, 255, 255, 0.03);
    z-index: 0;
    pointer-events: none;
}
                        
/* ── Sidebar Styling ── */
.sidebar-title {
    font-size: 1.1rem;
    font-weight: 700;
    padding: 0.4rem 0.6rem 0.8rem;
    color: #fff;
}
.sidebar-section {
    font-size: 0.9rem;
    font-weight: 600;
    color: #aaa;
    padding: 0.8rem 0.6rem 0.4rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Sidebar Watermark */
[data-testid="stSidebar"]::after {
    content: "© 2024";
    position: absolute;
    bottom: 20px;
    left: 0;
    width: 100%;
    text-align: center;
    font-size: 0.8rem;
    color: #555;
    letter-spacing: 0.1em;
}
                        
/* ── Chat messages (Layout focus) ── */
[data-testid="stChatMessage"] {
    background: transparent !important;
    padding: 0.6rem 0 !important;
    max-width: 780px;
    margin: 0 auto;
}

/* ── Input bar (Width fix) ── */
[data-testid="stChatInput"] {
    max-width: 780px;
    margin: 0 auto;
}

/* ── Custom Buttons ── */
div[data-testid="stButton"] > button {
    border-radius: 8px;
    transition: all 0.2s;
}

/* Specific styling for chat history buttons */
.chat-history-btn {
    text-align: left;
    padding: 0.5rem 0.6rem;
    margin: 2px 0;
    background: transparent;
    border: none;
    color: #ddd;
    width: 100%;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 0.95rem;
}
.chat-history-btn:hover {
    background-color: #2a2a2a;
    color: #fff;
}
.active-thread {
    background-color: #3a3a3a;
    color: #fff;
    font-weight: 600;
}
.active-thread:hover {
    background-color: #4a4a4a;
}

.thread-badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    margin-bottom: 0.5rem;
    background-color: #3a3a3a;
    color: #0f0;
    border-radius: 5px;
    font-size: 0.8rem;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SESSION STATE HELPERS
# ─────────────────────────────────────────────

def initialize_session_state():
    """Initializes session state variables."""
    if "token" not in st.session_state:
        st.session_state.token = None
        st.session_state.user_id = None
        st.session_state.username = None
    if "thread_list" not in st.session_state:
        st.session_state.thread_list = []
    if "current_thread_id" not in st.session_state:
        st.session_state.current_thread_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "show_upload" not in st.session_state: # For potential file uploads later
        st.session_state.show_upload = False

# ─────────────────────────────────────────────
# BACKEND API CALLS
# ─────────────────────────────────────────────

def get_headers():
    token = st.session_state.get("token")
    if token:
        # Debugging ke liye terminal mein print hoga
        print(f"DEBUG: Sending Token: {token[:10]}...") 
        return {"Authorization": f"Bearer {token}"}
    print("DEBUG: No token found in session_state")
    return {}

def fetch_threads():
    """Fetches the list of chat threads from the backend."""
    try:
        response = requests.get(f"{BACKEND_URL}/history", headers=get_headers())
        response.raise_for_status()
        threads_data = response.json()
        st.session_state.thread_list = threads_data
        # Set the first thread as current if no thread is selected yet
        if not st.session_state.current_thread_id and threads_data:
            st.session_state.current_thread_id = threads_data[0]["id"]
        elif not threads_data and st.session_state.current_thread_id is None:
             # If no threads exist, prepare for a new chat
             st.session_state.current_thread_id = str(uuid.uuid4())[:8] # Temporary ID for new chat
        return threads_data
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch chat history: {e}")
        return []

def fetch_thread_messages(thread_id):
    """Fetches messages for a specific thread."""
    try:
        response = requests.get(f"{BACKEND_URL}/threads/{thread_id}/messages", headers=get_headers())
        response.raise_for_status()
        messages_data = response.json()
        # Ensure messages are in the correct format for st.chat_message
        formatted_messages = []
        for msg in messages_data:
            message_obj = {"role": msg["role"], "content": msg["content"]}
            if "thoughts" in msg: # Assuming backend sends thoughts
                message_obj["thoughts"] = msg["thoughts"]
            formatted_messages.append(message_obj)
        st.session_state.messages = formatted_messages
        return formatted_messages
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch messages for thread {thread_id}: {e}")
        st.session_state.messages = [] # Clear messages on error
        return []

def create_new_thread():
    """Creates a new chat thread on the backend."""
    try:
        # If already logged in, create a new thread. If not logged in, this logic won't run.
        if not st.session_state.token:
            # This function should only be called when logged in
            st.warning("Please log in to create a new chat.")
            return None

        response = requests.post(f"{BACKEND_URL}/threads", headers=get_headers())
        response.raise_for_status()
        new_thread_data = response.json()
        new_thread_id = new_thread_data.get("thread_id")
        new_chat_title = new_thread_data.get("chat_title", f"Chat {new_thread_id}")

        # Add to session state and refresh threads list
        st.session_state.thread_list.insert(0, {"id": new_thread_id, "chat_title": new_chat_title}) # Add to beginning
        st.session_state.current_thread_id = new_thread_id
        st.session_state.messages = [] # Clear current messages for new chat
        st.success(f"New chat '{new_chat_title}' created!")
        return new_thread_id
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to create new chat: {e}")
        return None

def send_chat_message(user_input, thread_id, user_id):
    """Sends a message to the chat endpoint and returns a streaming response."""
    payload = {
        "user_input": user_input,
        "thread_id": thread_id,
        "user_id": user_id,
        # "messages": st.session_state.messages # Optionally send full history for context
    }
    try:
        # Use stream=True for streaming responses
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json=payload,
            headers=get_headers(),
            stream=True # Enable streaming
        )
        response.raise_for_status()
        
        # The response from /chat is expected to be a generator yielding message chunks or full messages
        # We need to process these chunks and yield them for st.write_stream
        
        full_response_content = ""
        all_thoughts = []
        
        # This part depends heavily on how the backend streams.
        # Assuming the backend streams JSON objects like:
        # {"content": "...", "role": "assistant", "thoughts": [...], "is_end": false}
        # or {"content": "...", "role": "assistant", "thoughts": [...], "is_end": true}
        
        # A more robust approach would be to parse SSE or a specific streaming format.
        # For simplicity here, let's assume text chunks and that thoughts might be in separate messages.
        # If the backend streams actual JSON objects for messages, this needs adjustment.
        
        # Simple approach: assume backend streams text chunks and we aggregate them.
        # A more advanced approach would be to parse JSON chunks.
        
        # Let's assume the backend streams chunks of text and we'll reconstruct the message.
        # If thoughts are separate, we'll need to handle that.
        
        # If the backend streams actual JSON message objects, this needs to be an iterator that parses JSON.
        # For now, we'll aggregate and assume thoughts might come in a special format or with the final message.
        
        # Re-architecting this part to handle potential thoughts and a proper stream.
        # If backend provides SSE, we'd use that. If it's just chunks, we assemble.
        # Let's assume the backend streams JSON objects for messages.
        
        # A common way to stream JSON objects: Each line is a JSON string.
        
        for line in response.iter_lines():
            if line:
                try:
                    data = response.json() # This might fail if not JSON per line.
                    # If backend sends actual JSON objects, parse it.
                    # e.g. {"content": "...", "role": "assistant", "thoughts": [...], "is_end": false/true}
                    # The previous code used 'chatbot.stream' which returned events.
                    # This HTTP stream needs a specific format from the backend.
                    
                    # Let's assume backend streams messages in a format like:
                    # {"role": "assistant", "content": "...", "thoughts": [...] }
                    # or for a simple chunk: {"content_chunk": "..."}
                    
                    # For now, let's simplify and assume the backend streams chunks of text for `st.write_stream`
                    # and we'll handle message aggregation and thought extraction separately if needed.
                    # This example assumes the backend streams raw text chunks for `st.write_stream`.
                    # If thoughts need to be handled, the backend needs to provide them in a structured way.
                    
                    # If the backend streams full messages with thoughts, we'd parse and yield those.
                    # For a simple write_stream, we just need to yield chunks.
                    
                    # Let's assume backend streams text chunks for st.write_stream
                    yield line.decode('utf-8') # Yield chunks for st.write_stream

                except Exception as e:
                    # Handle cases where line is not JSON or other parsing errors
                    # If the backend simply streams text, we can yield it directly.
                    yield line.decode('utf-8') # Yield as text if not JSON

    except requests.exceptions.RequestException as e:
        st.error(f"Error sending message: {e}")
        yield "An error occurred while sending your message." # Yield error message for st.write_stream
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        yield "An unexpected error occurred."

# ─────────────────────────────────────────────
# AUTHENTICATION FUNCTIONS (from previous frountend.py)
# ─────────────────────────────────────────────
def login_user(username, password):
    """Calls the FastAPI /auth/login endpoint."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"username": username, "password": password}
        )
        response.raise_for_status()
        data = response.json()
        return data.get("access_token"), data.get("user_id"), None
    except requests.exceptions.RequestException as e:
        error_message = "Login failed. Please check your credentials and ensure the backend is running."
        try:
            error_data = response.json()
            if 'detail' in error_data:
                error_message = f"Login failed: {error_data['detail']}"
            elif 'message' in error_data:
                 error_message = f"Login failed: {error_data['message']}"
        except Exception:
            pass
        return None, None, error_message

def signup_user(username, password):
    """Calls the FastAPI /auth/signup endpoint."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/signup",
            json={"username": username, "password": password}
        )
        response.raise_for_status()
        data = response.json()
        return True, data.get("message", "User registered successfully!"), None
    except requests.exceptions.RequestException as e:
        error_message = "Signup failed. Please ensure username is unique and try again."
        try:
            error_data = response.json()
            if 'detail' in error_data:
                error_message = f"Signup failed: {error_data['detail']}"
            elif 'message' in error_data:
                 error_message = f"Signup failed: {error_data['message']}"
        except Exception:
            pass
        return False, None, error_message

def logout_user():
    """Clears the session token."""
    st.session_state.pop("token", None)
    st.session_state.pop("user_id", None)
    st.session_state.pop("username", None)
    st.session_state.thread_list = []
    st.session_state.current_thread_id = None
    st.session_state.messages = []
    st.rerun()

# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────
initialize_session_state()

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-title">🤖 LG ChatBot</div>', unsafe_allow_html=True)

    # --- Authentication Section in Sidebar ---
    if not st.session_state.token:
        st.markdown("<h5 style='text-align: center; color: #888; margin-top: 1rem;'>Please Login</h5>", unsafe_allow_html=True)
        # Link to the main login/signup area if not already there
        # Optionally, embed mini forms here if desired, but main area is cleaner.
    else:
        # --- Chat Management ---
        if st.button("➕ New Chat", key="new_chat_button", use_container_width=True):
            new_thread_id = create_new_thread()
            if new_thread_id:
                # No need to rerun here, create_new_thread already sets current_thread_id and reruns
                pass
            else:
                # If creation failed, rerun to refresh state if necessary
                st.rerun()

        st.markdown('<div class="sidebar-section">Recent Chats</div>', unsafe_allow_html=True)

        # Fetch and display threads
        # Only fetch threads if token is available and list is empty or needs refresh
        if st.session_state.token and not st.session_state.thread_list:
            fetch_threads()

        # Display threads
        if st.session_state.thread_list:
            # Sort threads by ID (assuming ID can be converted to int for chronological order)
            # Or just display them as fetched if backend provides a meaningful order
            sorted_threads = sorted(st.session_state.thread_list, key=lambda x: int(x.get("id", 0)) if x.get("id", "").isdigit() else x.get("id", ""))

            for thread in reversed(sorted_threads): # Show newest first
                t_id = thread["id"]
                t_title = thread.get("chat_title", f"Chat {t_id}")
                is_active = t_id == st.session_state.current_thread_id

                css_class = "active-thread chat-history-btn" if is_active else "chat-history-btn"
                icon = "●" if is_active else "○"

                if st.button(f"{icon}  {t_title}", key=f"thread_{t_id}", use_container_width=True):
                    st.session_state.current_thread_id = t_id
                    st.session_state.messages = fetch_thread_messages(t_id) # Load messages for this thread
                    st.rerun()
        else:
             st.markdown("<div style='text-align: center; color: #555; font-size: 0.9rem; padding: 1rem;'>No chats yet. Start a new one!</div>", unsafe_allow_html=True)


    # --- Logout Button ---
    if st.session_state.token:
        st.markdown("---") # Separator
        if st.button("🚪 Logout", use_container_width=True):
            logout_user()


# ─────────────────────────────────────────────
# MAIN CHAT AREA
# ─────────────────────────────────────────────

# --- Authentication UI ---
if not st.session_state.token:
    st.markdown("<h1 style='text-align: center; color: white;'>LG ChatBot</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #888;'>Authentication</h3>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1]) # col2 will contain the forms

    with col2:
        tab1, tab2 = st.tabs(["Login", "Sign Up"])

        with tab1:
            st.markdown("##### Login")
            username_login = st.text_input("Username", key="login_username", placeholder="Enter your username")
            password_login = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
            
            if st.button("Login", key="login_button"):
                if username_login and password_login:
                    token, user_id, error = login_user(username_login, password_login)
                    if token:
                        st.session_state.token = token
                        st.session_state.user_id = user_id
                        st.session_state.username = username_login
                        st.success("Login successful!")
                        # Fetch threads and set initial state after login
                        fetch_threads()
                        if st.session_state.current_thread_id: # If threads were fetched
                             st.session_state.messages = fetch_thread_messages(st.session_state.current_thread_id)
                        else: # No threads, prepare for new chat
                             st.session_state.current_thread_id = str(uuid.uuid4())[:8] # Temp ID
                             st.session_state.messages = []
                        st.rerun()
                    else:
                        st.error(error)
                else:
                    st.warning("Please enter both username and password.")

        with tab2:
            st.markdown("##### Sign Up")
            username_signup = st.text_input("Username", key="signup_username", placeholder="Choose a unique username")
            password_signup = st.text_input("Password", type="password", key="signup_password", placeholder="Create a strong password")
            
            if st.button("Sign Up", key="signup_button"):
                if username_signup and password_signup:
                    success, message, error = signup_user(username_signup, password_signup)
                    if success:
                        st.success(message)
                        # Optionally, auto-login after signup
                        token, user_id, login_error = login_user(username_signup, password_signup)
                        if token:
                            st.session_state.token = token
                            st.session_state.user_id = user_id
                            st.session_state.username = username_signup
                            fetch_threads() # Fetch threads after login
                            if st.session_state.current_thread_id:
                                st.session_state.messages = fetch_thread_messages(st.session_state.current_thread_id)
                            else:
                                st.session_state.current_thread_id = str(uuid.uuid4())[:8] # Temp ID
                                st.session_state.messages = []
                            st.rerun()
                    else:
                        st.error(error)
                else:
                    st.warning("Please enter both username and password.")

# --- Chat Interface ---
else:
    # Display welcome message if logged in but no chat selected/loaded
    if not st.session_state.current_thread_id:
         st.markdown("<h1 style='text-align: center; color: white;'>Welcome!</h1>", unsafe_allow_html=True)
         st.markdown("<h3 style='text-align: center; color: #888;'>Select or create a new chat from the sidebar.</h3>", unsafe_allow_html=True)
         # Force a rerun to ensure sidebar is populated and a new chat is perhaps initiated if no threads exist
         if not st.session_state.thread_list: # If no threads loaded yet
             fetch_threads() # Fetch them
             if not st.session_state.thread_list: # Still no threads
                 st.session_state.current_thread_id = str(uuid.uuid4())[:8] # Set temporary ID
                 st.session_state.messages = []
                 st.rerun()
         st.stop() # Stop further execution until a thread is selected or created

    # --- Main Chat Area ---
    col1, center_col, col3 = st.columns([1, 6, 1]) # Use a central column for chat content

    with center_col:
        # Display Chat History
        if st.session_state.messages:
            st.markdown(f'<div style="text-align:center; padding: 0.5rem 0 1rem;"><span class="thread-badge">Thread #{st.session_state.current_thread_id}</span></div>', unsafe_allow_html=True)
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    # Display thoughts if available (assuming backend provides them)
                    if msg.get("thoughts"):
                        with st.expander("🧠 Thoughts"):
                            for thought in msg["thoughts"]:
                                st.markdown(f"- {thought}")
        else:
            st.markdown('<div style="text-align: center; font-size: 2rem; font-weight: 800; color: white; padding: 2rem;">How can I help you today?</div>', unsafe_allow_html=True)
            if st.session_state.current_thread_id: # Show thread ID even if no messages yet
                st.markdown(f'<div style="text-align:center; padding: 0.5rem 0 1rem;"><span class="thread-badge">Thread #{st.session_state.current_thread_id}</span></div>', unsafe_allow_html=True)


        # Chat Input
        user_input = st.chat_input("Type your message here...")

        if user_input and st.session_state.current_thread_id and st.session_state.token:
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # Send message to backend and display streaming response
            with st.chat_message("assistant"):
                # Call the streaming function
                message_placeholder = st.empty() # Create an empty container for the response
                
                # The send_chat_message function should yield chunks for st.write_stream
                full_response = ""
                # Assuming send_chat_message yields text chunks
                for chunk in send_chat_message(user_input, st.session_state.current_thread_id, st.session_state.user_id):
                    full_response += chunk
                    message_placeholder.markdown(full_response) # Update placeholder with aggregated response

                # After streaming is complete, we might want to process thoughts if backend provides them
                # This part requires a specific format from the backend for thoughts.
                # For now, we'll assume a simple text response.
                # If backend returns structured data like {"content": "...", "thoughts": [...]},
                # we would need to parse that from the stream and then append to messages.
                
                # A simple approach for now: if the response is not empty, add it to messages.
                # Extracting thoughts would require a more structured stream response from the backend.
                if full_response:
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    # Add thoughts if the backend provided them in a structured way after the stream
                    # For now, assuming no explicit thought extraction from stream.

            st.rerun() # Rerun to update the message history and clear input


# ─────────────────────────────────────────────
# Initial Load Logic (after authentication check)
# ─────────────────────────────────────────────
if st.session_state.token and st.session_state.current_thread_id is None:
    # If logged in but no thread is selected/loaded, try to load existing threads
    # or prepare for a new chat. This is handled within fetch_threads and initialization.
    # Rerunning once to ensure state is consistent.
    if not st.session_state.thread_list: # Fetch if not already fetched
        fetch_threads()
    if st.session_state.thread_list and st.session_state.current_thread_id is None: # If threads exist but none selected
        st.session_state.current_thread_id = st.session_state.thread_list[0]["id"] # Select first thread
        st.session_state.messages = fetch_thread_messages(st.session_state.current_thread_id)
        st.rerun()
    elif not st.session_state.thread_list and st.session_state.current_thread_id is None: # No threads, no current ID
        st.session_state.current_thread_id = str(uuid.uuid4())[:8] # Assign temporary ID for new chat
        st.session_state.messages = []
        st.rerun()

    
# To run this file:
# 1. Ensure you have streamlit, requests, and your backend running.
# 2. Run: streamlit run frountend.py
