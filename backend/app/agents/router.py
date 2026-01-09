"""Intent router - classifies user queries into different branches."""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Literal

from app.config import logger


class IntentClassification(BaseModel):
    """Classification of user intent."""
    intent: Literal["research", "action", "match", "clarify", "general"] = Field(
        description="The primary intent of the user's message"
    )
    confidence: float = Field(
        ge=0, le=1,
        description="Confidence score for the classification"
    )
    reasoning: str = Field(
        description="Brief explanation of why this intent was chosen"
    )


ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an intent classifier for an Australian legal AI assistant.

Classify the user's message into one of these intents:

1. **research**: User wants to understand law, rights, or legal concepts
   - Examples: "What are my rights as a tenant?", "Can my landlord enter without notice?"

2. **action**: User wants to DO something - a process, procedure, or task
   - Examples: "How do I get my bond back?", "I want to break my lease", "Help me prepare documents"

3. **match**: User wants to find or connect with a lawyer
   - Examples: "I need a lawyer", "Can you recommend a solicitor for employment issues?"

4. **clarify**: The message is ambiguous or you need more information
   - Examples: Single words like "bond", unclear pronouns, incomplete questions

5. **general**: General chat, greetings, or off-topic
   - Examples: "Hello", "Thanks", "What can you do?"

Current user state: {user_state}
"""),
    ("human", "{query}")
])


class MasterRouter:
    """Routes user queries to appropriate sub-graphs."""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.chain = ROUTER_PROMPT | self.llm.with_structured_output(IntentClassification)

    async def classify(self, query: str, user_state: str | None) -> IntentClassification:
        """Classify the user's intent."""
        logger.info(f"Classifying intent for query: '{query[:50]}...'")
        result = await self.chain.ainvoke({
            "query": query,
            "user_state": user_state or "Unknown"
        })
        logger.info(f"Intent classified as: {result.intent} (confidence: {result.confidence})")
        return result


# Singleton instance
router = MasterRouter()
