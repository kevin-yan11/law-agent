"""Research sub-graph - handles legal Q&A with citations."""

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.agents.state import AusLawState
from app.db import supabase
from app.config import logger


llm = ChatOpenAI(model="gpt-4o", temperature=0)


async def retrieve_documents(state: AusLawState) -> dict:
    """Retrieve relevant legal documents using full-text search."""
    query = state["current_query"]
    user_state = state.get("user_state", "VIC")

    # Convert to tsquery format with OR logic
    search_terms = query.strip().split()
    tsquery = " | ".join(search_terms)

    logger.info(f"Research: searching for '{tsquery}'")

    try:
        response = supabase.table("legal_docs").select("*").text_search("search_vector", tsquery).execute()
        docs = response.data if response.data else []
        logger.info(f"Research: found {len(docs)} documents")
        return {"retrieved_docs": docs}
    except Exception as e:
        logger.error(f"Research retrieval error: {e}")
        return {"retrieved_docs": [], "error": str(e)}


async def generate_answer(state: AusLawState) -> dict:
    """Generate answer with citations based on retrieved documents."""
    docs = state.get("retrieved_docs", [])
    query = state["current_query"]
    user_state = state.get("user_state", "VIC")

    if not docs:
        return {
            "research_result": {
                "answer": "I couldn't find specific legislation in the database for your query. Please try rephrasing or ask about a different topic.",
                "citations": []
            }
        }

    # Format documents for the prompt
    docs_text = "\n\n".join([
        f"[{doc['metadata'].get('source', 'Unknown')} {doc['metadata'].get('section', '')}]:\n{doc['content']}"
        for doc in docs
    ])

    GENERATOR_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an Australian legal assistant. Answer the user's question based ONLY on the provided legal documents.

Rules:
1. Always cite the specific Act and Section when making a claim
2. Use format: "According to [Act Name] [Section]..." for citations
3. If the documents don't contain enough information, say so clearly
4. Be helpful but remind users this is not legal advice
5. Write in plain English, avoiding unnecessary jargon

User's state: {user_state}"""),
        ("human", "Question: {question}\n\nRelevant Legal Documents:\n{documents}\n\nAnswer:")
    ])

    result = await (GENERATOR_PROMPT | llm).ainvoke({
        "user_state": user_state,
        "question": query,
        "documents": docs_text
    })

    # Extract citations from documents
    citations = [
        {
            "source": doc["metadata"].get("source", "Unknown"),
            "section": doc["metadata"].get("section", ""),
            "snippet": doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"]
        }
        for doc in docs
    ]

    return {
        "research_result": {
            "answer": result.content,
            "citations": citations
        }
    }


def build_research_graph() -> StateGraph:
    """Construct the research sub-graph."""
    workflow = StateGraph(AusLawState)

    # Add nodes
    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("generate", generate_answer)

    # Add edges
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()


research_graph = build_research_graph()
