"""
Agent Service - Singleton orchestrator for multi-agent system
Iteration 3, Wave 2: Wires RouterAgent with all specialist agents
"""

import logging
import json
from typing import Any, Dict, List, Optional, TypedDict
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class UserContext(TypedDict, total=False):
    """User context for agent execution."""

    user_id: str
    role: str  # "employee", "manager", "hr_generalist", "hr_admin"
    department: str
    can_view_all: bool
    can_modify: bool


class AgentService:
    """
    Singleton service that orchestrates multi-agent system.

    Responsibilities:
    1. Initialize RouterAgent with specialist agents
    2. Initialize RAG pipeline for document retrieval
    3. Initialize LLM gateway for model access
    4. Process user queries through routing + dispatch
    5. Log conversations to database
    6. Track metrics and statistics
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern - ensure only one instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize agent service (only once)."""
        if self._initialized:
            return

        logger.info("Initializing AgentService...")

        # Import here to avoid circular dependencies
        # NOTE: langchain_openai is imported LAZILY below because it can hang
        # during import in environments with SOCKS proxies (httpx issue).
        from src.agents.router_agent import RouterAgent
        from src.core.rag_pipeline import RAGPipeline
        from src.core.llm_gateway import LLMGateway
        from config.settings import get_settings

        settings = get_settings()

        # Initialize LangSmith tracing (opt-in via env var)
        try:
            from src.core.tracing import LangSmithTracer

            LangSmithTracer.setup_tracing(
                enabled=getattr(settings, "LANGCHAIN_TRACING_V2", False),
                api_key=getattr(settings, "LANGCHAIN_API_KEY", ""),
                project=getattr(settings, "LANGCHAIN_PROJECT", "hr-multi-agent"),
            )
        except Exception as e:
            logger.warning(f"LangSmith tracing setup skipped: {e}")

        # Initialize LLM (OpenAI primary, Google Gemini fallback)
        # Skip LLM init entirely if API keys are placeholders to avoid
        # hanging on network/proxy issues during constructor.
        logger.info("Creating LLM instance...")
        self.llm = None
        _placeholder_keys = {"", "not-set", "your-openai-api-key", "your-google-api-key"}

        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        google_key = getattr(settings, "GOOGLE_API_KEY", "")

        if openai_key and openai_key not in _placeholder_keys:
            try:
                from langchain_openai import ChatOpenAI

                model = getattr(settings, "LLM_DEFAULT_MODEL", "gpt-4o-mini")
                self.llm = ChatOpenAI(
                    model=model,
                    api_key=openai_key,
                    temperature=0.3,
                )
                logger.info(f"✅ LLM initialized: {model} (OpenAI)")
            except Exception as e:
                logger.warning(f"⚠️  OpenAI LLM init failed: {e}")
        else:
            logger.info("⏭️  OpenAI API key not configured, skipping OpenAI LLM")

        if self.llm is None and google_key and google_key not in _placeholder_keys:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI

                fallback_model = getattr(settings, "LLM_FALLBACK_MODEL", "gemini-2.0-flash")
                self.llm = ChatGoogleGenerativeAI(
                    model=fallback_model,
                    google_api_key=google_key,
                    temperature=0.3,
                )
                logger.info(f"✅ LLM initialized: {fallback_model} (Google Gemini fallback)")
            except Exception as e2:
                logger.warning(f"⚠️  Google Gemini LLM init failed: {e2}")
        elif self.llm is None:
            logger.info("⏭️  No valid LLM API keys configured — running in static-response mode")

        # Initialize Router Agent
        logger.info("Creating RouterAgent...")
        try:
            self.router_agent = RouterAgent(self.llm)
            logger.info("✅ RouterAgent initialized")
        except Exception as e:
            logger.error(f"❌ RouterAgent initialization failed: {e}")
            self.router_agent = None

        # Initialize RAG Pipeline
        logger.info("Creating RAGPipeline...")
        try:
            self.rag_pipeline = RAGPipeline(collection_name="hr_policies", use_chromadb=True)
            logger.info("✅ RAGPipeline initialized")
        except Exception as e:
            logger.error(f"❌ RAGPipeline initialization failed: {e}")
            self.rag_pipeline = None

        # Initialize LLM Gateway
        logger.info("Creating LLMGateway...")
        try:
            self.llm_gateway = LLMGateway(enable_caching=True)
            logger.info("✅ LLMGateway initialized")
        except Exception as e:
            logger.error(f"❌ LLMGateway initialization failed: {e}")
            self.llm_gateway = None

        # Initialize conversation tracker
        self.conversation_log: List[Dict[str, Any]] = []
        self.request_stats = {
            "total_requests": 0,
            "total_queries": 0,
            "agent_usage": {},
            "confidence_scores": [],
        }

        self._initialized = True
        logger.info("✅ AgentService fully initialized")

    # ==================== QUERY PROCESSING ====================

    def process_query(
        self,
        query: str,
        user_context: Optional[UserContext] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        timeout_seconds: int = 30,
    ) -> Dict[str, Any]:
        """
        Process user query through multi-agent system.

        Args:
            query: User query/question
            user_context: User info (id, role, department, etc.)
            conversation_history: Prior conversation messages
            timeout_seconds: Maximum execution time

        Returns:
            Result dict with:
            - answer: Response from agent(s)
            - sources: Referenced documents
            - confidence: Confidence score
            - agent_type: Which agent handled it
            - intents: Classified intent(s)
            - execution_time_ms: Processing time
            - request_id: Unique request ID
        """
        request_id = str(uuid.uuid4())
        logger.info(f"QUERY {request_id}: Processing: {query[:60]}...")

        start_time = datetime.now()

        # Validate inputs
        if not query:
            return {
                "answer": "Query cannot be empty",
                "confidence": 0.0,
                "error": "Invalid query",
                "request_id": request_id,
            }

        # Set defaults
        if user_context is None:
            user_context = {
                "user_id": "unknown",
                "role": "employee",
                "department": "unknown",
            }

        if conversation_history is None:
            conversation_history = []

        # Process query through router agent
        try:
            if not self.router_agent:
                logger.warning("Router agent not available, returning error")
                return {
                    "answer": "Agent system not initialized",
                    "confidence": 0.0,
                    "error": "Service unavailable",
                    "request_id": request_id,
                }

            # Run router agent
            result = self.router_agent.run(
                query=query,
                user_context=user_context,
                conversation_history=conversation_history,
            )

            # Calculate execution time
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Merge result with metadata
            result.update(
                {
                    "request_id": request_id,
                    "execution_time_ms": elapsed_ms,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Log conversation
            self._log_conversation(request_id, query, result, user_context)

            # Update statistics
            self._update_stats(result)

            logger.info(
                f"QUERY {request_id}: Complete in {elapsed_ms:.1f}ms, "
                f"confidence={result.get('confidence', 0):.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"QUERY {request_id}: Processing failed: {e}")

            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

            error_result = {
                "answer": f"Error processing query: {e}",
                "confidence": 0.0,
                "error": str(e),
                "request_id": request_id,
                "execution_time_ms": elapsed_ms,
                "timestamp": datetime.now().isoformat(),
            }

            # Still log failed query
            self._log_conversation(request_id, query, error_result, user_context)

            return error_result

    # ==================== CONVERSATION LOGGING ====================

    def _log_conversation(
        self,
        request_id: str,
        query: str,
        result: Dict[str, Any],
        user_context: UserContext,
    ) -> None:
        """
        Log conversation to in-memory log (and optionally database).

        Args:
            request_id: Unique request ID
            query: Original user query
            result: Agent result
            user_context: User information
        """
        try:
            log_entry = {
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "user_id": user_context.get("user_id", "unknown"),
                "role": user_context.get("role", "unknown"),
                "query": query,
                "answer": result.get("answer", ""),
                "confidence": result.get("confidence", 0),
                "agent_type": result.get("agent_type", "unknown"),
                "intents": result.get("intents", []),
                "execution_time_ms": result.get("execution_time_ms", 0),
                "error": result.get("error"),
            }

            self.conversation_log.append(log_entry)

            # In real implementation, would store in database
            # try:
            #     from src.models import Conversation, ConversationMessage, db
            #     conversation = Conversation(
            #         request_id=request_id,
            #         user_id=user_context.get("user_id"),
            #         ...
            #     )
            #     db.session.add(conversation)
            #     db.session.commit()
            # except Exception as e:
            #     logger.warning(f"Failed to log to database: {e}")

        except Exception as e:
            logger.error(f"Failed to log conversation: {e}")

    # ==================== STATISTICS ====================

    def _update_stats(self, result: Dict[str, Any]) -> None:
        """
        Update service statistics.

        Args:
            result: Agent result
        """
        try:
            self.request_stats["total_queries"] += 1

            agent_type = result.get("agent_type", "unknown")
            if agent_type not in self.request_stats["agent_usage"]:
                self.request_stats["agent_usage"][agent_type] = 0
            self.request_stats["agent_usage"][agent_type] += 1

            confidence = result.get("confidence", 0)
            self.request_stats["confidence_scores"].append(confidence)

        except Exception as e:
            logger.warning(f"Failed to update stats: {e}")

    def get_agent_stats(self) -> Dict[str, Any]:
        """
        Get agent usage statistics.

        Returns:
            Dict with:
            - total_queries: Total queries processed
            - avg_confidence: Average confidence score
            - popular_agents: Most used agents
            - agent_breakdown: Usage by agent type
        """
        stats = {
            "total_queries": self.request_stats["total_queries"],
            "agent_breakdown": self.request_stats["agent_usage"],
            "conversation_count": len(self.conversation_log),
        }

        if self.request_stats["confidence_scores"]:
            scores = self.request_stats["confidence_scores"]
            stats["avg_confidence"] = sum(scores) / len(scores)
            stats["min_confidence"] = min(scores)
            stats["max_confidence"] = max(scores)
        else:
            stats["avg_confidence"] = 0.0
            stats["min_confidence"] = 0.0
            stats["max_confidence"] = 0.0

        # Most used agents
        if self.request_stats["agent_usage"]:
            popular = sorted(
                self.request_stats["agent_usage"].items(), key=lambda x: x[1], reverse=True
            )
            stats["popular_agents"] = [
                {"agent": name, "count": count} for name, count in popular[:5]
            ]
        else:
            stats["popular_agents"] = []

        # LLM Gateway stats
        if self.llm_gateway:
            try:
                stats["llm_stats"] = self.llm_gateway.get_stats()
            except Exception as e:
                logger.warning(f"Failed to get LLM stats: {e}")

        return stats

    # ==================== AGENT INFORMATION ====================

    def get_available_agents(self) -> List[Dict[str, Any]]:
        """
        Get list of available specialist agents.

        Returns:
            List of agent type dicts with name and description
        """
        return [
            {
                "type": "employee_info",
                "name": "Employee Info Agent",
                "description": "Retrieves employee profiles, contact info, compensation",
            },
            {
                "type": "policy",
                "name": "Policy Agent",
                "description": "Answers HR policies, compliance, procedures",
            },
            {
                "type": "leave",
                "name": "Leave Agent",
                "description": "Manages PTO, sick leave, vacation requests",
            },
            {
                "type": "onboarding",
                "name": "Onboarding Agent",
                "description": "Handles new hire processes, orientation, documentation",
            },
            {
                "type": "benefits",
                "name": "Benefits Agent",
                "description": "Explains health insurance, retirement, perks",
            },
            {
                "type": "performance",
                "name": "Performance Agent",
                "description": "Manages reviews, goals, feedback",
            },
            {
                "type": "analytics",
                "name": "Analytics Agent",
                "description": "Generates reports, statistics, trends",
            },
            {
                "type": "router",
                "name": "Router Agent",
                "description": "Classifies intent, checks permissions, dispatches queries",
            },
        ]

    # ==================== RAG INTEGRATION ====================

    def search_documents(
        self,
        query: str,
        collection: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search RAG pipeline for relevant documents.

        Args:
            query: Search query
            collection: Collection name
            top_k: Number of results

        Returns:
            List of document results
        """
        if not self.rag_pipeline:
            logger.warning("RAG pipeline not available")
            return []

        try:
            results = self.rag_pipeline.search(
                query=query,
                collection=collection,
                top_k=top_k,
            )

            return [
                {
                    "content": r.content,
                    "source": r.source,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in results
            ]

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return []

    # ==================== HEALTH CHECK ====================

    def is_healthy(self) -> bool:
        """
        Check if agent service is healthy.

        Returns:
            True if operational, False otherwise
        """
        checks = {
            "router_agent": self.router_agent is not None,
            "llm": self.llm is not None,
            "rag": self.rag_pipeline is not None,
        }

        all_ok = all(checks.values())
        logger.info(f"Health check: {checks} → {'healthy' if all_ok else 'degraded'}")

        return all_ok
