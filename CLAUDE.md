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
2. **RRF Fusion**: Reciprocal Rank Fusion merges results (MIN_RRF_SCORE = 0.01 filters weak matches)
3. **Reranking**: Cohere rerank with MIN_RELEVANCE_SCORE = 0.25 threshold (falls back to RRF if not configured)
4. **Confidence Levels**: Results tagged as high (>0.6), medium (0.4-0.6), or low (0.25-0.4)
5. **Quality-Aware Responses**: Warnings added when only low-confidence results found
6. **Parent-Child Chunks**: Child chunks (500 tokens) for precise retrieval, parent chunks (2000 tokens) for context

**Retry Logic**: Embedding API calls retry 3x with exponential backoff (1s, 2s, 4s delays)

**Data Source**: Hugging Face `isaacus/open-australian-legal-corpus` (Primary Legislation only)
**Supported Jurisdictions**: NSW, QLD, FEDERAL (no Victoria data in corpus)

### CopilotKit Context Passing
The agent uses a **custom StateGraph** (not `create_react_agent`) to properly read frontend context:
- Frontend uses `useCopilotReadable` to share user's selected state and uploaded document URL
- Backend inherits from `CopilotKitState` and reads `state["copilotkit"]["context"]`
- **Important**: AG-UI protocol double-serializes string values. Use `clean_context_value()` in main.py to strip extra quotes and unescape inner quotes.

### State-Based Legal Information
Australian law varies by state. The `StateSelector` component lets users pick their state (VIC, NSW, QLD, etc.), which is passed to all tool calls automatically. **All tools require the state parameter - there are no defaults** to prevent incorrect jurisdiction assumptions. For unsupported states (VIC, SA, WA, TAS, NT), the system falls back to Federal law.

### Document Upload Flow
Files are uploaded to Supabase Storage (not backend memory) for persistence:
1. Frontend uploads to Supabase Storage bucket `documents`
2. Public URL shared with agent via `useCopilotReadable`
3. Agent calls `analyze_document(document_url=...)`
4. Tool fetches file from URL, parses it, returns text for agent to analyze

## Production Features

### Startup Validation
Backend validates Supabase and OpenAI connections on startup. Server exits if either fails.

### Rate Limiting
`/copilotkit` endpoint limited to 30 requests/minute per IP address.

### SSRF Protection
Document fetcher only allows URLs from domains in `ALLOWED_DOCUMENT_HOSTS`.

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
│   ├── page.tsx                # Landing page
│   ├── chat/page.tsx           # Main chat interface with CopilotChat
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
