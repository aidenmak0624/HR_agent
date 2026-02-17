"""
RAG Service - Wrapper around RAG pipeline for easy use by agents
Iteration 3, Wave 2: Document ingestion, search, and collection management
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class RAGService:
    """
    RAG service providing document management and search.

    Features:
    - Document ingestion from files/directories
    - Semantic search across collections
    - Collection statistics
    - Automatic sample document creation
    """

    def __init__(self):
        """Initialize RAG service."""
        logger.info("Initializing RAGService...")

        from src.core.rag_pipeline import RAGPipeline

        self.rag_pipeline = RAGPipeline(
            collection_name="hr_policies",
            use_chromadb=True,
        )

        # Create sample documents if they don't exist
        self._create_sample_documents()

        logger.info("✅ RAGService initialized")

    # ==================== SEARCH ====================

    def search(
        self,
        query: str,
        collections: Optional[List[str]] = None,
        min_score: float = 0.3,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents.

        Args:
            query: Search query
            collections: Specific collections to search
            min_score: Minimum similarity score
            top_k: Number of results

        Returns:
            List of result dicts with content, source, score, metadata
        """
        logger.info(f"Search: {query[:50]}... (top_k={top_k})")

        results = []

        try:
            if collections:
                # Search specific collections
                for collection in collections:
                    col_results = self.rag_pipeline.search(
                        query=query,
                        collection=collection,
                        top_k=top_k,
                        min_score=min_score,
                    )
                    results.extend(
                        [
                            {
                                "content": r.content,
                                "source": r.source,
                                "score": r.score,
                                "metadata": r.metadata,
                                "collection": collection,
                            }
                            for r in col_results
                        ]
                    )
            else:
                # Search all collections
                all_results = self.rag_pipeline.search(
                    query=query,
                    top_k=top_k,
                    min_score=min_score,
                )
                results = [
                    {
                        "content": r.content,
                        "source": r.source,
                        "score": r.score,
                        "metadata": r.metadata,
                    }
                    for r in all_results
                ]

            # Sort by score and limit
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:top_k]

            logger.info(f"Search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    # ==================== DOCUMENT INGESTION ====================

    def ingest_file(
        self,
        filepath: str,
        collection: str,
        doc_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingest a single file.

        Args:
            filepath: Path to file
            collection: Target collection
            doc_type: Document type (policy, handbook, etc.)

        Returns:
            Result dict with success, chunk_count, etc.
        """
        logger.info(f"Ingest file: {filepath} → {collection}")

        try:
            path = Path(filepath)
            if not path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {filepath}",
                }

            chunk_count = self.rag_pipeline.ingest_document(
                file_path=filepath,
                doc_type=doc_type or collection,
                collection=collection,
                metadata={"original_path": str(path)},
            )

            return {
                "success": True,
                "filepath": filepath,
                "collection": collection,
                "chunk_count": chunk_count,
            }

        except Exception as e:
            logger.error(f"File ingestion failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def ingest_directory(
        self,
        dirpath: str,
        collection: str,
        pattern: str = "*.txt",
    ) -> Dict[str, Any]:
        """
        Ingest all files in directory.

        Args:
            dirpath: Path to directory
            collection: Target collection
            pattern: File pattern (default: *.txt)

        Returns:
            Result dict with success, file_count, total_chunks, etc.
        """
        logger.info(f"Ingest directory: {dirpath} → {collection}")

        try:
            dir_path = Path(dirpath)
            if not dir_path.exists():
                return {
                    "success": False,
                    "error": f"Directory not found: {dirpath}",
                }

            files = list(dir_path.glob(pattern))
            logger.info(f"Found {len(files)} files matching {pattern}")

            total_chunks = 0
            successful_files = 0
            failed_files = []

            for file_path in files:
                try:
                    chunk_count = self.rag_pipeline.ingest_document(
                        file_path=str(file_path),
                        doc_type=collection,
                        collection=collection,
                        metadata={"directory": str(dir_path)},
                    )
                    total_chunks += chunk_count
                    successful_files += 1
                except Exception as e:
                    logger.warning(f"Failed to ingest {file_path}: {e}")
                    failed_files.append(str(file_path))

            return {
                "success": True,
                "directory": dirpath,
                "collection": collection,
                "file_count": len(files),
                "successful_files": successful_files,
                "failed_files": failed_files,
                "total_chunks": total_chunks,
            }

        except Exception as e:
            logger.error(f"Directory ingestion failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # ==================== COLLECTION MANAGEMENT ====================

    def get_collection_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all collections.

        Returns:
            Dict mapping collection_name -> stats
        """
        logger.info("Getting collection statistics...")

        try:
            stats = self.rag_pipeline.get_collection_stats()
            logger.info(f"Retrieved stats for {len(stats)} collections")
            return stats

        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}

    def reindex(self, collection: str) -> Dict[str, Any]:
        """
        Reindex a collection (placeholder for future implementation).

        Args:
            collection: Collection to reindex

        Returns:
            Result dict
        """
        logger.info(f"Reindex collection: {collection}")

        try:
            # In real implementation, would rebuild indices
            # For now, just verify collection exists
            stats = self.rag_pipeline.get_collection_stats()

            if collection in stats:
                return {
                    "success": True,
                    "collection": collection,
                    "message": f"Reindex triggered for {collection}",
                }
            else:
                return {
                    "success": False,
                    "error": f"Collection not found: {collection}",
                }

        except Exception as e:
            logger.error(f"Reindex failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # ==================== SAMPLE DOCUMENTS ====================

    def _create_sample_documents(self) -> None:
        """Create sample HR policy documents for demo."""
        logger.info("Creating sample HR documents...")

        data_dir = Path("./data/policies")
        data_dir.mkdir(parents=True, exist_ok=True)

        sample_docs = {
            "remote_work_policy.txt": """
REMOTE WORK POLICY

1. OVERVIEW
This policy outlines the guidelines for remote work arrangements
within our organization.

2. ELIGIBILITY
- Employees with 6+ months tenure are eligible
- Role must allow remote work (approved by manager)
- No disciplinary action in last 12 months

3. WORK SCHEDULE
- Must maintain standard working hours (9 AM - 5 PM)
- Flexible scheduling approved on case-by-case basis
- Core hours: 10 AM - 3 PM for collaboration

4. EQUIPMENT & SUPPORT
- Company provides laptop or budget for setup
- Internet stipend available
- Annual equipment refresh available

5. EXPECTATIONS
- Respond to messages within 2 hours
- Attend required in-person meetings
- Maintain professional environment
- Follow all security policies

6. TERMINATION
Remote work arrangement can be modified or terminated with 2 weeks notice.
""",
            "pto_policy.txt": """
PAID TIME OFF (PTO) POLICY

1. ACCRUAL
- Accrual rate: 1.67 days per month (20 days annually)
- Accrual begins on first day of employment
- Maximum carryover: 5 days per year

2. REQUEST PROCESS
- Submit requests at least 2 weeks in advance
- Use HR system for approval workflow
- Emergency PTO requires manager notification same day

3. RESTRICTIONS
- Black out dates: Dec 24-26, Jul 4
- No more than 10 consecutive days without executive approval
- PTO cannot be used for disciplinary suspension

4. PAYOUT
- Unused PTO paid out upon separation
- Payment calculated at current base salary
- No payout if terminated for cause

5. HOLIDAYS
Company observes 10 federal holidays plus 1 floating holiday.
""",
            "benefits_guide.txt": """
EMPLOYEE BENEFITS GUIDE

1. HEALTH INSURANCE
- Medical: Choice of 3 plans (HMO, PPO, High Deductible)
- Dental: 100% preventive, 80% basic, 50% major
- Vision: 1 eye exam per year, frames every 2 years

2. RETIREMENT
- 401(k) available with company match up to 6%
- Vesting: Immediate for employee contributions, 3-year cliff for company
- Annual contribution limit: $23,500 (2024)

3. WELLNESS
- Gym membership reimbursement: $50/month
- Mental health counseling: 10 sessions/year
- Wellness challenges with $500 annual reward

4. FAMILY BENEFITS
- Parental leave: 16 weeks (birth parent), 12 weeks (non-birth)
- Adoption assistance: $5,000 per adoption
- Dependent care FSA: Up to $5,000/year

5. FINANCIAL
- Life insurance: 2x annual salary
- Disability: Short-term (60% salary), Long-term (60% salary)
- Employee Stock Purchase Plan: 10% discount

6. PROFESSIONAL DEVELOPMENT
- Tuition reimbursement: $5,000/year
- Conference attendance: $2,000/year
- LinkedIn Learning: Unlimited
""",
        }

        for filename, content in sample_docs.items():
            filepath = data_dir / filename
            if not filepath.exists():
                try:
                    filepath.write_text(content.strip())
                    logger.info(f"Created sample document: {filename}")

                    # Ingest the document
                    doc_type = "policy" if "policy" in filename else "benefit"
                    collection = "hr_policies" if doc_type == "policy" else "benefits_guides"

                    chunk_count = self.rag_pipeline.ingest_document(
                        file_path=str(filepath),
                        doc_type=doc_type,
                        collection=collection,
                        metadata={"sample": True},
                    )
                    logger.info(f"Ingested {chunk_count} chunks from {filename}")

                except Exception as e:
                    logger.warning(f"Failed to create/ingest {filename}: {e}")

        logger.info("✅ Sample documents created and indexed")
