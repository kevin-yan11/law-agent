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

### Testing
```bash
cd backend
conda activate law_agent
pytest                                              # Run all tests
pytest tests/test_conversational_mode.py -v         # Conversational mode tests
pytest tests/test_brief_generation.py -v            # Brief generation tests
pytest tests/test_lookup_law.py -v                  # RAG/lookup tests
pytest tests/test_file.py::test_name -v             # Run single test
```

### Data Ingestion (RAG)
```bash
cd backend
python scripts/ingest_corpus.py --limit 10              # Test with 10 docs
python scripts/ingest_corpus.py --batch-size 500        # Full ingestion (~6000 docs)
python scripts/eval_rag.py --verbose                    # RAG evaluation
```

### Database
Run SQL files in Supabase SQL Editor:
- `database/setup.sql` - Initial schema and mock data
- `database/migration_v2.sql` - Adds action_templates table and state column
- `database/migration_rag.sql` - pgvector schema for RAG

## Environment Variables

Backend `.env` file in `/backend`:
```
SUPABASE_URL=
SUPABASE_KEY=
OPENAI_API_KEY=
COHERE_API_KEY=              # Optional: for reranking
ALLOWED_DOCUMENT_HOSTS=      # Required: your Supabase domain
```

Frontend `.env.local` file in `/frontend`:
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
BACKEND_URL=http://localhost:8000
```

## Key Architecture Decisions

### RAG System
The `lookup_law` tool uses hybrid retrieval: vector similarity (pgvector) + full-text search + RRF fusion + optional Cohere reranking.

- **Data Source**: Hugging Face `isaacus/open-australian-legal-corpus` (Primary Legislation)
- **Supported Jurisdictions**: NSW, QLD, FEDERAL (no Victoria in corpus)
- **Chunking**: Parent chunks (2000 tokens) + Child chunks (500 tokens) for docs >= 10K chars

### CopilotKit Context Passing
Frontend uses `useCopilotReadable` to share user's selected state and uploaded document URL. Backend reads from `state["copilotkit"]["context"]`.

**Bug Workaround**: AG-UI protocol double-serializes strings (e.g., `"\"NSW\""`). Use utilities from `app/agents/utils/context.py`:
- `extract_user_state(state)` - Get Australian state code
- `extract_document_url(state)` - Get uploaded document URL
- `clean_context_value(value)` - Strip extra quotes from raw values

### Suppressing Internal LLM Streaming

Use config helpers from `app/agents/utils/config.py` to control streaming:

| Helper | emit-messages | emit-tool-calls | Use for |
|--------|---------------|-----------------|---------|
| `get_internal_llm_config` | False | False | Internal LLM calls (safety, quick replies) |
| `get_chat_agent_config` | True | False | ReAct agents with tools |
| (default config) | True | True | Simple LLM calls without tools |

**Known limitation**: With `emit_messages=True`, intermediate ReAct agent messages like "Let me search for that..." will appear then disappear when the final response arrives. This is a tradeoff for keeping response streaming. CopilotKit currently doesn't support selective message filtering (see [GitHub Issue #1959](https://github.com/CopilotKit/CopilotKit/issues/1959)).

### Message Deduplication

Messages returned from LangGraph nodes must have explicit unique IDs to prevent duplicates on checkpoint restore. Without IDs, the frontend cannot deduplicate messages that are re-sent when state is restored.

```python
# Good - explicit ID preserved across checkpoint restore
AIMessage(content="...", id=f"analysis_offer_{uuid.uuid4().hex[:8]}")

# Bad - ID may change on deserialization, causing duplicates
AIMessage(content="...")
```

### Document Upload Flow
1. Frontend uploads to Supabase Storage bucket `documents`
2. Public URL shared with agent via `useCopilotReadable`
3. Agent calls `analyze_document(document_url=...)`

## Frontend Structure

```
frontend/app/
├── chat/page.tsx           # Main chat page with sidebar + CopilotChat
├── components/
│   ├── StateSelector.tsx   # Australian state/territory dropdown
│   ├── FileUpload.tsx      # Document upload to Supabase Storage
│   ├── ModeToggle.tsx      # Chat/Analysis mode toggle
│   └── AnalysisOutput.tsx  # Deep analysis results display
├── contexts/
│   └── ModeContext.tsx     # App-wide mode state (chat | analysis)
├── globals.css             # CopilotKit overrides, mode-based theming
└── layout.tsx              # CopilotKit provider setup
```

### Key Frontend Patterns
- **Mode-based theming**: CSS uses `[data-mode="chat"]` and `[data-mode="analysis"]` selectors for distinct visual styles
- **Quick replies**: Agent state provides `quick_replies` array via `useCoAgent`, limited to 3 items in UI
- **Topic pills**: Starter topic buttons shown before conversation begins, hidden after first message
- **CopilotKit styling**: Override classes like `.copilotKitMessages`, `.copilotKitInput` in globals.css

## Backend Structure

```
backend/
├── main.py                 # FastAPI app entry point
├── app/
│   ├── config.py           # Environment variables, logging
│   ├── db/supabase_client.py
│   ├── agents/
│   │   ├── conversational_state.py   # State + output schema for chat mode
│   │   ├── conversational_graph.py   # Main graph: chat + brief + analysis
│   │   ├── analysis/
│   │   │   └── deep_analysis.py      # Consolidated analysis (single LLM call)
│   │   ├── stages/
│   │   │   ├── safety_check_lite.py  # Fast keyword-first safety check
│   │   │   ├── chat_response.py      # ReAct agent with tools + quick replies
│   │   │   ├── brief_flow.py         # Brief generation nodes
│   │   │   └── deep_analysis.py      # Deep analysis flow nodes
│   │   ├── schemas/                  # Emergency resources
│   │   └── utils/                    # Config helpers, context extraction
│   ├── services/                     # RAG services (embedding, retrieval, reranking)
│   ├── tools/                        # lookup_law, find_lawyer, generate_checklist, analyze_document
│   └── utils/                        # Document parsing, URL fetching
├── tests/
└── scripts/                          # Data ingestion, RAG evaluation
```

## Database Schema

### RAG Tables
- **legislation_documents**: `id`, `version_id`, `citation`, `jurisdiction`, `source_url`, `full_text`
- **legislation_chunks**: `id`, `document_id`, `parent_chunk_id`, `content`, `embedding` (vector 1536), `chunk_type`

### Key SQL Function
`hybrid_search(query_embedding, query_text, filter_jurisdiction, match_count)` - Combined vector + keyword search.

---

## Conversational Mode

Fast, natural conversation with tools and optional deep analysis.

```
CHAT FLOW:
initialize → safety_check_lite → chat_response → [END | analysis_offer]
                    │                                    │
                    ↓ (if crisis)                        ↓ (if accepted)
            escalation_response → END     deep_analysis → analysis_response → END

BRIEF FLOW (user-triggered via "Generate Brief" button):
initialize → brief_check_info ─┬→ brief_generate → END
                    ↑          │
                    └──────────┴→ brief_ask_questions (loop)
```

### Key Features
- **Safety Check**: Keyword detection first, LLM fallback only when uncertain
- **Chat Response**: ReAct agent with `lookup_law` and `find_lawyer` tools
- **Quick Replies**: 2-4 suggested follow-up options after each response
- **Tool Usage**: ALWAYS use `lookup_law` for legal references, never web search
- **Deep Analysis**: Optional analysis offered when enough facts are gathered

### Deep Analysis Mode
When the conversation has gathered sufficient facts (analysis_readiness >= 0.7), the agent offers deep analysis:

1. **Analysis Offer**: "Would you like me to analyze your legal position?"
2. **If accepted**: Runs consolidated analysis (single LLM call) that produces:
   - **Facts**: Timeline, parties, evidence, key facts, fact gaps, narrative
   - **Risks**: Overall risk level, strengths, weaknesses, specific risks with mitigations
   - **Strategy**: Recommended action, alternatives, immediate next steps
3. **Analysis Response**: Presents findings conversationally (not as formal document)

**Architecture note**: The analysis uses a single consolidated LLM call (`run_consolidated_analysis`) instead of sequential calls, reducing latency from ~6s to ~2s.

**Detection triggers**:
- User described a specific dispute or conflict
- Multiple facts mentioned (dates, amounts, events)
- Other party identified (landlord, employer, etc.)
- User asked "what should I do?" or "what are my options?"

### Brief Generation Mode
User clicks "Generate Brief" button to create a lawyer brief:

1. **Info Check**: Extracts facts from conversation, identifies gaps
2. **Ask Questions**: Questions asked **one at a time** with progress indicator ("Question 1/3")
   - Handles "I don't know" → moves item to unknown list, asks next question
   - Handles "Generate brief now" → generates with available info
3. **Generate Brief**: Creates comprehensive brief with Summary, Facts, Parties, Goals, Questions for Lawyer
   - Includes "Information Not Provided" section for skipped items

**State fields** (in `conversational_state.py`):
- `brief_pending_questions` - Remaining questions to ask
- `brief_current_question_index` - For progress display
- `brief_total_questions` - Total questions in current round

**Triggers**:
- `[GENERATE_BRIEF]` - Start brief mode (sent by frontend button)
- `[GENERATE_NOW]` - Early generation request

---

## Code Style

- All comments and documentation must be in English
- After completing code changes, generate a commit message summarizing the changes
