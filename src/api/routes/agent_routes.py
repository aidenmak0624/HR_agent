# src/api/routes/agent_routes.py - CONSOLIDATED VERSION

"""
Consolidated Agent & Chat Routes
Handles both agent mode and simple RAG mode in one file
"""

from flask import Blueprint, request, jsonify
from src.agent.agent_brain import HRAssistantAgent
import os
import logging
import signal
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint("agent", __name__, url_prefix="/api")

# ===== SINGLETON INSTANCES =====
_agent_instance = None
_rag_instance = None


# ===== TIMEOUT HANDLER =====
'''
@contextmanager
def timeout(seconds):
    
    
    
    """Context manager for operation timeout"""
    def signal_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    # Only works on Unix-like systems
    if hasattr(signal, 'SIGALRM'):
        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
    else:
        # Windows fallback - no timeout
        yield
'''


def get_agent():
    """Get or create agent instance (singleton pattern)."""
    global _agent_instance

    if _agent_instance is None:
        api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            logger.error("❌ GOOGLE_API_KEY not found in environment")
            return None

        try:
            logger.info("🤖 Initializing HR Assistant Agent...")
            _agent_instance = HRAssistantAgent(api_key=api_key)
            logger.info(f"✅ Agent initialized with {len(_agent_instance.tools)} tools")

        except Exception as e:
            logger.exception("❌ Failed to initialize agent")
            _agent_instance = None

    return _agent_instance


def get_rag():
    """Get or create RAG instance (singleton pattern)."""
    global _rag_instance

    if _rag_instance is None:
        try:
            logger.info("📚 Initializing RAG system...")
            from src.core.rag_system import HRKnowledgeBase

            _rag_instance = HRKnowledgeBase(preload_topics=True)
            logger.info("✅ RAG system initialized")
        except Exception as e:
            logger.exception("❌ Failed to initialize RAG")
            _rag_instance = None

    return _rag_instance


# ===== HEALTH CHECK =====


@bp.route("/health", methods=["GET"])
def health():
    """System health check"""
    rag = get_rag()
    agent = get_agent()

    return (
        jsonify(
            {
                "status": "healthy",
                "rag_initialized": rag is not None,
                "agent_initialized": agent is not None,
                "agent_tools": list(agent.tools.keys()) if agent else [],
                "modes": {"simple_rag": "/api/chat", "agent_mode": "/api/agent/chat"},
            }
        ),
        200,
    )


# ===== SIMPLE RAG MODE (NON-AGENT) =====


@bp.route("/chat", methods=["POST"])
def simple_chat():
    """
    Simple RAG endpoint (non-agent mode).
    Fast, direct retrieval without agent orchestration.

    Request:
    {
        "query": "What is our PTO policy?",
        "topic": "benefits",
        "difficulty": "intermediate"
    }

    Response:
    {
        "answer": "...",
        "sources": ["doc1.txt", "doc2.txt"],
        "tools_used": ["rag_search"],
        "confidence": 0.85
    }
    """
    try:
        data = request.json

        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        query = data.get("query")
        topic = data.get("topic", "benefits")
        difficulty = data.get("difficulty", "intermediate")

        if not query:
            return jsonify({"error": "Missing required field: query"}), 400

        logger.info(f"📝 Simple RAG: '{query[:100]}...' | Topic: {topic}")

        # Get RAG instance
        rag = get_rag()
        if rag is None:
            return jsonify({"error": "RAG system not initialized"}), 503

        # Generate answer
        answer = rag.generate_answer(query, topic, difficulty)

        # Extract sources from answer
        sources = []
        if "📚 Sources:" in answer:
            parts = answer.split("📚 Sources:")
            answer_text = parts[0].strip()
            sources_text = parts[1].strip()
            sources = [s.strip() for s in sources_text.split(",")]
        else:
            answer_text = answer

        logger.info(f"✅ RAG completed | Sources: {len(sources)}")

        return (
            jsonify(
                {
                    "answer": answer_text,
                    "sources": sources,
                    "tools_used": ["rag_search"],
                    "confidence": 0.85,  # RAG has fixed confidence
                    "reasoning_trace": ["Simple RAG retrieval and generation"],
                    "metadata": {"mode": "simple_rag", "topic": topic, "difficulty": difficulty},
                }
            ),
            200,
        )

    except Exception as e:
        logger.exception("❌ Error in simple_chat")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


# ===== AGENT MODE (AUTONOMOUS) =====


@bp.route("/agent/chat", methods=["POST"])
def agent_chat():
    """
    Agent endpoint with autonomous tool selection.

    Request:
    {
        "query": "What is our PTO policy?",
        "topic": "benefits",
        "difficulty": "intermediate"
    }

    Response:
    {
        "answer": "...",
        "sources": ["doc1.txt"],
        "reasoning_trace": ["PLAN: ...", "DECISION: ...", "REFLECTION: ..."],
        "confidence": 0.85,
        "tools_used": ["rag_search", "web_search"],
        "metadata": {...}
    }
    """
    try:
        data = request.json

        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        query = data.get("query")
        topic = data.get("topic", "benefits")
        difficulty = data.get("difficulty", "intermediate")

        if not query:
            return jsonify({"error": "Missing required field: query"}), 400

        if difficulty not in ["beginner", "intermediate", "advanced"]:
            return (
                jsonify(
                    {
                        "error": f"Invalid difficulty: {difficulty}",
                        "valid_options": ["beginner", "intermediate", "advanced"],
                    }
                ),
                400,
            )

        logger.info(f"🤖 Agent mode: '{query[:100]}...' | Topic: {topic}")

        # Get agent instance
        agent = get_agent()
        if agent is None:
            return jsonify({"error": "Agent not initialized"}), 503

        # Execute with timeout protection
        """
        try:
            with timeout(45):  # 45 second timeout
                result = agent.run(query=query, topic=topic, difficulty=difficulty)
        except TimeoutError as e:
            logger.error(f"⏰ Agent timeout: {e}")
            return jsonify({
                'error': 'Request timed out',
                'message': 'The agent took too long to respond. Try simplifying your query.'
            }), 504
        """
        # Execute agent (timeout disabled in Flask threads)
        result = agent.run(query=query, topic=topic, difficulty=difficulty)
        # Enhance response with metadata
        result["metadata"] = {
            "mode": "agent",
            "search_strategy": "RAG first, web search on quality threshold",
            "topic": topic,
            "difficulty": difficulty,
        }

        tools_used = result.get("tools_used", [])
        logger.info(
            f"✅ Agent completed | Tools: {tools_used} | Confidence: {result.get('confidence', 0):.2f}"
        )

        return jsonify(result), 200

    except ValueError as e:
        logger.warning(f"⚠️ Validation error: {e}")
        return jsonify({"error": "Validation error", "details": str(e)}), 400

    except Exception as e:
        logger.exception("❌ Error in agent_chat")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


# ===== DEBUG ENDPOINT =====


@bp.route("/agent/debug", methods=["POST"])
def agent_debug():
    """
    Debug endpoint with full reasoning trace.
    Same as /agent/chat but with extra debug info.
    """
    try:
        data = request.json or {}

        query = data.get("query", "What is the PTO policy?")
        topic = data.get("topic", "benefits")
        difficulty = data.get("difficulty", "intermediate")

        agent = get_agent()
        if agent is None:
            return jsonify({"error": "Agent not initialized"}), 503

        # Run agent
        result = agent.run(query=query, topic=topic, difficulty=difficulty)

        # Build comprehensive debug response
        debug_response = {
            "result": result,
            "debug_info": {
                "agent_config": {
                    "tools_available": list(agent.tools.keys()),
                    "model": "gemini-2.5-pro",
                    "max_iterations": 5,
                },
                "request": {"query": query, "topic": topic, "difficulty": difficulty},
                "execution_trace": result.get("reasoning_trace", []),
                "tools_used": result.get("tools_used", []),
                "confidence_score": result.get("confidence", 0.0),
            },
        }

        return jsonify(debug_response), 200

    except Exception as e:
        logger.exception("❌ Error in debug endpoint")
        return jsonify({"error": str(e)}), 500


# ===== UTILITY ENDPOINTS =====


@bp.route("/agent/tools", methods=["GET"])
def list_tools():
    """List all available agent tools"""
    agent = get_agent()

    if agent is None:
        return jsonify({"error": "Agent not initialized", "tools": []}), 503

    tools_info = {}
    for name, tool in agent.tools.items():
        tools_info[name] = {
            "name": name,
            "description": getattr(tool, "description", "No description"),
            "available": True,
        }

    return (
        jsonify(
            {
                "tools": tools_info,
                "count": len(tools_info),
                "search_priority": ["rag_search", "web_search"],
            }
        ),
        200,
    )


@bp.route("/topics", methods=["GET"])
def get_topics():
    """Get available topics (moved from topic_routes for consolidation)"""
    TOPICS = [
        {
            "id": "employment_law",
            "name": "Employment Law",
            "icon": "⚖️",
            "description": "FMLA, ADA, Title VII, FLSA, and other federal employment laws",
        },
        {
            "id": "benefits",
            "name": "Benefits & Compensation",
            "icon": "💰",
            "description": "Health insurance, 401(k), ESPP, leave benefits, and perks",
        },
        {
            "id": "company_policies",
            "name": "Company Policies",
            "icon": "📋",
            "description": "Code of conduct, remote work, performance reviews, and more",
        },
        {
            "id": "payroll_compliance",
            "name": "Payroll & Compliance",
            "icon": "📊",
            "description": "Pay schedules, taxes, I-9 verification, and background checks",
        },
        {
            "id": "employee_handbook",
            "name": "Employee Handbook",
            "icon": "📖",
            "description": "Onboarding, workplace safety, ERGs, and company events",
        },
    ]

    return jsonify({"topics": TOPICS}), 200


# ===== ERROR HANDLERS =====


@bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return (
        jsonify(
            {
                "error": "Endpoint not found",
                "available_endpoints": [
                    "/api/health",
                    "/api/chat (simple RAG)",
                    "/api/agent/chat (agent mode)",
                    "/api/agent/debug",
                    "/api/agent/tools",
                    "/api/topics",
                ],
            }
        ),
        404,
    )


@bp.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.exception("Internal server error")
    return jsonify({"error": "Internal server error", "message": str(error)}), 500


# ===== MODULE INFO =====

if __name__ == "__main__":
    print("This is a Flask blueprint module.")
    print("Import and register with: app.register_blueprint(bp)")
    print("\nAvailable endpoints:")
    print("  GET  /api/health")
    print("  GET  /api/topics")
    print("  POST /api/chat (simple RAG)")
    print("  POST /api/agent/chat (agent mode)")
    print("  POST /api/agent/debug")
    print("  GET  /api/agent/tools")
