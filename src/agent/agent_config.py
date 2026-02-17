"""
Agent configuration and tool definitions.
Defines available tools and agent behavior parameters.
"""

AGENT_TOOLS = {
    "rag_search": {
        "name": "HR Knowledge Base Search",
        "description": "Searches vector database for relevant HR policies, benefits, and employment law documents using semantic search",
        "use_when": "User asks factual questions about HR policies, benefits, employment law, or needs source-grounded answers from the knowledge base.",
        "parameters": ["query", "topic", "top_k"],
    },
    "web_search": {
        "name": "Web Search Tool",
        "description": "Searches the live internet for up-to-date employment law, HR news, external policies, or information not found in local documents.",
        "use_when": "RAG search quality is low, query is about current events, or needs external/general knowledge grounding.",
        "parameters": ["query", "num_results"],
    },
    "fact_verifier": {
        "name": "Fact Verification Tool",
        "description": "Cross-references information across multiple documents to verify claims about HR policies and employment law",
        "use_when": "Information seems contradictory, need to verify specific claims, ensuring accuracy is critical",
        "parameters": ["claim", "topic"],
    },
    "comparative_analyzer": {
        "name": "Policy Comparison Tool",
        "description": "Compares and contrasts content across different HR policies, benefits plans, or employment regulations",
        "use_when": "User asks 'How is X different from Y?', comparing benefits plans, analyzing policy differences",
        "parameters": ["aspect", "topic", "documents"],
    },
    "educational_planner": {
        "name": "HR Training Content Generator",
        "description": "Creates training materials, onboarding guides, quizzes, and educational materials for HR topics",
        "use_when": "User requests training plans, compliance quizzes, onboarding materials, educational content",
        "parameters": ["content_type", "topic", "level", "details"],
    },
}

# Agent behavior configuration
AGENT_CONFIG = {
    "max_iterations": 5,
    "confidence_threshold": 0.7,
    "temperature": 0.1,  # Low temperature for consistent reasoning
    "model": "gpt-4o-mini",
    "enable_debug": True,
    "timeout_seconds": 30,
}

# Difficulty level descriptions
DIFFICULTY_LEVELS = {
    "quick": {
        "description": "Brief, concise answers with key facts",
        "target_audience": "Employees with simple questions",
    },
    "detailed": {
        "description": "Balanced detail, policy references, practical examples",
        "target_audience": "Employees needing thorough understanding",
    },
    "expert": {
        "description": "Comprehensive analysis, legal nuance, compliance details",
        "target_audience": "HR professionals, managers, compliance officers",
    },
}
