"""
RAG Pipeline (CORE-003) for HR multi-agent platform.

Handles document ingestion, chunking, embedding, and retrieval
for HR policies, employee handbook, compliance docs, and benefits guides.

Supports ChromaDB for vector storage with fallback to in-memory implementation.
"""

import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class RAGResult:
    """Result from RAG search with metadata."""

    content: str
    source: str
    score: float
    metadata: Dict[str, Any]

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RAGResult(source='{self.source}', score={self.score:.2f}, "
            f"content_len={len(self.content)}, metadata={self.metadata})"
        )


class InMemoryVectorStore:
    """
    Simple in-memory vector store for testing/fallback.

    Stores documents with basic similarity scoring.
    Not recommended for production - use ChromaDB instead.
    """

    def __init__(self):
        """Initialize in-memory store."""
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.embeddings: Dict[str, List[float]] = {}
        self.doc_counter = 0

    def add_document(self, content: str, embedding: List[float], metadata: Dict[str, Any]) -> str:
        """
        Add document to store.

        Args:
            content: Document text
            embedding: Embedding vector
            metadata: Document metadata

        Returns:
            Document ID
        """
        doc_id = f"doc_{self.doc_counter}"
        self.doc_counter += 1

        self.documents[doc_id] = {
            "content": content,
            "metadata": metadata,
        }
        self.embeddings[doc_id] = embedding

        return doc_id

    def search(
        self, query_embedding: List[float], top_k: int = 5, min_score: float = 0.3
    ) -> List[tuple[str, float]]:
        """
        Search for similar documents.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results
            min_score: Minimum similarity score

        Returns:
            List of (doc_id, score) tuples
        """
        if not self.embeddings:
            return []

        scores = []
        for doc_id, doc_embedding in self.embeddings.items():
            # Cosine similarity
            sim = self._cosine_similarity(query_embedding, doc_embedding)
            if sim >= min_score:
                scores.append((doc_id, sim))

        # Sort by score, return top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID."""
        return self.documents.get(doc_id)

    def delete_document(self, doc_id: str) -> bool:
        """Delete document."""
        if doc_id in self.documents:
            del self.documents[doc_id]
            del self.embeddings[doc_id]
            return True
        return False

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all documents with metadata."""
        return [
            {
                "doc_id": doc_id,
                "metadata": doc.get("metadata", {}),
                "content_length": len(doc.get("content", "")),
            }
            for doc_id, doc in self.documents.items()
        ]

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec_a or not vec_b:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(x**2 for x in vec_a) ** 0.5
        norm_b = sum(x**2 for x in vec_b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


class RAGPipeline:
    """
    RAG (Retrieval-Augmented Generation) pipeline for HR platform.

    Handles:
    1. Document ingestion from various sources
    2. Text chunking with overlap
    3. Embedding generation
    4. Vector storage (ChromaDB or in-memory)
    5. Semantic search with scoring

    Collections:
    - hr_policies: Company HR policies
    - employee_handbook: Employee handbook and guidelines
    - compliance_docs: Legal and compliance documents
    - benefits_guides: Benefits program documentation
    """

    def __init__(
        self,
        collection_name: str = "hr_policies",
        embedding_model: str = "all-MiniLM-L6-v2",
        use_chromadb: bool = True,
    ):
        """
        Initialize RAG pipeline.

        Args:
            collection_name: Default collection name
            embedding_model: Sentence-transformers model name
            use_chromadb: Use ChromaDB if available, else in-memory
        """
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        self.use_chromadb = use_chromadb

        logger.info(f"RAG: Initializing with collection='{collection_name}'")

        # Initialize embeddings
        self._init_embeddings()

        # Initialize vector store
        self._init_vector_store()

        # Track collections
        self.collections: Dict[str, Any] = {}
        self._init_collections()

        logger.info("RAG: Initialization complete")

    def _init_embeddings(self) -> None:
        """Initialize embedding model."""
        try:
            from sentence_transformers import SentenceTransformer

            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            logger.info(f"RAG: Embedding model loaded: {self.embedding_model_name}")
        except Exception as e:
            logger.warning(f"RAG: Failed to load embeddings: {e}, using dummy")
            self.embedding_model = None

    def _init_vector_store(self) -> None:
        """Initialize vector store (ChromaDB or in-memory)."""
        if self.use_chromadb:
            try:
                import chromadb
                from chromadb.config import Settings

                persist_path = Path("./chromadb_hr")
                persist_path.mkdir(parents=True, exist_ok=True)

                self.chroma_client = chromadb.PersistentClient(
                    path=str(persist_path),
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True,
                    ),
                )

                self.vector_store = self.chroma_client
                self.use_chromadb = True
                logger.info(f"RAG: ChromaDB initialized at {persist_path}")

            except Exception as e:
                logger.warning(f"RAG: ChromaDB init failed: {e}, using in-memory")
                self.vector_store = InMemoryVectorStore()
                self.use_chromadb = False
        else:
            self.vector_store = InMemoryVectorStore()
            logger.info("RAG: Using in-memory vector store")

    def _init_collections(self) -> None:
        """Initialize default collections."""
        collection_names = [
            "hr_policies",
            "employee_handbook",
            "compliance_docs",
            "benefits_guides",
        ]

        for name in collection_names:
            try:
                if self.use_chromadb:
                    col = self.vector_store.get_or_create_collection(
                        name=name,
                        metadata={
                            "hnsw:space": "cosine",
                            "description": f"Collection for {name}",
                        },
                    )
                    self.collections[name] = col
                else:
                    self.collections[name] = {"documents": [], "name": name}

                logger.info(f"RAG: Initialized collection: {name}")
            except Exception as e:
                logger.error(f"RAG: Failed to init collection {name}: {e}")

    # ==================== Search ====================

    def search(
        self,
        query: str,
        collection: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> List[RAGResult]:
        """
        Search for relevant documents.

        Args:
            query: Search query text
            collection: Collection name (default: default collection)
            top_k: Number of results
            min_score: Minimum similarity score (0.0-1.0)

        Returns:
            List of RAGResult objects with content, source, score, metadata
        """
        collection_name = collection or self.collection_name

        logger.info(f"RAG: Searching '{query[:50]}...' in {collection_name}")

        # Get or create collection
        if collection_name not in self.collections:
            logger.warning(f"RAG: Collection {collection_name} not found, using default")
            collection_name = self.collection_name

        try:
            if self.use_chromadb:
                return self._search_chromadb(query, collection_name, top_k, min_score)
            else:
                return self._search_inmemory(query, collection_name, top_k, min_score)
        except Exception as e:
            logger.error(f"RAG: Search failed: {e}")
            return []

    def _search_chromadb(
        self,
        query: str,
        collection_name: str,
        top_k: int,
        min_score: float,
    ) -> List[RAGResult]:
        """Search using ChromaDB."""
        col = self.collections.get(collection_name)
        if not col:
            return []

        try:
            results = col.query(
                query_texts=[query],
                n_results=top_k,
                where={"score": {"$gte": min_score}} if min_score > 0 else None,
            )

            rag_results = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    score = (
                        results.get("distances", [[]])[0][i] if results.get("distances") else 0.0
                    )
                    metadata = (
                        results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                    )
                    source = metadata.get("source", f"doc_{i}")

                    # ChromaDB returns distances, convert to similarity
                    similarity = 1.0 - score if score else 0.8

                    if similarity >= min_score:
                        rag_results.append(
                            RAGResult(
                                content=doc,
                                source=source,
                                score=similarity,
                                metadata=metadata,
                            )
                        )

            logger.info(f"RAG: ChromaDB returned {len(rag_results)} results")
            return rag_results

        except Exception as e:
            logger.error(f"RAG: ChromaDB search failed: {e}")
            return []

    def _search_inmemory(
        self,
        query: str,
        collection_name: str,
        top_k: int,
        min_score: float,
    ) -> List[RAGResult]:
        """Search using in-memory store."""
        if not self.embedding_model:
            logger.warning("RAG: No embedding model, returning empty results")
            return []

        try:
            # Embed query
            query_embedding = self.embedding_model.encode(query).tolist()

            # Search in-memory store
            results = self.vector_store.search(query_embedding, top_k, min_score)

            rag_results = []
            for doc_id, score in results:
                doc = self.vector_store.get_document(doc_id)
                if doc:
                    rag_results.append(
                        RAGResult(
                            content=doc.get("content", ""),
                            source=doc.get("metadata", {}).get("source", doc_id),
                            score=score,
                            metadata=doc.get("metadata", {}),
                        )
                    )

            logger.info(f"RAG: In-memory search returned {len(rag_results)} results")
            return rag_results

        except Exception as e:
            logger.error(f"RAG: In-memory search failed: {e}")
            return []

    # ==================== Ingestion ====================

    def ingest_document(
        self,
        file_path: str,
        doc_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        collection: Optional[str] = None,
    ) -> int:
        """
        Ingest document from file.

        Supports: .txt, .md, .pdf (placeholder)

        Args:
            file_path: Path to document file
            doc_type: Document type (policy, handbook, compliance, benefit)
            metadata: Additional metadata (title, section, page_number, last_updated)
            collection: Collection to store in (default: based on doc_type)

        Returns:
            Number of chunks created
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"RAG: File not found: {file_path}")
            return 0

        # Determine collection
        collection_name = collection
        if not collection_name:
            if doc_type == "policy":
                collection_name = "hr_policies"
            elif doc_type == "handbook":
                collection_name = "employee_handbook"
            elif doc_type == "compliance":
                collection_name = "compliance_docs"
            elif doc_type == "benefit":
                collection_name = "benefits_guides"
            else:
                collection_name = self.collection_name

        logger.info(f"RAG: Ingesting {file_path} as {doc_type} → {collection_name}")

        # Extract text
        try:
            text = self._extract_text(file_path)
        except Exception as e:
            logger.error(f"RAG: Text extraction failed: {e}")
            return 0

        # Chunk text
        chunks = self._chunk_text(text, chunk_size=512, overlap=50)

        # Prepare metadata
        doc_metadata = metadata or {}
        doc_metadata.update(
            {
                "source": path.name,
                "doc_type": doc_type,
                "file_path": str(path),
            }
        )

        # Store chunks
        chunk_count = 0
        try:
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                if self.use_chromadb:
                    col = self.collections.get(collection_name)
                    if col:
                        chunk_metadata = doc_metadata.copy()
                        chunk_metadata["chunk_index"] = i

                        col.add(
                            ids=[f"{path.stem}_chunk_{i}"],
                            documents=[chunk],
                            metadatas=[chunk_metadata],
                        )
                        chunk_count += 1
                else:
                    if not self.embedding_model:
                        logger.warning("RAG: No embedding model, skipping storage")
                        continue

                    embedding = self.embedding_model.encode(chunk).tolist()
                    chunk_metadata = doc_metadata.copy()
                    chunk_metadata["chunk_index"] = i

                    self.vector_store.add_document(chunk, embedding, chunk_metadata)
                    chunk_count += 1

            logger.info(f"RAG: Ingested {chunk_count} chunks from {path.name}")
            return chunk_count

        except Exception as e:
            logger.error(f"RAG: Chunk storage failed: {e}")
            return 0

    # ==================== Text Processing ====================

    @staticmethod
    def _chunk_text(
        text: str,
        chunk_size: int = 512,
        overlap: int = 50,
    ) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Input text
            chunk_size: Characters per chunk
            overlap: Character overlap between chunks

        Returns:
            List of text chunks
        """
        if not text or len(text) <= chunk_size:
            return [text] if text else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)

            # Move start position with overlap
            start = end - overlap

        return chunks

    @staticmethod
    def _extract_text(file_path: str) -> str:
        """
        Extract text from file.

        Supports: .txt, .md, .pdf (placeholder)

        Args:
            file_path: Path to file

        Returns:
            Extracted text

        Raises:
            ValueError: If file format not supported
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        elif suffix == ".md":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        elif suffix == ".pdf":
            # Placeholder for PDF extraction
            # In real implementation, use PyPDF2, pdfplumber, etc.
            logger.warning("RAG: PDF support not implemented, returning placeholder")
            return f"PDF content from {path.name} - not yet extracted"

        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    # ==================== Document Management ====================

    def delete_document(self, doc_id: str, collection: Optional[str] = None) -> bool:
        """
        Delete document by ID.

        Args:
            doc_id: Document ID
            collection: Collection name

        Returns:
            True if deleted, False otherwise
        """
        collection_name = collection or self.collection_name

        try:
            if self.use_chromadb:
                col = self.collections.get(collection_name)
                if col:
                    col.delete(ids=[doc_id])
                    logger.info(f"RAG: Deleted {doc_id} from {collection_name}")
                    return True
            else:
                if self.vector_store.delete_document(doc_id):
                    logger.info(f"RAG: Deleted {doc_id}")
                    return True
        except Exception as e:
            logger.error(f"RAG: Delete failed: {e}")

        return False

    def list_documents(self, collection: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List documents in collection.

        Args:
            collection: Collection name (all if None)

        Returns:
            List of document metadata dicts
        """
        documents = []

        if collection:
            collections = [collection]
        else:
            collections = list(self.collections.keys())

        for col_name in collections:
            try:
                if self.use_chromadb:
                    col = self.collections.get(col_name)
                    if col:
                        # ChromaDB doesn't have direct list, count instead
                        count = col.count()
                        documents.append(
                            {
                                "collection": col_name,
                                "count": count,
                            }
                        )
                else:
                    docs = self.vector_store.list_documents()
                    documents.extend([{"collection": col_name, **d} for d in docs])
            except Exception as e:
                logger.error(f"RAG: List failed for {col_name}: {e}")

        return documents

    # ==================== Utilities ====================

    def get_collection_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all collections.

        Returns:
            Dict mapping collection_name -> {doc_count, chunk_count, ...}
        """
        stats = {}

        for col_name in self.collections.keys():
            try:
                if self.use_chromadb:
                    col = self.collections.get(col_name)
                    if col:
                        count = col.count()
                        stats[col_name] = {
                            "doc_count": count,
                            "chunk_count": count,
                            "backend": "chromadb",
                        }
                else:
                    docs = self.vector_store.list_documents()
                    stats[col_name] = {
                        "doc_count": len(docs),
                        "chunk_count": len(docs),
                        "backend": "in-memory",
                    }
            except Exception as e:
                logger.error(f"RAG: Stats failed for {col_name}: {e}")
                stats[col_name] = {"error": str(e)}

        return stats

    def health_check(self) -> bool:
        """
        Check RAG pipeline health.

        Returns:
            True if healthy, False otherwise
        """
        try:
            if self.use_chromadb:
                # Try to access a collection
                col = list(self.collections.values())[0] if self.collections else None
                if col:
                    col.count()
            else:
                # In-memory store is always healthy
                pass

            logger.info("RAG: Health check passed")
            return True
        except Exception as e:
            logger.error(f"RAG: Health check failed: {e}")
            return False
