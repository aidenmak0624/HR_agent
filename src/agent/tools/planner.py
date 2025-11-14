"""Educational Planner Tool - Creates lesson plans, quizzes, and study materials"""

from typing import Dict, Any
import sys
from pathlib import Path
import logging
import os
import json

# Ensure necessary paths are in system path for imports to work
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from src.core.rag_system import SimpleRAG
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class EducationalPlannerTool:
    """Creates educational materials like lesson plans, quizzes, and study guides."""
    
    name = "educational_planner"
    description = """Create educational materials (lesson plans, quizzes, study guides) 
    for teaching human rights topics at different educational levels."""
    
    def __init__(self):
        logger.info("Initializing Educational Planner Tool...")
        # Check for API Key presence for better error tracing
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.error("GOOGLE_API_KEY environment variable is missing for Educational Planner.")
            
        self.rag = SimpleRAG(preload_topics=True)
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key, # Uses the environment variable
            temperature=0.7
        )
        logger.info("✅ Educational Planner ready")
    
    def run(self, content_type: str, topic: str, level: str = "high_school", 
            details: dict = None) -> Dict[str, Any]:
        """Generate educational content."""
        
        if details is None:
            details = {}
        
        # Gather content (robust RAG retrieval)
        topic_info = self._gather_topic_info(topic)
        
        if content_type == "lesson_plan":
            return self._generate_lesson_plan(topic, level, topic_info, details)
        elif content_type == "quiz":
            return self._generate_quiz(topic, level, topic_info, details)
        elif content_type == "study_guide":
            return self._generate_study_guide(topic, level, topic_info, details)
        else:
            return {"error": f"Unknown content type: {content_type}"}
    
    def _gather_topic_info(self, topic: str) -> dict:
        """Gather information from RAG (FIXED: correct data extraction)."""
        try:
            results = self.rag.retrieve(
                query=f"Educational content about {topic}", 
                topic=topic, 
                n_results=5
            )
            
            # Handle both dict and list returns from RAG
            if isinstance(results, dict):
                documents = results.get('documents', [])
                metadatas = results.get('metadatas', [])
            elif isinstance(results, list):
                # If results is a list, it's probably the documents directly
                documents = results
                metadatas = [{}] * len(results)  # Empty metadata for each doc
            else:
                documents = []
                metadatas = []
            
            # Extract source from each metadata dictionary
            sources = [m.get('source', 'unknown') for m in metadatas]
            
            return {
                "documents": documents,
                "sources": sources
            }
        except Exception as e:
            logger.error(f"RAG retrieval failed for topic '{topic}' in EducationalPlanner: {e}")
            return {"documents": [], "sources": []}
    
    def _generate_lesson_plan(self, topic: str, level: str, 
                              topic_info: dict, details: dict) -> Dict[str, Any]:
        """Generate a lesson plan."""
        duration = details.get("duration", "45 minutes")
        # Ensure only the top 3 documents are joined to form context
        context = "\n\n".join(topic_info['documents'][:3])
        
        prompt = f"""Create a {duration} lesson plan on "{topic}" for {level} students.

Background Context from Documents: {context}

Include: Learning Objectives, Materials, Introduction, Main Activity, Discussion, Assessment

**LESSON PLAN:**"""
        
        try:
            messages = [SystemMessage(content="You are an expert educator, specializing in human rights curriculum design. Generate the lesson plan in clear markdown format."),
                       HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            
            return {
                "content": response.content,
                "format": "markdown",
                "sources": topic_info['sources'],
                "content_type": "lesson_plan"
            }
        except Exception as e:
            logger.error(f"LLM generation failed for Lesson Plan (Topic: {topic}): {e}")
            return {"error": str(e), "content": "", "format": "text"}
    
    def _generate_quiz(self, topic: str, level: str, 
                       topic_info: dict, details: dict) -> Dict[str, Any]:
        """Generate quiz questions."""
        num_questions = details.get("num_questions", 10)
        context = "\n\n".join(topic_info['documents'][:3])
        
        prompt = f"""Create a {num_questions}-question quiz on "{topic}" for {level} students.
Use the background context provided below.

Background Context: {context}

Return ONLY JSON array of question objects, where each object has 'question', 'options' (list of strings), 'answer' (string matching an option), and 'explanation'."""
        
        try:
            messages = [SystemMessage(content="You are a quiz creator who returns valid, clean JSON."),
                       HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            
            try:
                # Attempt to parse the response as JSON
                quiz_data = json.loads(response.content)
                return {"content": quiz_data, "format": "json", 
                       "sources": topic_info['sources']}
            except json.JSONDecodeError:
                logger.warning("Quiz generation failed to return clean JSON. Returning as Markdown.")
                return {"content": response.content, "format": "markdown",
                       "sources": topic_info['sources']}
        except Exception as e:
            logger.error(f"LLM generation failed for Quiz (Topic: {topic}): {e}")
            return {"error": str(e), "content": "", "format": "text"}
    
    def _generate_study_guide(self, topic: str, level: str, 
                             topic_info: dict, details: dict) -> Dict[str, Any]:
        """Generate a study guide."""
        context = "\n\n".join(topic_info['documents'][:3])
        
        prompt = f"""Create a comprehensive study guide on "{topic}" for {level} students.
Use the background context provided below.

Background Context: {context}

Include: Key Concepts, Definitions, Study Questions, Resources (links are optional if not in context)"""
        
        try:
            messages = [SystemMessage(content="You are an expert educator who generates helpful study guides in clear markdown."),
                       HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            
            return {
                "content": response.content,
                "format": "markdown",
                "sources": topic_info['sources'],
                "content_type": "study_guide"
            }
        except Exception as e:
            logger.error(f"LLM generation failed for Study Guide (Topic: {topic}): {e}")
            return {"error": str(e), "content": "", "format": "text"}
        
        
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("Testing planner...")
    planner = EducationalPlannerTool()
    
    result = planner.run(
        content_type="lesson_plan",
        topic="foundational_rights",
        level="high_school"
    )
    
    if 'error' in result:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"✅ Success! Generated {len(result.get('content', ''))} chars")