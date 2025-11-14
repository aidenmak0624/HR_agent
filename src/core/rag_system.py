# --- put telemetry env flags BEFORE importing chromadb ---
import os
import logging

# Suppress chromadb telemetry errors early
os.environ["CHROMADB_ANONYMIZED_TELEMETRY"] = "false"
os.environ["CHROMADB_TELEMETRY_IMPL"] = "none"
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

# src/core/rag_system.py
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from chromadb import PersistentClient
from chromadb.config import Settings
import google.generativeai as genai


class SimpleRAG:
    """Basic RAG system for human rights education"""

    def __init__(self, persist_directory: str = "./chromadb", topics_dir: str = "data/processed",preload_topics: bool = True):
        print("🔧 Initializing RAG system...")

        # --- 0) Env & Keys ---
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set. Put it in your .env and NEVER hardcode keys in code.")
        genai.configure(api_key=api_key)

        # --- 1) LLM ---
        self.model = genai.GenerativeModel(model_name="gemini-2.0-flash")
        print("✅ Gemini model ready")

        # --- 2) Embeddings ---
        self.embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        print("✅ Embedding model loaded")

        # --- 3) Vector DB (Chroma) ---
        persist_path = Path(persist_directory)
        persist_path.mkdir(parents=True, exist_ok=True)
        
        try:
            self.chroma_client = PersistentClient(
                path=str(persist_path),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True  # Important!
                )
            )
            # Test connection
            self.chroma_client.heartbeat()
            print(f"✅ ChromaDB connected at {persist_path.resolve()}")
        except Exception as e:
            print(f"❌ ChromaDB connection failed: {e}")
            raise RuntimeError(f"Failed to initialize ChromaDB: {e}")
    
        print(f"✅ ChromaDB ready at {persist_path.resolve()}")

        # --- 4) State (init ONCE) ---
        self.collections: Dict[str, any] = {}
        self.topics_dir = Path(topics_dir)
        self.topics: List[str] = self._discover_topics()
        print(f"✅ Discovered topics: {self.topics}")
        print("✅ Default collection ready")
        
        if preload_topics:
            self.load_all_topics()

    # ---------- Utilities ----------
    def _discover_topics(self) -> List[str]:
        if not self.topics_dir.exists():
            return []
        return [p.name for p in self.topics_dir.iterdir() if p.is_dir()]

    def _get_or_create_collection(self, name: str):
        if name in self.collections:
            return self.collections[name]
        col = self.chroma_client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine", "description": f"Documents for {name}"}
        )
        self.collections[name] = col
        return col
    # ---------- Ingestion ----------

    def load_documents_for_topic(self, topic_name: str, min_chunk_len: int = 50):
        """Load documents under data/processed/{topic_name}/*.txt into Chroma"""
        topic_dir = self.topics_dir / topic_name
        print(f"📚 Loading documents for '{topic_name}' from {topic_dir} ...")

        if not topic_dir.exists():
            print(f"⚠️  No documents found for {topic_name} (dir not found)")
            return

        collection = self._get_or_create_collection(topic_name)


        doc_count, chunk_count = 0, 0
        for txt_file in topic_dir.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8", errors="ignore")
            chunks = [p.strip() for p in content.split("\n\n") if p.strip() and len(p.strip()) > min_chunk_len]
            if not chunks:
                continue

            # vectorize in batch
            embeddings = self.embedding_model.encode(chunks, batch_size=32, convert_to_numpy=True).tolist()

            # stable IDs (content hash) to make ingestion idempotent
            import hashlib
            def _cid(stem, i, text):
                h = hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()
                return f"{stem}_c{i}_{h}"

            ids = [_cid(txt_file.stem, i, ch) for i, ch in enumerate(chunks)]
            metadatas = [{"source": txt_file.name, "topic": topic_name, "chunk_id": i} for i in range(len(chunks))]

            # requires chromadb 0.5.x
            collection.upsert(
                documents=chunks,
                embeddings=embeddings,
                ids=ids,
                metadatas=metadatas
            )
            doc_count += 1
            chunk_count += len(chunks)

        print(f"✅ Loaded {doc_count} docs ({chunk_count} chunks) -> collection '{topic_name}'")

    def load_all_topics(self):
        if not self.topics:
            print("⚠️  No topic folders found under data/processed")
            return
        print(f"📚 Loading all topics: {self.topics}")
        for topic in self.topics:
            self.load_documents_for_topic(topic)
        print("✅ All topics loaded")

    # ---------- Retrieval ----------
    def retrieve(self, query: str, topic: str, n_results: int = 6):
        # lazy-load if needed
        if topic not in self.collections:
            self.load_documents_for_topic(topic)
        if topic not in self.collections:
            print(f"⚠️  Topic '{topic}' still not available.")
            return None

        query_emb = self.embedding_model.encode(query, convert_to_numpy=True).tolist()
        return self.collections[topic].query(
            query_embeddings=[query_emb],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]  # <-- add scores
        )

    # ---------- Generation ----------
    def _preprocess_context(self, docs: List[str], query: str) -> str:
    #"""Preprocess retrieved documents for better context"""
    
    # Remove very short chunks (likely noise)
        meaningful_docs = [d for d in docs if len(d.strip()) > 50]
        
        if not meaningful_docs:
            return "\n\n".join(docs)
        
        # Deduplicate similar chunks
        unique_docs = []
        seen_content = set()
        
        for doc in meaningful_docs:
            # Simple dedup based on first 100 chars
            signature = doc[:100].lower().strip()
            if signature not in seen_content:
                unique_docs.append(doc)
                seen_content.add(signature)
        
        # Join with clear separators
        context = "\n\n---\n\n".join(unique_docs)
        
        # Truncate if too long (Gemini has limits)
        max_context_chars = 4000
        if len(context) > max_context_chars:
            context = context[:max_context_chars] + "\n\n[Context truncated for length]"
    
        return context
    
    def _postprocess_answer(self, answer: str) -> str:
        # """Clean and format the AI response"""
        
        # Remove common AI disclaimers that aren't needed
        unwanted_phrases = [
            "As a helpful assistant,",
            "I'm here to help,",
            "Let me help you understand,",
            "Based on my training,",
        ]
        
        for phrase in unwanted_phrases:
            answer = answer.replace(phrase, "")
        
        # Ensure proper spacing after periods
        answer = answer.replace(". ", ".  ")
        
        # Format bold text (if Gemini uses ** for bold)
        # Frontend will handle **text** as bold
        
        # Trim excess whitespace
        answer = "\n\n".join(
            line.strip() for line in answer.split("\n") if line.strip()
        )
        
        return answer.strip()
    
    def generate_answer(self, query: str, topic: str, difficulty: str = "intermediate") -> str:
        #"""Generate answer with context retrieval and difficulty adaptation"""
        
        print(f"\n❓ Question: {query}\n📂 Topic: {topic}\n📊 Difficulty: {difficulty}")
        
        # Initialize answer variable FIRST
        answer = ""
        
        # Retrieve context
        results = self.retrieve(query, topic, n_results=4)
        if not results or not results.get("documents") or not results["documents"][0]:
            return self._generate_no_context_response(query, topic)
        
        # Process retrieved documents
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results.get("distances", [[None]*len(docs)])[0]
        
        # Rank by relevance
        rank = sorted(range(len(docs)), key=lambda i: dists[i] if dists[i] is not None else 1e9)[:3]
        raw_docs = [docs[i] for i in rank]
        context = self._preprocess_context(raw_docs, query)
        sources = [f"{metas[i].get('source','?')} (score={dists[i]:.3f})" for i in rank]
        
        # Build enhanced prompt
        prompt = self._build_enhanced_prompt(query, context, topic, difficulty)
        
        # Generate with error handling
        try:
            resp = self.model.generate_content(prompt)
            # Get the text FIRST
            answer = (getattr(resp, "text", "") or "").strip()
            # THEN postprocess it
            answer = self._postprocess_answer(answer)
            
            if not answer:
                answer = "I apologize, but I couldn't generate a response. Please try rephrasing your question."
                
        except Exception as e:
            print(f"⚠️ Generation error: {e}")
            answer = "I encountered an error while processing your question. Please try again."
        
        # Add citations
        citation = "\n\n📚 Sources: " + ", ".join(sorted(set(sources)))
        return answer + citation


    def _build_enhanced_prompt(self, query: str, context: str, topic: str, difficulty: str) -> str:
        """Build prompt with difficulty-level adaptation"""
        
        # Difficulty-specific instructions
        difficulty_instructions = {
            "beginner": """
    - Use simple, everyday language
    - Avoid legal jargon unless you explain it
    - Provide concrete examples (e.g., "Like the right to go to school")
    - Use analogies ("Think of it like...")
    - Keep explanations brief and clear
    - Focus on practical understanding
    - Start with simplest explanation first""",
            
            "intermediate": """
    - Balance technical accuracy with accessibility
    - Use legal terminology when appropriate, with context
    - Provide structured explanations with examples
    - Include relevant details without overwhelming
    - Connect concepts to real-world applications""",
            
            "advanced": """
    - Use precise legal and academic terminology
    - Reference specific articles and frameworks
    - Provide comprehensive analysis
    - Include nuanced interpretations
    - Connect to broader human rights discourse"""
        }
        
        instructions = difficulty_instructions.get(difficulty, difficulty_instructions["intermediate"])
        
        # Get few-shot examples
        examples = self._get_example_qas(difficulty)
        
        # Build the prompt with examples
        prompt = f"""You are an expert human rights educator specializing in international law and human rights frameworks.

    **Example Responses at {difficulty.title()} Level:**
    {examples}

    **Now answer this question following the same style and depth:**

    **Context from Authoritative Documents:**
    {context}

    **Student Question:**
    {query}

    **Topic Context:** {topic.replace('_', ' ').title()}

    **Instructions for {difficulty.title()}-Level Response:**
    {instructions}

    **Response Structure:**
    1. Direct Answer: Start with a clear, direct response to the question
    2. Explanation: Provide detailed explanation grounded in the provided context
    3. Key Points: Highlight 2-3 essential takeaways
    4. Context: Connect to broader human rights frameworks when relevant

    **Critical Guidelines:**
    - Base your answer ONLY on the provided context
    - If the context doesn't contain enough information, acknowledge limitations
    - Cite specific documents or articles when making claims
    - Maintain educational tone - explain, don't just state
    - Use examples to illustrate abstract concepts

    **Response Length Guidelines:**
    - Beginner: 150-250 words
    - Intermediate: 250-400 words  
    - Advanced: 400-600 words (comprehensive but focused)

    **Response Format:**
    - Use clear paragraphs
    - Bold key concepts (use **bold**)
    - Use numbered lists for steps or multiple points

    **Now provide your response:**"""
        
        return prompt


    def _generate_no_context_response(self, query: str, topic: str) -> str:
        """Handle cases where no relevant context is found"""
        return f"""I couldn't find specific information about "{query}" in the {topic.replace('_', ' ')} documents currently available.

    This could mean:
    - The question is outside the scope of loaded documents
    - The question needs to be rephrased for better matching
    - The topic category might not be the best fit

    **Suggestions:**
    1. Try rephrasing your question with different keywords
    2. Check if another topic category might be more relevant
    3. Ask a more specific question about a particular aspect

    I'm here to help with questions about human rights based on authoritative UN documents and international frameworks."""


    def _get_example_qas(self, difficulty: str) -> str:
        """Provide example Q&As for few-shot learning"""
        
        examples = {
            "beginner": """
    **Example 1:**
    Q: What are human rights?
    A: Human rights are basic rights and freedoms that belong to every person in the world, from birth until death. They include things like the right to life, freedom from torture, freedom of speech, and the right to education. Think of them as the fundamental things everyone deserves, no matter who they are or where they live.

    **Key Points:**
    - Universal (for everyone)
    - Protect human dignity
    - Can't be taken away

    **Example 2:**
    Q: Why are human rights important?
    A: Human rights are important because they protect people from harm and ensure everyone is treated fairly. For example, the right to education means all children can go to school. The right to freedom of speech means you can express your opinions. These rights help create a society where everyone can live safely and pursue their goals.""",
            
            "intermediate": """
    **Example:**
    Q: What is the relationship between civil-political rights and economic-social-cultural rights?
    A: Civil and political rights (like freedom of speech and voting rights) and economic, social, and cultural rights (like the right to education and adequate housing) are interdependent and mutually reinforcing.

    **The Connection:**
    The 1993 Vienna Declaration emphasizes that all human rights are "universal, indivisible and interdependent and interrelated." This means:
    - You need freedom of expression (civil right) to advocate for better working conditions (economic right)
    - Access to education (social right) enables political participation (political right)
    - Economic security supports the exercise of cultural rights

    **Key Framework:**
    Both sets of rights are protected under international law through the ICCPR (civil-political) and ICESCR (economic-social-cultural) covenants, which together with the UDHR form the International Bill of Human Rights.""",
            
            "advanced": """
    **Example:**
    Q: How does Article 29 of the UDHR establish the framework for limitations on rights?
    A: Article 29 of the Universal Declaration of Human Rights establishes the foundational principles for permissible limitations on rights and freedoms, creating a delicate balance between individual liberties and communal responsibilities.

    **Legal Framework:**
    Article 29 articulates three critical dimensions:

    1. **Duties to Community** (Article 29.1): Establishes that rights exist within a social context where "everyone has duties to the community in which alone the free and full development of his personality is possible." This reflects the principle that rights and responsibilities are correlative.

    2. **Permissible Limitations** (Article 29.2): Limitations must be "determined by law" and serve legitimate aims: "due recognition and respect for the rights and freedoms of others" and "just requirements of morality, public order and the general welfare in a democratic society."

    3. **Adherence to UN Principles** (Article 29.3): Rights cannot be exercised "contrary to the purposes and principles of the United Nations," ensuring alignment with international peace, security, and human dignity.

    **Interpretive Significance:**
    This tripartite structure provides the doctrinal foundation for proportionality analysis in human rights adjudication, requiring that any restriction be: (1) prescribed by law, (2) pursue a legitimate aim, and (3) be necessary and proportionate in a democratic society."""
        }
        
        return examples.get(difficulty, examples["intermediate"])
# ---------- Quick test ----------

def test_rag():
    print("=" * 60)
    print("🌍 Testing Human Rights RAG System")
    print("=" * 60)

    rag = SimpleRAG()
    rag.load_documents_for_topic("foundational_rights")

    query = "What are human rights?"
    answer = rag.generate_answer(query, "foundational_rights")

    print("\n" + "=" * 60)
    print("ANSWER:")
    print("=" * 60)
    print(answer)
    print("=" * 60)


if __name__ == "__main__":
    test_rag()

