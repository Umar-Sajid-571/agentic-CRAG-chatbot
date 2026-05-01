from langchain_ollama import ChatOllama
from langchain_openrouter import ChatOpenRouter
from langchain_ollama import OllamaEmbeddings
from dotenv import load_dotenv

from pydantic import BaseModel, Field
from typing import Literal

load_dotenv()

# *****************************************Ollama Model****************************************

ollama_model = ChatOllama(model="qwen2.5:0.5b")

# ***************************************** Embedding Model ****************************************

embd_model = OllamaEmbeddings(model="mxbai-embed-large:latest")

# *****************************************OpenRouter Model****************************************

from langchain_core.prompts import ChatPromptTemplate
from typing import List

or_model = ChatOpenRouter(
    model="stepfun/step-3.5-flash:free",
    max_tokens=1024,
    # api_key="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", 
    # base_url="https://openrouter.ai/api/v1"
)

# **************************************-- OpenRouter Model --*************************************

class GradeDocuments(BaseModel):
    """Assess context and search strategy."""
    binary_score: Literal["yes", "web_search", "refine", "no"] = Field(
        description="'yes': Fully answered. 'web_search': Insufficient/outdated. Provide 8-10 keywords in 'search_hint'. 'refine': Query too vague. 'no': Irrelevant."
    )
    search_hint: str = Field(description="8-10 keywords if 'web_search', else empty.")
    reasoning: str = Field(description="Brief logic.")

system_msg = """Grade 'Document' vs 'Question':
- 'yes': Fully answered.
- 'web_search': Relevant but needs more/newer info. Provide 8-10 keywords in 'search_hint'.
- 'refine': Query too vague.
- 'no': Irrelevant.
Focus keywords on missing specific entities or facts."""

grader_prompt = ChatPromptTemplate.from_messages([
    ("system", system_msg),
    ("human", "Q: {question} 
Doc: {document}")
])
grader_model = grader_prompt | or_model.with_structured_output(GradeDocuments)


# **************************************-- OpenRouter Model --*************************************

class RefinedQuery(BaseModel):
    """Rewrite the search query to be more specific based on missing information."""
    original_query: str = Field(description="The initial user query.")
    refined_query: str = Field(description="The newly optimized and specific search string.")

refiner_system_msg = """You are a Precision Query Optimizer.
Your task is to analyze an 'Original Query' and 'Incomplete Context' to create a surgically precise search query.

Guidelines:
- Identify information gaps in the current context.
- Ensure the 'refined_query' is optimized for vector search or keyword retrieval in context of documents.
- Focus on the core intent of the original question."""

refiner_prompt = ChatPromptTemplate.from_messages([
    ("system", refiner_system_msg),
    ("human", "Original Query: {query} 

 Incomplete Context Found: {context}")
])

query_refiner_model = refiner_prompt | or_model.with_structured_output(RefinedQuery)


# **************************************-- route_decider Model --*************************************

class StepController(BaseModel):
    """Determine the next step based on the user's query."""
    
    action: Literal[
        "ingest_and_prepare_retriever",
        "ask_question",
        "calculator",
        "search_tool",
        "task_complete"
    ] = Field(description="The specific next action to take.")
    
    reasoning: str = Field(description="""Choose exactly one of these steps:
        1. 'ingest_and_prepare_retriever': Use if the user provides a new document, URL, or data that needs to be indexed.
        2. 'ask_question': Use if a retriever already exists and the user is asking about the content of those documents.
        3. 'calculator': Use if the query involves any math, formulas, or numerical calculations.
        4. 'search_tool': Use if the query requires real-time information from the internet or facts not found in local documents.
        5. 'task_complete' : Select this ONLY if the user's query is fully answered.""")

route_decider = ollama_model.with_structured_output(StepController)
