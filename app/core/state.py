from typing import Annotated, Sequence, TypedDict, Literal, List
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.types import interrupt
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.tools import tool
from langgraph.graph.message import add_messages

# *****************************************Defining Schemas****************************************

class ChatBbot_Schema(TypedDict):
    messages : Annotated[list[BaseMessage], add_messages]
    summary: str # Added for memory summarization

# *****************************************Defining GraphState****************************************
class GraphState(TypedDict):
    query: str
    documents: List[str]
    relevance: str
    context_hint: str
    loop_step: int
    review_result: str