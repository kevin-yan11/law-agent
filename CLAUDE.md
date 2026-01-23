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
- **Important**: AG-UI protocol double-serializes string values. Use `clean_context_value()` in main.py to strip extra quotes and unescape inner quotes.

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
├── main.py                 # FastAPI app, custom LangGraph, CopilotKit integration
├── pytest.ini              # Pytest configuration
├── app/
│   ├── config.py           # Environment variables, logging
│   ├── db/supabase_client.py
│   ├── services/           # RAG services
│   │   ├── embedding_service.py   # OpenAI text-embedding-3-small
│   │   ├── hybrid_retriever.py    # Vector + FTS + RRF fusion
│   │   └── reranker.py            # Cohere reranker (optional)
│   ├── tools/
│   │   ├── lookup_law.py       # RAG-based legal search
│   │   ├── find_lawyer.py      # Filter by location/specialty
│   │   ├── generate_checklist.py  # LLM-generated or template-based
│   │   └── analyze_document.py # Fetch & parse docs for agent analysis
│   └── utils/
│       ├── document_parser.py  # PDF, DOCX, image parsing
│       └── url_fetcher.py      # Fetch documents from URLs
├── tests/
│   ├── conftest.py         # Shared fixtures
│   ├── test_url_fetcher.py # SSRF protection tests
│   └── test_lookup_law.py  # RAG tool tests
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

## Adaptive Agent Workflow (In Progress)

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
| **Phase 5** | ⏳ Pending | Strategy + escalation brief + full integration with main.py |

### New File Structure (Adaptive Agent)
```
backend/app/agents/
├── adaptive_state.py           # ✅ Extended TypedDict for all 8 stages
├── adaptive_graph.py           # ⏳ Main orchestration graph (Phase 5)
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
│   ├── strategy.py             # ⏳ Stage 7 (Phase 5)
│   └── escalation_brief.py     # ⏳ Stage 8 (Phase 5)
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
pytest tests/test_safety_gate.py tests/test_phase2_classification.py tests/test_phase3_fact_elements.py tests/test_phase4_precedent_risk.py -v  # All adaptive agent tests (87 total)
```

### Enabling Adaptive Graph (Future)
Once complete, enable via environment variable:
```bash
USE_ADAPTIVE_GRAPH=true python main.py
```

### Reference Documents
- `agent.md` - Detailed workflow design document (user's research on real lawyer consultation flow)
- `/Users/kevin/.claude/plans/humble-chasing-bumblebee.md` - Full implementation plan
