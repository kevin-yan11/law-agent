# AusLaw AI

An Australian Legal Assistant MVP that provides legal information, lawyer matching, step-by-step checklists, and document analysis for legal procedures across Australian states/territories.

## Features

- **Legal Research**: RAG-powered search of Australian legislation with hybrid retrieval (vector + full-text search)
- **Lawyer Matching**: Find lawyers by specialty and location
- **Procedure Checklists**: Generate step-by-step guides for legal processes
- **Document Analysis**: Upload and analyze legal documents (PDF, DOCX, images)
- **State-Aware**: All information is tailored to the user's Australian state/territory

## Tech Stack

- **Frontend**: Next.js 14, CopilotKit, shadcn/ui, Tailwind CSS
- **Backend**: FastAPI, LangGraph, langchain-openai (GPT-4o)
- **Database**: Supabase PostgreSQL with pgvector for RAG
- **Storage**: Supabase Storage for document uploads

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+ with conda
- Supabase account
- OpenAI API key

### Setup

1. **Clone and install**
   ```bash
   git clone <repo-url>
   cd law_agent

   # Frontend
   cd frontend && npm install

   # Backend
   cd ../backend
   conda create -n law_agent python=3.11
   conda activate law_agent
   pip install -r requirements.txt
   ```

2. **Environment variables**

   Create `backend/.env`:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   OPENAI_API_KEY=your_openai_key
   COHERE_API_KEY=your_cohere_key  # Optional: for reranking
   ```

   Create `frontend/.env.local`:
   ```
   NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
   ```

3. **Database setup**

   Run the following SQL files in Supabase SQL Editor:
   - `database/setup.sql` - Initial schema and mock data
   - `database/migration_v2.sql` - Action templates table
   - `database/migration_rag.sql` - pgvector schema for RAG

4. **Ingest legal corpus** (optional, for RAG)
   ```bash
   cd backend
   conda activate law_agent
   python scripts/ingest_corpus.py --limit 100  # Test with 100 docs
   ```

5. **Run**
   ```bash
   # Terminal 1 - Backend
   cd backend && conda activate law_agent && python main.py

   # Terminal 2 - Frontend
   cd frontend && npm run dev
   ```

6. Open http://localhost:3000

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

## RAG System

The `lookup_law` tool uses a hybrid retrieval pipeline:
1. **Hybrid Search**: Vector similarity (pgvector) + PostgreSQL full-text search
2. **RRF Fusion**: Reciprocal Rank Fusion merges results from both methods
3. **Reranking**: Optional Cohere rerank for final precision

**Data Source**: [Open Australian Legal Corpus](https://huggingface.co/datasets/isaacus/open-australian-legal-corpus) (Primary Legislation)

**Supported Jurisdictions**: NSW, QLD, Federal (others fall back to Federal law)

## License

MIT
