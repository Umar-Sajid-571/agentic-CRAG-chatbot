import os
import uuid
# Assuming 'chromadb' is used for vector stores and 'pydantic' for models
import chromadb
from pydantic import BaseModel, Field

# Import necessary models and tools from the app structure
# Assuming these exist or will be created in app/core/models.py and app/tools/base_tools.py respectively
from app.core.models import GraphState, AgentState # Example models
from app.tools.base_tools import BaseTool # Example base tool

class RetrieverManager:
    """
    Manages retrieval operations, including vector store persistence and checkpointers.
    Vector stores and checkpointers are isolated per user and thread.
    """
    def __init__(self, db_path: str = "./chroma_db"):
        self.db_path = db_path
        # Initialize ChromaDB client (or other vector store client)
        # We won't initialize the client here directly, but rather when needed per path.
        # This allows for dynamic path creation.

    def _get_persist_path(self, user_id: str, thread_id: str) -> str:
        """
        Generates an isolated persistence path for vector stores and checkpointers.
        Path format: ./chroma_db/{user_id}/{thread_id}/
        """
        if not user_id:
            raise ValueError("user_id cannot be empty for persistence path.")
        if not thread_id:
            raise ValueError("thread_id cannot be empty for persistence path.")
        
        return os.path.join(self.db_path, user_id, thread_id)

    def _get_vector_store(self, user_id: str, thread_id: str, collection_name: str = "documents"):
        """
        Gets or creates a ChromaDB vector store client for a specific user and thread.
        """
        persist_directory = self._get_persist_path(user_id, thread_id)
        # Ensure the directory exists
        os.makedirs(persist_directory, exist_ok=True)
        
        client = chromadb.PersistentClient(path=persist_directory)
        
        # Get or create the collection
        try:
            collection = client.get_collection(name=collection_name)
        except: # If collection doesn't exist
            collection = client.create_collection(name=collection_name)
        
        return collection

    def ingest_and_prepare_retriever(self, user_id: str, thread_id: str, documents: list[dict], metadata: dict):
        """
        Ingests documents into the isolated vector store and prepares the retriever.
        'documents' is expected to be a list of dicts, e.g., [{'content': '...', 'metadata': {...}}]
        'metadata' could contain common info like source, etc.
        """
        if not user_id or not thread_id:
            print("Warning: User ID or Thread ID missing. Cannot ingest to isolated vector store.")
            return None

        try:
            collection = self._get_vector_store(user_id, thread_id)
            
            # Prepare data for ChromaDB
            texts = [doc['content'] for doc in documents]
            doc_metadatas = [
                {**doc.get('metadata', {}), **metadata} # Merge with common metadata
                for doc in documents
            ]
            ids = [str(uuid.uuid4()) for _ in documents]

            collection.add(
                documents=texts,
                metadatas=doc_metadatas,
                ids=ids
            )
            print(f"Ingested {len(documents)} documents for user {user_id}, thread {thread_id} into collection '{collection.name}'.")
            
            # In a real scenario, you might return a retriever object here,
            # e.g., from LangChain, configured with this vector store.
            # For now, we'll just confirm ingestion.
            return collection # Returning collection for potential further use

        except Exception as e:
            print(f"Error during document ingestion for user {user_id}, thread {thread_id}: {e}")
            return None

    # Placeholder for checkpointer logic, similar isolation could be applied
    def _get_checkpoint_path(self, user_id: str, thread_id: str) -> str:
        """Generates an isolated persistence path for checkpointers."""
        if not user_id or not thread_id:
            raise ValueError("user_id and thread_id are required for checkpoint path.")
        return os.path.join(self.db_path, user_id, thread_id, "checkpoints")

    def save_checkpoint(self, user_id: str, thread_id: str, state: AgentState):
        """Saves the current state as a checkpoint, isolated by user and thread."""
        checkpoint_dir = self._get_checkpoint_path(user_id, thread_id)
        os.makedirs(checkpoint_dir, exist_ok=True)
        # Save state logic here (e.g., serialize to JSON, pickle, etc.)
        # Example: using a simple file save
        checkpoint_file = os.path.join(checkpoint_dir, "latest_state.json")
        try:
            with open(checkpoint_file, 'w') as f:
                # Assuming AgentState can be serialized to JSON.
                # If not, a different serialization method (like pickle) would be needed.
                f.write(AgentState.model_dump_json(indent=2)) 
            print(f"Checkpoint saved for user {user_id}, thread {thread_id} at {checkpoint_file}")
        except Exception as e:
            print(f"Error saving checkpoint for user {user_id}, thread {thread_id}: {e}")

    def load_checkpoint(self, user_id: str, thread_id: str) -> AgentState | None:
        """Loads the latest checkpoint for a given user and thread."""
        checkpoint_dir = self._get_checkpoint_path(user_id, thread_id)
        checkpoint_file = os.path.join(checkpoint_dir, "latest_state.json")
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, 'r') as f:
                    state_data = json.load(f) # Assuming json serialization
                # Load data back into AgentState model
                return AgentState(**state_data) # Requires AgentState to be Pydantic model
            except Exception as e:
                print(f"Error loading checkpoint for user {user_id}, thread {thread_id}: {e}")
                return None
        return None

# --- Example usage context (for clarity, not part of the class itself) ---
# In your LangGraph application, you would instantiate RetrieverManager:
# retriever_manager = RetrieverManager(db_path="./chroma_db")
#
# To ingest data:
# user_id = "user123"
# thread_id = "threadabc"
# documents_to_ingest = [
#     {"content": "This is the first document.", "metadata": {"source": "doc1.txt"}},
#     {"content": "This is the second document.", "metadata": {"source": "doc2.txt"}}
# ]
# common_metadata = {"user_id": user_id, "thread_id": thread_id} # Can be passed to isolation
# retriever_manager.ingest_and_prepare_retriever(user_id, thread_id, documents_to_ingest, common_metadata)
#
# To save state:
# current_state = AgentState(steps=["step1", "step2"], output="result") # Example state
# retriever_manager.save_checkpoint(user_id, thread_id, current_state)
#
# To load state:
# loaded_state = retriever_manager.load_checkpoint(user_id, thread_id)
# if loaded_state:
#     print("Loaded state:", loaded_state)

