"""
Agent configuration and tool definitions.
Defines available tools and agent behavior parameters.
"""

AGENT_TOOLS = {
    "rag_search": {
        "name": "Human Rights Document Search",
        "description": "Searches vector database for relevant human rights documents using semantic search",
        "use_when": "User asks factual questions about human rights, needs source-grounded answers, or asks questions covered by local documents.",
        "parameters": ["query", "topic", "top_k"]
    },
    "web_search": {
        "name": "Web Search Tool",
        "description": "Searches the live internet for up-to-date human rights news, external policies, or information not found in local documents.",
        "use_when": "RAG search quality is low, query is about current events, or needs external/general knowledge grounding.",
        "parameters": ["query", "num_results"]
    },
    "fact_verifier": {
        "name": "Fact Verification Tool",
        "description": "Cross-references information across multiple documents to verify claims",
        "use_when": "Information seems contradictory, need to verify specific claims, ensuring accuracy is critical",
        "parameters": ["claim", "topic"]
    },
    "comparative_analyzer": {
        "name": "Document Comparison Tool",
        "description": "Compares and contrasts content across different human rights documents",
        "use_when": "User asks 'How is X different from Y?', comparing provisions across conventions, analyzing evolution",
        "parameters": ["aspect", "topic", "documents"]
    },
    "educational_planner": {
        "name": "Educational Content Generator",
        "description": "Creates lesson plans, quizzes, study guides, and educational materials",
        "use_when": "User requests lesson plans, quizzes, study materials, educational content",
        "parameters": ["content_type", "topic", "level", "details"]
    }
}

# Agent behavior configuration
AGENT_CONFIG = {
    "max_iterations": 5,
    "confidence_threshold": 0.7,
    "temperature": 0.1,  # Low temperature for consistent reasoning
    "model": "gemini-2.0-flash",
    "enable_debug": True,
    "timeout_seconds": 30
}

# Difficulty level descriptions
DIFFICULTY_LEVELS = {
    "beginner": {
        "description": "Simple language, basic concepts, clear examples",
        "target_audience": "High school students or general public"
    },
    "intermediate": {
        "description": "Balanced detail, some legal terminology, contextual examples",
        "target_audience": "Undergraduate students or informed citizens"
    },
    "advanced": {
        "description": "Comprehensive analysis, technical language, legal nuance",
        "target_audience": "Law students, academics, professionals"
    }
}