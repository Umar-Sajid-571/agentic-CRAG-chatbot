from fastmcp import FastMCP
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain.schema import Document
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA # Potentially useful, but as_retriever is sufficient for now
import os
import re
import json
from typing import List, Dict, Optional, Any

# Assuming app.core.models has GraphState and AgentState, and app.tools.base_tools has BaseTool
# These imports are placeholders and might need adjustment based on actual file contents.
# We need RetrieverManager from app.core.retriever
from app.core.retriever import RetrieverManager # This import requires app/core/retriever.py to be in the Python path.

mcp = FastMCP('SmartAssistantTools')

# Instantiate RetrieverManager. It defaults to './chroma_db' for persistence.
# The user_id is derived from thread_id for isolation in this tool context.
retriever_manager = RetrieverManager(db_path="./chroma_db")

@mcp.tool()
def check_health() -> str:
    """Check if the MCP tool server is active."""
    return 'MCP Server is Online and Healthy'

@mcp.tool()
def calculator(first_num: float, second_num: float, operation: str) -> str:
    """Perform arithmetic: add, sub, mul, div."""
    if operation == 'add': result = first_num + second_num
    elif operation == 'sub': result = first_num - second_num
    elif operation == 'mul': result = first_num * second_num
    elif operation == 'div':
        if second_num == 0: return "Error: Division by zero"
        result = first_num / second_num
    else: return f"Error: Unknown operation {operation}"
    return str(result)

@mcp.tool()
def web_search(query: str) -> str:
    """Search the web for real-time information."""
    search = DuckDuckGoSearchResults()
    return search.run(query)

@mcp.tool()
def ingest_data(source: str, thread_id: str) -> str:
    """
    Load a PDF or URL and index it for a specific chat thread.
    Args:
        source: URL or local file path to the PDF.
        thread_id: Unique ID for the current user session.
    """
    # Use thread_id as user_id for isolation in RetrieverManager
    user_id = thread_id 
    documents: List[Document] = []
    
    try:
        if source.startswith("http://") or source.startswith("https://"):
            print(f"Loading data from URL: {source}")
            loader = WebBaseLoader(source)
            # WebBaseLoader returns Document objects
            documents = loader.load()
            metadata = {"source": source, "thread_id": thread_id}
        elif source.lower().endswith(".pdf"):
            print(f"Loading data from PDF file: {source}")
            if not os.path.exists(source):
                return f"Error: File not found at {source}"
            loader = PyPDFLoader(source)
            # PyPDFLoader returns Document objects, but we need to process them further
            # PyPDFLoader loads page by page, so we combine them if needed or process as is
            raw_documents = loader.load()
            documents = [
                Document(page_content=doc.page_content, metadata={"source": os.path.basename(source), "page": doc.metadata.get("page"), "thread_id": thread_id})
                for doc in raw_documents
            ]
            metadata = {"source": os.path.basename(source), "thread_id": thread_id}
        else:
            return f"Error: Unsupported source type for {source}. Please provide a URL or a .pdf file path."
        
        if not documents:
            return f"Error: No documents loaded from source {source}."
        
        # Call the existing logic from retriever.py
        # Ensure retriever_manager is instantiated with the correct path (it defaults to './chroma_db')
        ingest_success = retriever_manager.ingest_and_prepare_retriever(
            user_id=user_id,
            thread_id=thread_id,
            documents=documents,
            metadata_dict=metadata # Pass source and thread_id as common metadata
        )

        if ingest_success:
            return f"Ingestion complete for thread {thread_id}. Source: {source}"
        else:
            return f"Ingestion failed for thread {thread_id}. Source: {source}"
            
    except FileNotFoundError:
        return f"Error: The file {source} was not found."
    except Exception as e:
        print(f"An unexpected error occurred during ingestion: {e}")
        return f"Error during ingestion for thread {thread_id}: {e}"

@mcp.tool()
def query_documents(query: str, thread_id: str) -> str:
    """
    Retrieve relevant context from the indexed documents for a specific thread.
    Args:
        query: The user's question or search query.
        thread_id: Unique ID for the current user session.
    Returns:
        A string containing the relevant document contents, separated by '---'.
        Returns an error message if no documents are found or an issue occurs.
    """
    # Use thread_id as user_id for isolation in RetrieverManager
    user_id = thread_id
    
    try:
        # Get the retriever for the specific user and thread
        retriever = retriever_manager.get_retriever(user_id=user_id, thread_id=thread_id)
        
        if not retriever:
            return "No documents found for this thread. Please upload a file first."

        # Retrieve relevant documents
        # The retriever.get_relevant_documents expects a query string
        docs = retriever.get_relevant_documents(query)
        
        if not docs:
            return "No relevant documents found for your query in this thread."
        
        # Format the output
        return "
---
".join([d.page_content for d in docs])
        
    except Exception as e:
        print(f"An error occurred while querying documents: {e}")
        return f"An error occurred while retrieving documents for thread {thread_id}: {e}"

# Note: The original app/core/retriever.py had save_checkpoint and load_checkpoint methods.
# These are not directly exposed as MCP tools here, but are part of the RetrieverManager
# and could be called if needed by other parts of the application.
