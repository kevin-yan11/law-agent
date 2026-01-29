# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AusLaw AI - An Australian Legal Assistant MVP that provides legal information, lawyer matching, step-by-step checklists, and document analysis for legal procedures across Australian states/territories.

## Architecture

```
Frontend (Next.js)  →  /api/copilotkit  →  FastAPI Backend  →  Supabase
     ↓                      ↓                    ↓
CopilotChat         HttpAgent proxy      Custom LangGraph
+ StateSelector     (AG-UI protocol)     (CopilotKitState)
+ FileUpload                                   ↓
+ useCopilotReadable              Tools: lookup_law, find_lawyer,
                                  generate_checklist, analyze_document
```

**Frontend**: Next.js 14 + CopilotKit + shadcn/ui + Tailwind CSS
**Backend**: FastAPI + LangGraph + langchain-openai (GPT-4o)
**Database**: Supabase PostgreSQL with pgvector for RAG
**Storage**: Supabase Storage for document uploads

## Development Commands

### Backend (requires conda environment `law_agent`)
```bash
cd backend
conda activate law_agent
python main.py                    # Start server on localhost:8000
```

### Frontend
```bash
cd frontend
npm run dev                       # Start dev server on localhost:3000
npm run build
npm run lint
```

### Data Ingestion (RAG)
```bash
cd backend
python scripts/ingest_corpus.py --limit 10              # Test with 10 docs
python scripts/ingest_corpus.py --dry-run               # Preview without changes
python scripts/ingest_corpus.py --batch-size 500        # Full ingestion (~6000 docs, optimized)
```

### RAG Evaluation
```bash
cd backend
python scripts/eval_rag.py              # Auto-generate test cases from DB
python scripts/eval_rag.py --verbose    # Show detailed results per case
python scripts/eval_rag.py --stats      # Show DB statistics first
python scripts/eval_rag.py --static     # Use hardcoded test cases instead
```

### Testing
```bash
cd backend
conda activate law_agent
pytest                                   # Run all tests
pytest tests/test_url_fetcher.py -v     # Run specific test file
pytest -k "ssrf" -v                      # Run tests matching pattern
```

### Database
Run SQL files in Supabase SQL Editor:
- `database/setup.sql` - Initial schema and mock data
- `database/migration_v2.sql` - Adds action_templates table and state column
- `database/migration_rag.sql` - pgvector schema for RAG (legislation_documents, legislation_chunks, hybrid_search function)

## Environment Variables

Backend `.env` file in `/backend`:
```
SUPABASE_URL=
SUPABASE_KEY=
OPENAI_API_KEY=
COHERE_API_KEY=              # Optional: for reranking (gracefully degrades if not set)
ALLOWED_DOCUMENT_HOSTS=      # Required: your Supabase domain (e.g., your-project.supabase.co)
```

Frontend `.env.local` file in `/frontend`:
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
BACKEND_URL=http://localhost:8000    # For production: set to deployed backend URL
```

## Key Architecture Decisions

### RAG System (Advanced Retrieval)
The `lookup_law` tool uses a hybrid retrieval pipeline:
1. **Hybrid Search**: Vector similarity (pgvector) + PostgreSQL full-text search
2. **RRF Fusion**: Reciprocal Rank Fusion merges results from both search methods
3. **Reranking**: Optional Cohere rerank for final precision (falls back to RRF if not configured)
4. **Parent-Child Chunks**: Child chunks (500 tokens) for precise retrieval, parent chunks (2000 tokens) for context

**Data Source**: Hugging Face `isaacus/open-australian-legal-corpus` (Primary Legislation only)
**Supported Jurisdictions**: NSW, QLD, FEDERAL (no Victoria data in corpus)

### CopilotKit Context Passing
The agent uses a **custom StateGraph** (not `create_react_agent`) to properly read frontend context:
- Frontend uses `useCopilotReadable` to share user's selected state and uploaded document URL
- Backend inherits from `CopilotKitState` and reads `state["copilotkit"]["context"]`

**CopilotKit/AG-UI Bug Workaround**: The AG-UI protocol double-serializes string values, causing context values to arrive with extra quotes (e.g., `"\"NSW\""` instead of `"NSW"`). The `clean_context_value()` function in both `adaptive_graph.py` and `conversational_graph.py` handles this by:
1. Stripping outer quotes if value starts and ends with `"`
2. Unescaping inner quotes (`\"` → `"`)

This bug affects both `emit-messages` config keys (must set both `copilotkit:emit-messages` and `emit-messages`) and context string values.

### Suppressing Internal LLM Streaming

**Problem**: When making internal LLM calls (e.g., for classification, analysis, or generating quick replies), the AG-UI protocol streams their output as raw JSON to the chat UI. This appears during processing and disappears when complete, causing confusing UX.

**Solution**: Use `get_internal_llm_config(config)` from `app/agents/utils/config.py` for ALL internal LLM calls that shouldn't be streamed to the user.

```python
from app.agents.utils import get_internal_llm_config

async def my_node(state: State, config: RunnableConfig) -> dict:
    # Use internal config to suppress streaming
    internal_config = get_internal_llm_config(config)

    # This LLM call won't stream to the chat UI
    result = await llm.ainvoke(prompt, config=internal_config)
```

**When to use `get_internal_llm_config`**:
- Safety classification LLM calls
- Quick reply generation
- Complexity routing decisions
- Any structured output that shouldn't appear in chat

**When NOT to use it**:
- The main chat response (should stream to user)
- Tool results that the user should see

### State-Based Legal Information
Australian law varies by state. The `StateSelector` component lets users pick their state (VIC, NSW, QLD, etc.), which is passed to all tool calls automatically. For unsupported states (VIC, SA, WA, TAS, NT), the system falls back to Federal law.

### Document Upload Flow
Files are uploaded to Supabase Storage (not backend memory) for persistence:
1. Frontend uploads to Supabase Storage bucket `documents`
2. Public URL shared with agent via `useCopilotReadable`
3. Agent calls `analyze_document(document_url=...)`
4. Tool fetches file from URL, parses it, returns text for agent to analyze

## Backend Structure

```
backend/
├── main.py                 # FastAPI app, graph selection (conversational vs adaptive)
├── pytest.ini              # Pytest configuration
├── app/
│   ├── config.py           # Environment variables, logging
│   ├── db/supabase_client.py
│   ├── agents/
│   │   ├── conversational_state.py   # Simple state for chat mode
│   │   ├── conversational_graph.py   # Fast 3-node conversational graph (DEFAULT)
│   │   ├── adaptive_state.py         # Complex state for adaptive mode
│   │   ├── adaptive_graph.py         # 14-node adaptive pipeline
│   │   ├── stages/
│   │   │   ├── safety_check_lite.py  # Fast keyword-first safety check
│   │   │   ├── chat_response.py      # ReAct agent with tools + quick replies
│   │   │   ├── safety_gate.py        # Full LLM safety check (adaptive mode)
│   │   │   └── ...                   # Other adaptive stages
│   │   ├── routers/
│   │   │   ├── safety_router.py      # LLM-based safety classification
│   │   │   └── complexity_router.py  # Simple/complex path routing
│   │   └── schemas/
│   │       ├── emergency_resources.py # Crisis hotlines by state
│   │       └── ...
│   ├── services/           # RAG services
│   │   ├── embedding_service.py   # OpenAI text-embedding-3-small
│   │   ├── hybrid_retriever.py    # Vector + FTS + RRF fusion
│   │   └── reranker.py            # Cohere reranker (optional)
│   ├── tools/
│   │   ├── lookup_law.py       # RAG-based legal search (ALWAYS use for legal refs)
│   │   ├── find_lawyer.py      # Filter by location/specialty
│   │   ├── generate_checklist.py  # LLM-generated or template-based
│   │   └── analyze_document.py # Fetch & parse docs for agent analysis
│   └── utils/
│       ├── document_parser.py  # PDF, DOCX, image parsing
│       └── url_fetcher.py      # Fetch documents from URLs
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── test_conversational_mode.py  # Conversational graph tests (15 tests)
│   ├── test_safety_gate.py      # Safety gate tests (16 tests)
│   ├── test_url_fetcher.py      # SSRF protection tests
│   └── test_lookup_law.py       # RAG tool tests
├── scripts/
│   ├── ingest_corpus.py    # Hugging Face dataset ingestion (batch inserts)
│   └── eval_rag.py         # RAG retrieval quality evaluation
```

## Database Schema

### Original Tables (mock data)
- **legal_docs**: `id`, `content`, `metadata` (JSONB), `state`, `search_vector` (tsvector)
- **lawyers**: `id`, `name`, `specialty`, `location`, `rate`
- **action_templates**: `id`, `state`, `category`, `title`, `keywords` (array), `steps` (JSONB)

### RAG Tables (real legislation)
- **legislation_documents**: `id`, `version_id`, `citation`, `jurisdiction`, `source_url`, `full_text`
- **legislation_chunks**: `id`, `document_id`, `parent_chunk_id`, `content`, `embedding` (vector 1536), `chunk_type`, `content_tsv` (tsvector)

### Key SQL Function
`hybrid_search(query_embedding, query_text, filter_jurisdiction, match_count)` - Performs combined vector + keyword search with automatic handling of parent-only chunks (small documents).

## Chunking Strategy

| Document Size | Strategy |
|--------------|----------|
| < 10K chars | Parent chunks only (no children) |
| >= 10K chars | Parent (2000 tokens) + Child (500 tokens) chunks |

Retrieval uses child chunks for precision, then fetches parent chunk for fuller context.

### Ingestion Performance
The ingestion script uses batch inserts for chunks (all parent chunks in one INSERT, all child chunks in another) rather than individual inserts. Use `--batch-size 500` for optimal embedding API throughput. Full ingestion of ~6000 docs takes approximately 6-8 hours.

## Frontend Structure

```
frontend/
├── app/
│   ├── page.tsx                # Main page with CopilotChat integration
│   ├── layout.tsx              # Root layout with CopilotKit provider
│   ├── globals.css             # Tailwind + shadcn CSS variables
│   ├── components/
│   │   ├── StateSelector.tsx   # Australian state/territory dropdown
│   │   └── FileUpload.tsx      # Supabase Storage upload component
│   └── api/copilotkit/route.ts # Proxy to FastAPI backend
├── components/ui/              # shadcn/ui components (Card, Alert, Button, etc.)
├── lib/utils.ts                # shadcn cn() utility
└── components.json             # shadcn configuration
```

### Adding shadcn Components
```bash
cd frontend
npx shadcn@latest add <component-name>
```

## Code Style

- All comments and documentation must be in English
- After completing code changes, generate a commit message summarizing the changes

---

## Adaptive Agent Workflow (Complete)

### Overview
Transforming the agent from a simple chat↔tools loop into an **8-stage professional legal workflow** with **adaptive depth routing** - simple queries stay fast, complex queries get full analysis.

### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│  [0] SAFETY GATE (always runs)                              │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ESCALATE        SIMPLE PATH     COMPLEX PATH
        (high-risk)      (~3k tokens)    (~9k tokens)
              │               │               │
              ▼               ▼               ▼
         Crisis           [1] Issue ID    [1] Issue ID
         Resources        [2] Jurisdiction [2] Jurisdiction
                          [7] Strategy    [3] Fact Structure
                                          [4] Elements Map
                                          [5] Case Precedent
                                          [6] Risk Analysis
                                          [7] Strategy
                                          [8] Escalation Brief
```

### Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | Safety gate foundation (adaptive_state, emergency_resources, safety_router, safety_gate, tests) |
| **Phase 2** | ✅ Complete | Issue identification + complexity router + jurisdiction (23 tests) |
| **Phase 3** | ✅ Complete | Complex path core - fact structuring, legal elements, element schemas (24 tests) |
| **Phase 4** | ✅ Complete | Case precedent + risk analysis with mock case database (24 tests) |
| **Phase 5** | ✅ Complete | Strategy + escalation brief + adaptive graph orchestration (19 tests) |

### New File Structure (Adaptive Agent)
```
backend/app/agents/
├── adaptive_state.py           # ✅ Extended TypedDict for all 8 stages
├── adaptive_graph.py           # ✅ Main orchestration graph with simple/complex paths
├── routers/
│   ├── __init__.py             # ✅
│   ├── safety_router.py        # ✅ High-risk detection (GPT-4o-mini)
│   └── complexity_router.py    # ✅ Heuristics-first + LLM fallback routing
├── stages/
│   ├── __init__.py             # ✅
│   ├── safety_gate.py          # ✅ Stage 0 - always runs first
│   ├── issue_identification.py # ✅ Stage 1 - multi-label legal classification
│   ├── jurisdiction.py         # ✅ Stage 2 - federal vs state law resolution
│   ├── fact_structuring.py     # ✅ Stage 3 - timeline, parties, evidence extraction
│   ├── legal_elements.py       # ✅ Stage 4 - element satisfaction + viability assessment
│   ├── case_precedent.py       # ✅ Stage 5 - case law search + relevance analysis
│   ├── risk_analysis.py        # ✅ Stage 6 - risks, defences, counterfactuals
│   ├── strategy.py             # ✅ Stage 7 - multiple pathways with pros/cons
│   └── escalation_brief.py     # ✅ Stage 8 - structured lawyer handoff package
└── schemas/
    ├── __init__.py             # ✅
    ├── emergency_resources.py  # ✅ Australian crisis hotlines by state/category
    ├── legal_elements.py       # ✅ Element schemas for tenancy, employment, family, consumer, criminal
    └── case_precedents.py      # ✅ Mock case database for tenancy, employment, family, consumer
```

### Key Types (adaptive_state.py)
- `SafetyAssessment` - High-risk detection result with crisis resources
- `IssueClassification` - Primary/secondary legal issues with complexity score
- `FactStructure` - Timeline, parties, evidence inventory
- `ElementsAnalysis` - Legal elements satisfied/unsatisfied mapping
- `PrecedentAnalysis` - Similar cases and outcome patterns
- `RiskAssessment` - Counterfactual analysis and defences
- `StrategyRecommendation` - Multiple pathways with pros/cons
- `EscalationBrief` - Structured lawyer handoff package
- `AdaptiveAgentState` - Main state combining all stage outputs

### Safety Gate Categories
The safety router detects these high-risk situations and provides state-specific crisis resources:
- `criminal` - Police involvement, charges, arrests
- `family_violence` - DVO/AVO, domestic abuse, threats
- `urgent_deadline` - Court dates within 7 days, limitation periods
- `child_welfare` - Child protection, custody emergencies
- `suicide_self_harm` - Mental health crises

### Complexity Routing (Heuristics-First)
The complexity router uses fast heuristics before falling back to LLM:

**→ COMPLEX path triggers:**
- Document uploaded
- Multiple secondary issues (>1)
- Complexity score > 0.4
- Multiple jurisdictions involved
- Query contains: "dispute", "court", "tribunal", "sued"

**→ SIMPLE path triggers:**
- Short query with simple patterns ("what are my rights", "can my landlord")
- Low complexity score (≤0.3) with no secondary issues

**→ UNCERTAIN:** Falls back to GPT-4o-mini classification

### Testing
```bash
pytest tests/test_safety_gate.py -v            # 16 tests for Phase 1 (safety gate)
pytest tests/test_phase2_classification.py -v  # 23 tests for Phase 2 (issue ID, complexity, jurisdiction)
pytest tests/test_phase3_fact_elements.py -v   # 24 tests for Phase 3 (fact structuring, legal elements)
pytest tests/test_phase4_precedent_risk.py -v  # 24 tests for Phase 4 (case precedent, risk analysis)
pytest tests/test_phase5_strategy_brief.py -v  # 19 tests for Phase 5 (strategy, escalation brief, graph)
pytest tests/test_safety_gate.py tests/test_phase2_classification.py tests/test_phase3_fact_elements.py tests/test_phase4_precedent_risk.py tests/test_phase5_strategy_brief.py -v  # All adaptive agent tests (106 total)
```

### Enabling Adaptive Graph
Enable the adaptive workflow via environment variable:
```bash
USE_ADAPTIVE_GRAPH=true python main.py
```

### Reference Documents
- `agent.md` - Detailed workflow design document (user's research on real lawyer consultation flow)
- `/Users/kevin/.claude/plans/humble-chasing-bumblebee.md` - Full implementation plan

---

## Conversational Mode (Default)

### Overview
The **conversational mode** is now the default agent behavior. It provides fast, natural conversation instead of the multi-stage analysis pipeline. Users can still access the adaptive workflow by setting `USE_ADAPTIVE_GRAPH=true`.

### Why Conversational Mode?
- **Performance**: 1-2 LLM calls vs 6-11 in adaptive mode
- **Natural UX**: Chat flows like talking to a helpful friend, not a rigid pipeline
- **User Control**: Deep analysis and lawyer briefs only when explicitly requested
- **Quick Replies**: Suggested follow-up options for smoother conversation

### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│  CONVERSATIONAL MODE (default)                              │
│                                                             │
│  initialize → safety_check_lite → chat_response → END      │
│                      │                                      │
│                      ↓ (if crisis)                         │
│              escalation_response → END                      │
└─────────────────────────────────────────────────────────────┘
```

### File Structure (Conversational Mode)
```
backend/app/agents/
├── conversational_state.py      # Simplified state for chat mode
├── conversational_graph.py      # Fast 3-node graph
└── stages/
    ├── safety_check_lite.py     # Keyword-first safety (LLM fallback only when uncertain)
    └── chat_response.py         # ReAct agent with tools + quick replies
```

### Key Features

**1. Fast Safety Check (`safety_check_lite.py`)**
- Keyword detection first (no LLM for obvious cases)
- Falls back to LLM only for uncertain queries
- Skips safety check entirely for short follow-up messages

**2. Natural Chat Response (`chat_response.py`)**
- Uses ReAct agent pattern with tools (`lookup_law`, `find_lawyer`)
- Generates conversational responses, not structured analysis
- Produces 2-4 quick reply suggestions after each response
- **Critical**: Always uses `lookup_law` tool for legal references, never web search

**3. Quick Replies**
After each response, the agent suggests follow-up options like:
- "What are my options?"
- "Tell me more"
- "Find me a lawyer"
- "What happens next?"

### Tool Usage Guidelines (Conversational Mode)
- **`lookup_law`**: ALWAYS use for specific laws, legislation, or legal requirements
- **`find_lawyer`**: Use when user asks for lawyer recommendations
- **NEVER use web search** for legal information - only use the local legislation database

### Testing Conversational Mode
```bash
pytest tests/test_conversational_mode.py -v  # 15 tests
```

### Switching Between Modes
```bash
# Conversational mode (default)
python main.py

# Adaptive mode (multi-stage pipeline)
USE_ADAPTIVE_GRAPH=true python main.py
```

---

## Conversational Mode Implementation Progress

### Phase Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | Basic conversational mode (fast graph, safety check, chat response) |
| **Phase 2** | ✅ Complete | Quick replies (backend generation, frontend display via useCoAgent) |
| **Phase 3** | ⏳ Not Started | Brief generation mode (user-triggered, info gathering, comprehensive brief) |

### Phase 2 Implementation Details (Quick Replies)

**Backend** (`chat_response.py`):
- After generating chat response, calls `generate_quick_replies()` with gpt-4o-mini
- Uses `get_internal_llm_config(config)` to suppress streaming (prevents raw JSON in chat)
- Returns `quick_replies` in state output

**Frontend** (`chat/page.tsx`):
- Uses `useCoAgent` hook to access agent state (NOT `useCoAgentStateRender`)
- Renders `QuickRepliesPanel` component when `quick_replies` exists
- Clicking a quick reply sends it as user message via `useCopilotChat().appendMessage()`

**Key Learning**: Quick replies use `get_internal_llm_config` because internal LLM calls stream raw JSON to the UI otherwise. The fix is documented in "Suppressing Internal LLM Streaming" section above.

---

## Phase 3: Brief Generation Mode (TODO)

### Overview
User-triggered brief generation that analyzes conversation history, asks follow-up questions if info is missing, then generates a comprehensive lawyer brief.

### Architecture
```
USER CLICKS "Generate Brief" BUTTON
         │
         ▼
┌─────────────────────────────────────────────┐
│  BRIEF GENERATION MODE                      │
│                                             │
│  [1] Analyze conversation history           │
│      - What legal issue is this?            │
│      - What facts do we have?               │
│      - What's missing?                      │
│                                             │
│  [2] If missing critical info:              │
│      → Ask targeted questions               │
│      → Wait for user responses              │
│      → Loop until sufficient                │
│                                             │
│  [3] When ready:                            │
│      → Generate comprehensive brief         │
│      → Include: facts, issues, risks,       │
│        questions for lawyer                 │
│                                             │
└─────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 3.1: Add State Fields for Brief Mode

**Modify** `conversational_state.py`:
```python
class ConversationalState(TypedDict):
    # ... existing fields ...

    # Brief generation state (only used in brief mode)
    brief_facts_collected: Optional[dict]      # Facts gathered from conversation
    brief_missing_info: Optional[list[str]]    # What we still need
    brief_info_complete: bool                  # Ready to generate?
    brief_questions_asked: int                 # Track question count (max 3 rounds)
```

#### Step 3.2: Create Brief Generation Nodes

**Create** `backend/app/agents/stages/brief_flow.py`:

```python
async def brief_check_info_node(state: ConversationalState, config: RunnableConfig) -> dict:
    """Analyze conversation to determine what info we have and need."""
    messages = state.get("messages", [])

    # Use LLM to extract facts from conversation
    facts = await extract_facts_from_conversation(messages, config)

    # Determine legal area and required info
    legal_area = facts.get("legal_area", "general")
    required = get_required_info_for_brief(legal_area)

    # Find gaps
    missing = [r for r in required if r not in facts]

    return {
        "brief_facts_collected": facts,
        "brief_missing_info": missing,
        "brief_info_complete": len(missing) == 0
    }

async def brief_ask_questions_node(state: ConversationalState, config: RunnableConfig) -> dict:
    """Ask targeted questions to fill info gaps."""
    missing = state.get("brief_missing_info", [])
    questions_asked = state.get("brief_questions_asked", 0)

    # Generate natural questions for missing info (max 2 at a time)
    questions = await generate_questions_for_missing(missing[:2], config)

    return {
        "messages": [AIMessage(content=questions)],
        "brief_questions_asked": questions_asked + 1
    }

async def brief_generate_node(state: ConversationalState, config: RunnableConfig) -> dict:
    """Generate the comprehensive lawyer brief."""
    facts = state.get("brief_facts_collected", {})
    messages = state.get("messages", [])
    user_state = state.get("user_state")

    brief = await generate_comprehensive_brief(facts, messages, user_state, config)

    return {
        "messages": [AIMessage(content=format_brief(brief))],
        "mode": "chat"  # Return to chat mode after brief
    }
```

#### Step 3.3: Update Graph with Brief Mode Routing

**Modify** `conversational_graph.py`:

```python
def route_after_chat(state: ConversationalState) -> str:
    """Route based on mode."""
    if state.get("mode") == "brief":
        return "brief_check_info"
    return END

def route_brief_info(state: ConversationalState) -> str:
    """Route based on whether we have enough info."""
    if state.get("brief_info_complete"):
        return "brief_generate"
    if state.get("brief_questions_asked", 0) >= 3:
        return "brief_generate"  # Max 3 rounds of questions
    return "brief_ask_questions"

# Add nodes
graph.add_node("brief_check_info", brief_check_info_node)
graph.add_node("brief_ask_questions", brief_ask_questions_node)
graph.add_node("brief_generate", brief_generate_node)

# Add edges
graph.add_conditional_edges("chat_response", route_after_chat, {
    "brief_check_info": "brief_check_info",
    END: END
})
graph.add_conditional_edges("brief_check_info", route_brief_info, {
    "brief_generate": "brief_generate",
    "brief_ask_questions": "brief_ask_questions"
})
graph.add_edge("brief_ask_questions", END)  # Wait for user response
graph.add_edge("brief_generate", END)
```

#### Step 3.4: Add Frontend "Generate Brief" Button

**Modify** `frontend/app/chat/page.tsx`:

```tsx
// Add to SidebarContent or bottom of chat
<Card className="border-sky-200 bg-sky-50/50">
  <CardHeader className="pb-2">
    <CardTitle className="text-base font-medium flex items-center gap-2">
      <FileText className="h-4 w-4 text-sky-700" />
      Lawyer Brief
    </CardTitle>
    <CardDescription>
      Generate a summary to share with a solicitor
    </CardDescription>
  </CardHeader>
  <CardContent>
    <Button
      onClick={handleGenerateBrief}
      className="w-full"
      disabled={!hasConversation}
    >
      Generate Brief
    </Button>
  </CardContent>
</Card>

// Handler
const handleGenerateBrief = async () => {
  await appendMessage(
    new TextMessage({
      role: MessageRole.User,
      content: "[GENERATE_BRIEF] Please prepare a lawyer brief based on our conversation.",
    })
  );
};
```

#### Step 3.5: Detect Brief Trigger in Initialize

**Modify** `conversational_graph.py` initialize node:

```python
def initialize_node(state: ConversationalState, config: RunnableConfig) -> dict:
    # ... existing code ...

    # Check for brief generation trigger
    is_brief_mode = "[GENERATE_BRIEF]" in current_query

    return {
        # ... existing fields ...
        "mode": "brief" if is_brief_mode else "chat",
        "current_query": current_query.replace("[GENERATE_BRIEF]", "").strip(),
    }
```

### Testing Plan

```bash
# Unit tests for brief mode
pytest tests/test_brief_generation.py -v

# Manual testing
1. Have a conversation about a legal issue
2. Click "Generate Brief" button
3. Answer any follow-up questions
4. Verify brief is generated with facts, issues, risks
```

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `backend/app/agents/stages/brief_flow.py` | Create | Brief generation nodes |
| `backend/app/agents/conversational_state.py` | Modify | Add brief state fields |
| `backend/app/agents/conversational_graph.py` | Modify | Add brief routing & nodes |
| `frontend/app/chat/page.tsx` | Modify | Add "Generate Brief" button |
| `backend/tests/test_brief_generation.py` | Create | Tests for brief mode |
