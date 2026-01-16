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
python scripts/ingest_corpus.py --limit 10    # Test with 10 docs
python scripts/ingest_corpus.py --dry-run     # Preview without changes
python scripts/ingest_corpus.py               # Full ingestion (~6000 docs)
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
COHERE_API_KEY=          # Optional: for reranking (gracefully degrades if not set)
```

Frontend `.env.local` file in `/frontend`:
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
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
├── scripts/
│   └── ingest_corpus.py    # Hugging Face dataset ingestion
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
