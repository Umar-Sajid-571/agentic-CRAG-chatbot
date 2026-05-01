import numpy as np

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt, Command


from langgraph.graph import StateGraph, START, END
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver

from retriver_sub_graph import create_crag_workflow, transform_from_subgraph
from retriver import ingest_and_prepare_retriever
from tools import calculator, search_tool
from models import ollama_model, or_model, embd_model

from typing import TypedDict, Annotated, List # Added List import
import sqlite3
import os

import psycopg2
from pgvector.psycopg2 import register_vector

# Import BackgroundTasks from fastapi
from fastapi import FastAPI, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

# Import security and state modules
from app.api.auth import get_current_user
from app.core.state import ChatBbot_Schema

# Import the new functions and existing graph components from LangGraph_Backend
from LangGraph_Backend import chatbot, init_memory_db_and_tables, all_previous_threads, process_memory, extract_fact, save_to_long_term_memory # Import process_memory and others

os.environ["LANGSMITH_PROJECT"] = "ChatBot Tracing"

# *****************************************Defining Schemas****************************************

class ChatBbot_Schema(TypedDict):
    messages : Annotated[list[BaseMessage], add_messages]
    summary: str # Added for memory summarization

# *****************************************Defining CheckPointers************************************
conn = sqlite3.connect(database="chat_history.db", check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_titles (
        thread_id TEXT PRIMARY KEY,
        title TEXT
    )
""")
conn.commit()

def save_chat_title(thread_id, title):
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    
    # Pehle check karein ke table bani hui hai ya nahi
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_titles (
            thread_id TEXT PRIMARY KEY, 
            title TEXT
        )
    """)
    
    # Ab insert karein
    cursor.execute("INSERT OR REPLACE INTO chat_titles (thread_id, title) VALUES (?, ?)", (thread_id, title))
    
    conn.commit()
    conn.close()

# *****************************************Postgres Long-term Memory Setup**************************
def get_mem_connection():
    conn = psycopg2.connect("postgresql://postgres:12345678@localhost:5432/postgres")
    return conn

# Table setup for Long-term Memory
def init_memory_db():
    conn = get_mem_connection()
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector") # This line ensures vector extension is enabled

    cur.execute("""
        CREATE TABLE IF NOT EXISTS long_term_memory (
            id SERIAL PRIMARY KEY,
            content TEXT,
            embedding vector(1024), 
            user_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# *****************************************Memory Tool**********************************************
@tool
def save_user_fact(fact: str, config: RunnableConfig):
    """Saves a specific fact or preference about the user for future sessions."""
    # Extract user/thread id from config if needed
    user_id = config.get("configurable", {}).get("user_id", "global_user")
    
    # Generate Embedding
    vector = embd_model.embed_query(fact)
    
    conn = get_mem_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO long_term_memory (content, embedding, user_id) VALUES (%s, %s, %s)",
        (fact, vector, user_id)
    )
    conn.commit()
    conn.close()
    return "Memory Updated"

# *****************************************Memory Retrieval Node************************************
def fetch_relevant_memories(query: str, user_id: str):
    query_vector = embd_model.embed_query(query)
    
    conn = get_mem_connection()
    cur = conn.cursor()
    register_vector(conn) # Vector handling register karein
    
    # Cosine Similarity check (<=> operator)
    cur.execute("""
        SELECT content FROM long_term_memory 
        WHERE user_id = %s 
        ORDER BY embedding <=> %s 
        LIMIT 3
    """, (user_id, np.array(query_vector)))
    
    results = cur.fetchall()
    conn.close()
    return [r[0] for r in results]


# *****************************************Defining Nodes*******************************************

def transform_to_subgraph(state: ChatBbot_Schema):
    """Main state se data nikal kar Subgraph ko dena"""
    # Last user message ko query banao
    last_user_msg = [m.content for m in state["messages"] if isinstance(m, HumanMessage)][-1]
    return {
        "query": last_user_msg,
        "loop_step": 0,
        "documents": []
    }

crag_workflow = create_crag_workflow(checkpointer=checkpointer)
@tool    
def ask_question(query: str, config: RunnableConfig) -> str:
    """
    Retrieves highly relevant context from the previously processed 
    document or website to answer user questions accurately.
    """

    sub_state = {
        "query": query,
        "loop_step": 0,
        "documents": []
    }
    result = crag_workflow.invoke(sub_state, config=config)
    return transform_from_subgraph(result)
        

tools = [ingest_and_prepare_retriever, calculator, search_tool, ask_question, save_user_fact]
llm = or_model.bind_tools(tools)
tool_node = ToolNode(tools)

def summarize_conversation(state: ChatBbot_Schema, config: RunnableConfig) -> ChatBbot_Schema:
    """
    Summarizes older conversation messages if the history is too long.
    Keeps the last 3-4 messages for immediate context.
    """
    if len(state["messages"]) > 6:
        # Keep the last 4 messages for immediate context, summarize the rest
        messages_to_summarize = state["messages"][:-4] 
        
        # Construct a prompt for summarization
        summary_prompt_messages = [
            SystemMessage(content="You are a helpful assistant that summarizes conversations. Please provide a concise summary of the following chat history. Focus on key decisions, actions, and outcomes. Output only the summary."),
            *messages_to_summarize
        ]
        
        try:
            # Invoke the summarization model
            summary_response = ollama_model.invoke(summary_prompt_messages, config=config)
            
            # Extract the summary text
            if isinstance(summary_response, BaseMessage):
                summary_text = summary_response.content
            else: # If it's a string directly
                summary_text = str(summary_response)
                
            state["summary"] = summary_text
            
            # Remove older messages, keeping only the last 4
            state["messages"] = state["messages"][-4:]
            
            print(f"Conversation summarized. Keeping last 4 messages. Summary: {summary_text[:50]}...") # For debugging
            
        except Exception as e:
            print(f"Error during summarization: {e}")
            state["summary"] = f"Error summarizing conversation: {e}"
            # If summarization fails, we keep the messages as they are for now.
    else:
        # If less than 6 messages, no summarization needed. Ensure summary field exists.
        if "summary" not in state or not state.get("summary"):
             state["summary"] = "" # Initialize summary if it's not present or empty
        
    return state

def chat_node(state: ChatBbot_Schema, config: RunnableConfig):
    messages = state["messages"] # These are the few messages remaining after summarization
    
    # Get the summary from the state
    conversation_summary = state.get("summary", "")
    
    # Extract user_id for memory retrieval
    user_id = config.get("configurable", {}).get("user_id", "global_user")
    
    # Fetch memories relevant to the current query
    # Ensure there's a message to get content from before accessing index
    last_query = ""
    if messages and isinstance(messages[-1], HumanMessage):
        last_query = messages[-1].content # This is the current user query after potential pruning
    
    past_memories = fetch_relevant_memories(last_query, user_id)

    # Construct the final messages for LLM invocation
    final_messages_for_llm = []
    
    # Add summary as a system message
    if conversation_summary:
        final_messages_for_llm.append(SystemMessage(content=f"Summary of previous conversation: {conversation_summary}"))

    # Add relevant memories from long-term storage
    if past_memories:
        for memory in past_memories:
            final_messages_for_llm.append(SystemMessage(content=f"Relevant User Memory: {memory}"))
            
    # Add the current conversation messages (which are already pruned if summarization happened)
    final_messages_for_llm.extend(messages)

    # Invoke the main LLM
    response = llm.invoke(final_messages_for_llm, config=config) 
    
    # The chat_node should return a dictionary that gets merged into the state.
    # The 'add_messages' sorter in ChatBbot_Schema will handle appending this response.
    return {"messages": [response]}

# *****************************************Defining Graph********************************************
graph = StateGraph(ChatBbot_Schema)

# *****************************************Defining Nodes********************************************
graph.add_node("summarize_conversation", summarize_conversation) # Add the new summarization node
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

# *****************************************Defining Edges********************************************
# Update the graph flow: START -> summarize_conversation -> chat_node
graph.add_edge(START, "summarize_conversation") 
graph.add_edge("summarize_conversation", "chat_node")

# The conditional edges for tools remain attached to chat_node, as it's the node that might produce a tool call.
graph.add_conditional_edges(
    "chat_node",
    tools_condition,
)
graph.add_edge("tools", "chat_node")

# *****************************************Compiling Graph and Defining Exportables*******************************************

# The compiled graph object that will be imported by main.py
chatbot = graph.compile(checkpointer=checkpointer, interrupt_before=["tools"])

# Function to initialize memory DB (needed on app startup)
def init_memory_db_and_tables():
    init_memory_db()
    print("Postgres Long-term Memory Initialized!")

# Function to get chat history
def all_previous_threads():
    thread_list = []
    conn = sqlite3.connect("chat_history.db")
    cursor = conn.cursor()
    
    # Ensure chat_titles table exists before querying
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_titles (
            thread_id TEXT PRIMARY KEY, 
            title TEXT
        )
    """)
    
    # Checkpoints table might not exist if no checkpoints are saved yet.
    # We should check for its existence or handle the case where it's not found.
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints';")
        if cursor.fetchone():
            # If checkpoints table exists, perform the join
            cursor.execute("""
                SELECT DISTINCT c.thread_id, t.title 
                FROM checkpoints c
                LEFT JOIN chat_titles t ON c.thread_id = t.thread_id
            """)
            threads = cursor.fetchall()
        else:
            # If checkpoints table does not exist, query only chat_titles
            # This might happen if titles were saved before any checkpoints were made.
            cursor.execute("SELECT thread_id, title FROM chat_titles")
            threads = cursor.fetchall()
            
    except sqlite3.OperationalError as e:
        print(f"Error accessing database tables: {e}")
        # If there's an error (e.g., table doesn't exist), return empty list or handle gracefully
        threads = []

    for t_id, title in threads:
        # Agar title null hai to default name de do
        display_title = title if title else f"Thread {t_id}"
        thread_list.append({"id": t_id, "chat_title": display_title})
        
    conn.close()
    return thread_list

# Note: The 'if __name__ == "__main__":' block has been removed.
# The app instantiation and running logic should now be handled in app/main.py.
