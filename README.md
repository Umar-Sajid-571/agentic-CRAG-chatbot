# 🤖 LG ChatBot

An advanced, intelligent conversational agent built with LangGraph and LangChain. Created by Umar Farooq , this project implements a Corrective Retrieval-Augmented Generation (CRAG) architecture , multi-tiered memory management , and a modern Streamlit frontend.

## 🌟 Key Features
**Advanced Hybrid Retrieval Pipeline:** Integrates multiple retrieval strategies for high precision and recall, combining Vector Search with Maximal Marginal Relevance (MMR), BM25 keyword search, and Multi-Query Retrieval (MQR). The ensemble system weights BM25 at 0.4 and MQR at 0.6.

**Post-Retrieval Reranking:** Utilizes `FlashrankRerank` through a Contextual Compression Retriever to surface the top 4 most relevant document chunks.

**Corrective RAG (CRAG) Logic:** Features an intelligent grading node that evaluates document relevance (scoring as 'yes', 'web_search', 'refine', or 'no'). It dynamically rewrites vague queries or triggers a DuckDuckGo web search if local context is insufficient.

* **Multi-Tiered Memory Management:**

**Short-Term Memory:** Implements SQLite via `SqliteSaver` to maintain chat history, session states, and dynamically generated thread titles.
**Long-Term Memory:** Uses PostgreSQL with the `pgvector` extension to save specific user facts, retrieving them across sessions using cosine similarity.

**Human-in-the-Loop (HITL):** Incorporates a safety and approval mechanism within the UI, pausing the graph and requiring the user to explicitly approve or reject the indexing of new documents.

**Dynamic Document Ingestion:** Processes both web URLs and PDF files using a sophisticated hybrid splitting approach that combines `RecursiveCharacterTextSplitter` and `SemanticChunker` before indexing them into ChromaDB.

**Integrated Tool Suite:** Empowers the LLM with actionable tools, including a calculator for basic arithmetic (addition, subtraction, multiplication, division) , a real-time web search tool , and a dedicated fact-saving tool for memory retention.


## 🛠️ Technical Stack

**Large Language Models (LLMs):** `qwen2.5:0.5b` via Ollama and `stepfun/step-3.5-flash:free` via OpenRouter for reasoning and structured tool calling.

**Embeddings:** `mxbai-embed-large:latest` powered by Ollama Embeddings.

**Frameworks & Orchestration:** LangChain, LangGraph.

**Vector Store & Databases:** ChromaDB for local document vectors , SQLite for thread check-pointing , and PostgreSQL for persistent long-term vector storage.
 
**User Interface:** Streamlit (custom-styled for a ChatGPT-like experience with an expandable "Thoughts" view for system reasoning).



## 🧠 System Architecture Overview

The backend operates as a stateful graph (`StateGraph`) that routes the user query through several intelligent nodes:

1. **Retrieve Node:** Fetches documents from the ChromaDB hybrid pipeline.


2. **Grade Docs Node:** An LLM critically evaluates the context. If the context is complete, it finalizes the response; if incomplete, it routes to web search; if vague, it routes to a query refiner.


3. **Web Search / Rewrite Nodes:** Augments missing data via DuckDuckGo or optimizes the user's initial prompt for better semantic matching.


4. **Tool Node:** Executes necessary operations (calculating, saving memory, ingesting PDFs) based on structured LLM outputs.


