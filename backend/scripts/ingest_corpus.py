#!/usr/bin/env python3
"""
Data Ingestion Script for AusLaw AI RAG

Loads the Open Australian Legal Corpus from Hugging Face and ingests
it into Supabase with embeddings.

Usage:
    cd backend
    conda activate law_agent
    python scripts/ingest_corpus.py

Options:
    --dry-run       Preview what would be ingested without making changes
    --limit N       Only process first N documents (for testing)
    --batch-size N  Embedding batch size (default: 20)
    --max-doc-size  Maximum document size in chars (default: 500000)
"""

import os
import sys
import asyncio
import argparse
import gc
from datetime import datetime
from typing import List, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datasets import load_dataset
import tiktoken

from app.db import supabase
from app.services.embedding_service import EmbeddingService
from app.config import logger


# Jurisdiction mapping from dataset to app format
JURISDICTION_MAP = {
    "commonwealth": "FEDERAL",
    "new_south_wales": "NSW",
    "queensland": "QLD",
}

# Target jurisdictions to ingest
TARGET_JURISDICTIONS = ["commonwealth", "new_south_wales", "queensland"]

# Chunking parameters (optimized based on document size analysis)
PARENT_CHUNK_SIZE = 2000  # tokens (~8000 chars) - larger for better context
CHILD_CHUNK_SIZE = 500    # tokens (~2000 chars) - covers a full legal clause
CHILD_OVERLAP = 50        # tokens

# Threshold for creating child chunks (in characters)
# Documents smaller than this only get parent chunks (no children)
SMALL_DOC_THRESHOLD = 10000  # 10K chars - about 25% of docs

# Memory management
MAX_DOC_SIZE = 500000     # Max chars per document (500k)
MAX_CHUNKS_PER_DOC = 200  # Reduced limit per document


class DocumentChunker:
    """Chunks documents into parent-child hierarchy."""

    def __init__(self):
        # Use cl100k_base tokenizer (same as GPT-4/text-embedding-3)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def chunk_text(
        self,
        text: str,
        chunk_size: int,
        overlap: int = 0
    ) -> List[str]:
        """
        Split text into chunks of approximately chunk_size tokens.
        """
        if not text.strip():
            return []

        # Truncate very long texts to prevent memory issues
        if len(text) > MAX_DOC_SIZE:
            text = text[:MAX_DOC_SIZE]
            logger.warning(f"Truncated document to {MAX_DOC_SIZE} chars")

        tokens = self.tokenizer.encode(text)

        if len(tokens) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(tokens) and len(chunks) < MAX_CHUNKS_PER_DOC:
            end = min(start + chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)

            # Try to find sentence boundary
            if end < len(tokens):
                for punct in ['. ', '.\n', '? ', '!\n']:
                    last_punct = chunk_text.rfind(punct)
                    if last_punct > len(chunk_text) * 0.5:
                        chunk_text = chunk_text[:last_punct + 1]
                        end = start + len(self.tokenizer.encode(chunk_text))
                        break

            chunks.append(chunk_text.strip())
            start = end - overlap

        return chunks

    def create_parent_child_chunks(self, text: str) -> List[Dict]:
        """
        Create parent-child chunk hierarchy.

        For small documents (< SMALL_DOC_THRESHOLD), only create parent chunks.
        For larger documents, create both parent and child chunks.
        """
        is_small_doc = len(text) < SMALL_DOC_THRESHOLD

        # Create parent chunks
        parent_texts = self.chunk_text(text, PARENT_CHUNK_SIZE, overlap=0)

        all_chunks = []
        global_index = 0

        for parent_idx, parent_text in enumerate(parent_texts):
            if len(all_chunks) >= MAX_CHUNKS_PER_DOC:
                break

            # Add parent chunk
            parent_chunk = {
                "content": parent_text,
                "chunk_type": "parent",
                "chunk_index": global_index,
                "parent_index": None,
                "token_count": self.count_tokens(parent_text),
            }
            all_chunks.append(parent_chunk)
            parent_global_index = global_index
            global_index += 1

            # For small documents, skip child chunks - parent is enough
            if is_small_doc:
                continue

            # Create child chunks from this parent (only for larger docs)
            child_texts = self.chunk_text(parent_text, CHILD_CHUNK_SIZE, CHILD_OVERLAP)

            for child_text in child_texts:
                if len(all_chunks) >= MAX_CHUNKS_PER_DOC:
                    break

                child_chunk = {
                    "content": child_text,
                    "chunk_type": "child",
                    "chunk_index": global_index,
                    "parent_index": parent_global_index,
                    "token_count": self.count_tokens(child_text),
                }
                all_chunks.append(child_chunk)
                global_index += 1

        return all_chunks


class CorpusIngester:
    """Handles ingestion of legal corpus into Supabase."""

    def __init__(self, dry_run: bool = False, batch_size: int = 20, max_doc_size: int = MAX_DOC_SIZE):
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.max_doc_size = max_doc_size
        self.chunker = DocumentChunker()
        self.embedding_service = EmbeddingService()
        self.stats = {
            "documents_processed": 0,
            "documents_skipped": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
            "errors": 0,
        }

    def load_corpus(self, limit: Optional[int] = None):
        """
        Load and filter the corpus from Hugging Face.
        """
        logger.info("Loading corpus from Hugging Face...")

        # Load dataset in streaming mode to handle large size
        dataset = load_dataset(
            "isaacus/open-australian-legal-corpus",
            split="corpus",
            streaming=True
        )

        count = 0
        for record in dataset:
            # Filter by type and jurisdiction
            if record.get("type") != "primary_legislation":
                continue

            jurisdiction = record.get("jurisdiction", "")
            if jurisdiction not in TARGET_JURISDICTIONS:
                continue

            yield record
            count += 1

            if limit and count >= limit:
                break

        logger.info(f"Filtered {count} primary_legislation documents")

    def parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse date string to ISO format for PostgreSQL."""
        if not date_str:
            return None

        try:
            if len(date_str) >= 10:
                return date_str[:10]
            elif len(date_str) == 7:
                return f"{date_str}-01"
            elif len(date_str) == 4:
                return f"{date_str}-01-01"
            else:
                return None
        except Exception:
            return None

    async def ingest_document(self, record: Dict) -> Optional[str]:
        """
        Ingest a single document into the database.
        """
        version_id = record.get("version_id", "")
        citation = record.get("citation", "Unknown")

        try:
            jurisdiction = JURISDICTION_MAP.get(record.get("jurisdiction", ""), "FEDERAL")
            text = record.get("text", "")

            # Skip empty documents
            if not text or not text.strip():
                logger.warning(f"Skipping empty document: {citation}")
                self.stats["documents_skipped"] += 1
                return None

            # Truncate very large documents
            if len(text) > self.max_doc_size:
                logger.info(f"Truncating large document ({len(text)} chars): {citation}")
                text = text[:self.max_doc_size]

            if self.dry_run:
                logger.info(f"[DRY RUN] Would ingest: {citation} ({jurisdiction})")
                self.stats["documents_processed"] += 1
                return "dry-run-id"

            # Check if document already exists
            existing = supabase.table("legislation_documents") \
                .select("id") \
                .eq("version_id", version_id) \
                .execute()

            if existing.data:
                logger.info(f"Skipping existing: {citation}")
                self.stats["documents_skipped"] += 1
                return existing.data[0]["id"]

            # Insert document (store truncated text)
            doc_data = {
                "version_id": version_id,
                "citation": citation,
                "jurisdiction": jurisdiction,
                "source": record.get("source", ""),
                "source_url": record.get("url", ""),
                "mime_type": record.get("mime", ""),
                "effective_date": self.parse_date(record.get("date")),
                "full_text": text[:100000],  # Store max 100k in DB
            }

            doc_response = supabase.table("legislation_documents") \
                .insert(doc_data) \
                .execute()

            document_id = doc_response.data[0]["id"]

            # Create chunks
            chunks = self.chunker.create_parent_child_chunks(text)

            if not chunks:
                logger.warning(f"No chunks created for: {citation}")
                self.stats["documents_processed"] += 1
                return document_id

            logger.info(f"Processing {len(chunks)} chunks for: {citation}")

            # Generate embeddings in smaller batches to save memory
            chunk_texts = [c["content"] for c in chunks]

            # Process embeddings in batches
            all_embeddings = []
            for i in range(0, len(chunk_texts), self.batch_size):
                batch = chunk_texts[i:i + self.batch_size]
                batch_embeddings = await self.embedding_service.embed_batch(batch, batch_size=self.batch_size)
                all_embeddings.extend(batch_embeddings)
                self.stats["embeddings_generated"] += len(batch_embeddings)


            # First pass: batch insert parent chunks
            parent_chunks_data = []
            parent_chunk_indices = []  # Track chunk_index for mapping

            for chunk, embedding in zip(chunks, all_embeddings):
                if chunk["chunk_type"] == "parent":
                    chunk_data = {
                        "document_id": document_id,
                        "parent_chunk_id": None,
                        "content": chunk["content"],
                        "embedding": embedding,
                        "chunk_type": "parent",
                        "chunk_index": chunk["chunk_index"],
                        "token_count": chunk["token_count"],
                    }
                    parent_chunks_data.append(chunk_data)
                    parent_chunk_indices.append(chunk["chunk_index"])

            # Batch insert all parent chunks at once
            parent_id_map = {}
            if parent_chunks_data:
                parent_response = supabase.table("legislation_chunks") \
                    .insert(parent_chunks_data) \
                    .execute()

                # Map chunk_index to database ID
                for idx, row in zip(parent_chunk_indices, parent_response.data):
                    parent_id_map[idx] = row["id"]
                self.stats["chunks_created"] += len(parent_chunks_data)

            # Second pass: batch insert child chunks
            child_chunks_data = []
            for chunk, embedding in zip(chunks, all_embeddings):
                if chunk["chunk_type"] == "child":
                    parent_db_id = parent_id_map.get(chunk["parent_index"])
                    chunk_data = {
                        "document_id": document_id,
                        "parent_chunk_id": parent_db_id,
                        "content": chunk["content"],
                        "embedding": embedding,
                        "chunk_type": "child",
                        "chunk_index": chunk["chunk_index"],
                        "token_count": chunk["token_count"],
                    }
                    child_chunks_data.append(chunk_data)

            # Batch insert all child chunks at once
            if child_chunks_data:
                supabase.table("legislation_chunks") \
                    .insert(child_chunks_data) \
                    .execute()
                self.stats["chunks_created"] += len(child_chunks_data)

            self.stats["documents_processed"] += 1
            logger.info(f"✓ Ingested: {citation} ({len(chunks)} chunks)")

            # Force garbage collection after each document
            del chunks, chunk_texts, all_embeddings
            gc.collect()

            return document_id

        except Exception as e:
            logger.error(f"Error ingesting {citation}: {e}")
            self.stats["errors"] += 1
            # Force garbage collection on error too
            gc.collect()
            return None

    async def run(self, limit: Optional[int] = None):
        """
        Run the full ingestion process.
        """
        start_time = datetime.now()
        logger.info(f"Starting corpus ingestion (dry_run={self.dry_run}, batch_size={self.batch_size})")

        doc_count = 0
        for record in self.load_corpus(limit):
            doc_count += 1
            await self.ingest_document(record)

            # Progress update every 10 documents
            if doc_count % 10 == 0:
                elapsed = datetime.now() - start_time
                logger.info(f"""
--- Progress Report ---
Documents seen: {doc_count}
Documents processed: {self.stats['documents_processed']}
Documents skipped: {self.stats['documents_skipped']}
Chunks created: {self.stats['chunks_created']}
Errors: {self.stats['errors']}
Elapsed: {elapsed}
-----------------------
                """)

                # Periodic garbage collection
                gc.collect()

        elapsed = datetime.now() - start_time
        logger.info(f"""
========================================
Ingestion Complete!
========================================
Duration: {elapsed}
Documents processed: {self.stats['documents_processed']}
Documents skipped: {self.stats['documents_skipped']}
Chunks created: {self.stats['chunks_created']}
Embeddings generated: {self.stats['embeddings_generated']}
Errors: {self.stats['errors']}
========================================
        """)


def main():
    parser = argparse.ArgumentParser(description="Ingest legal corpus into Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--limit", type=int, help="Limit number of documents to process")
    parser.add_argument("--batch-size", type=int, default=20, help="Embedding batch size (default: 20)")
    parser.add_argument("--max-doc-size", type=int, default=MAX_DOC_SIZE, help="Max document size in chars")

    args = parser.parse_args()

    ingester = CorpusIngester(
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        max_doc_size=args.max_doc_size
    )

    asyncio.run(ingester.run(limit=args.limit))


if __name__ == "__main__":
    main()
