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


class HRKnowledgeBase:
    """HR Knowledge Base RAG system for TechNova Inc."""

    def __init__(
        self,
        persist_directory: str = "./chromadb",
        topics_dir: str = "data/knowledge_base",
        policies_dir: str = "data/policies",
        preload_topics: bool = True,
    ):
        print("🔧 Initializing HR Knowledge Base...")

        # --- 0) Env & Keys ---
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY not set. Put it in your .env and NEVER hardcode keys in code."
            )
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
                settings=Settings(anonymized_telemetry=False, allow_reset=True),  # Important!
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
        self.policies_dir = Path(policies_dir)
        self.topics: List[str] = self._discover_topics()
        print(f"✅ Discovered topics: {self.topics}")
        print("✅ Knowledge base initialized")

        if preload_topics:
            self.load_all_topics()
            self.load_policies()

    # ---------- Utilities ----------
    def _discover_topics(self) -> List[str]:
        if not self.topics_dir.exists():
            return []
        return [p.name for p in self.topics_dir.iterdir() if p.is_dir()]

    def _get_or_create_collection(self, name: str):
        if name in self.collections:
            return self.collections[name]
        col = self.chroma_client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine", "description": f"Documents for {name}"}
        )
        self.collections[name] = col
        return col

    # ---------- Ingestion ----------

    def load_documents_for_topic(self, topic_name: str, min_chunk_len: int = 50):
        """Load documents under data/knowledge_base/{topic_name}/*.txt into Chroma"""
        topic_dir = self.topics_dir / topic_name
        print(f"📚 Loading documents for '{topic_name}' from {topic_dir} ...")

        if not topic_dir.exists():
            print(f"⚠️  No documents found for {topic_name} (dir not found)")
            return

        collection = self._get_or_create_collection(topic_name)

        doc_count, chunk_count = 0, 0
        for txt_file in topic_dir.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8", errors="ignore")
            chunks = [
                p.strip()
                for p in content.split("\n\n")
                if p.strip() and len(p.strip()) > min_chunk_len
            ]
            if not chunks:
                continue

            # vectorize in batch
            embeddings = self.embedding_model.encode(
                chunks, batch_size=32, convert_to_numpy=True
            ).tolist()

            # stable IDs (content hash) to make ingestion idempotent
            import hashlib

            def _cid(stem, i, text):
                h = hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()
                return f"{stem}_c{i}_{h}"

            ids = [_cid(txt_file.stem, i, ch) for i, ch in enumerate(chunks)]
            metadatas = [
                {"source": txt_file.name, "topic": topic_name, "chunk_id": i}
                for i in range(len(chunks))
            ]

            # requires chromadb 0.5.x
            collection.upsert(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
            doc_count += 1
            chunk_count += len(chunks)

        print(f"✅ Loaded {doc_count} docs ({chunk_count} chunks) -> collection '{topic_name}'")

    def load_all_topics(self):
        """Load all topic folders from data/knowledge_base"""
        if not self.topics:
            print("⚠️  No topic folders found under data/knowledge_base")
            return
        print(f"📚 Loading all topics: {self.topics}")
        for topic in self.topics:
            self.load_documents_for_topic(topic)
        print("✅ All topics loaded")

    def load_policies(self, min_chunk_len: int = 50):
        """Load company policies from data/policies/*.txt into 'policies' collection"""
        print(f"📚 Loading company policies from {self.policies_dir} ...")

        if not self.policies_dir.exists():
            print(f"⚠️  No policies directory found at {self.policies_dir}")
            return

        collection = self._get_or_create_collection("policies")

        doc_count, chunk_count = 0, 0
        for txt_file in self.policies_dir.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8", errors="ignore")
            chunks = [
                p.strip()
                for p in content.split("\n\n")
                if p.strip() and len(p.strip()) > min_chunk_len
            ]
            if not chunks:
                continue

            # vectorize in batch
            embeddings = self.embedding_model.encode(
                chunks, batch_size=32, convert_to_numpy=True
            ).tolist()

            # stable IDs (content hash) to make ingestion idempotent
            import hashlib

            def _cid(stem, i, text):
                h = hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()
                return f"{stem}_c{i}_{h}"

            ids = [_cid(txt_file.stem, i, ch) for i, ch in enumerate(chunks)]
            metadatas = [
                {"source": txt_file.name, "topic": "policies", "chunk_id": i}
                for i in range(len(chunks))
            ]

            collection.upsert(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
            doc_count += 1
            chunk_count += len(chunks)

        print(f"✅ Loaded {doc_count} policy docs ({chunk_count} chunks) -> collection 'policies'")

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
            include=["documents", "metadatas", "distances"],  # <-- add scores
        )

    # ---------- Generation ----------
    def _preprocess_context(self, docs: List[str], query: str) -> str:
        # """Preprocess retrieved documents for better context"""

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
        answer = "\n\n".join(line.strip() for line in answer.split("\n") if line.strip())

        return answer.strip()

    def generate_answer(self, query: str, topic: str, difficulty: str = "intermediate") -> str:
        # """Generate answer with context retrieval and difficulty adaptation"""

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
        dists = results.get("distances", [[None] * len(docs)])[0]

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
        """Build prompt with difficulty-level adaptation for HR context"""

        # Difficulty-specific instructions (quick, detailed, expert)
        difficulty_instructions = {
            "quick": """
    - Provide a brief, direct answer
    - Use simple language and avoid jargon when possible
    - Focus on the most critical information
    - Include one practical example if relevant
    - Keep explanation concise and actionable
    - Ideal for quick reference or time-constrained employees""",
            "detailed": """
    - Balance clarity with technical accuracy
    - Use HR and legal terminology when appropriate, with explanations
    - Provide structured explanations with multiple examples
    - Cover relevant scenarios and edge cases
    - Connect concepts to TechNova Inc. context when applicable
    - Ideal for thorough understanding of policies""",
            "expert": """
    - Use precise HR, employment law, and compliance terminology
    - Reference specific regulations (FMLA, ADA, FLSA, etc.)
    - Provide comprehensive analysis with nuanced interpretations
    - Include compliance considerations and legal frameworks
    - Address edge cases and special circumstances
    - Ideal for HR professionals and managers making decisions""",
        }

        instructions = difficulty_instructions.get(difficulty, difficulty_instructions["detailed"])

        # Get few-shot examples
        examples = self._get_example_qas(difficulty)

        # Build the prompt with examples
        prompt = f"""You are a knowledgeable HR assistant for TechNova Inc. specializing in employment law, benefits, and company policies.

    **Example Responses at {difficulty.title()} Level:**
    {examples}

    **Now answer this question following the same style and depth:**

    **Context from HR Knowledge Base:**
    {context}

    **Employee/Manager Question:**
    {query}

    **Topic Area:** {topic.replace('_', ' ').title()}

    **Instructions for {difficulty.title()}-Level Response:**
    {instructions}

    **Response Structure:**
    1. Direct Answer: Start with a clear, direct response to the question
    2. Explanation: Provide details grounded in the provided context and TechNova Inc. policies
    3. Key Takeaways: Highlight 2-3 essential points for the employee/manager
    4. Application: Connect to practical workplace scenarios when relevant

    **Critical Guidelines:**
    - Base your answer ONLY on the provided context
    - If the context doesn't contain enough information, acknowledge limitations
    - Cite specific policies, regulations, or sections when making claims
    - Maintain a professional, supportive tone
    - Provide actionable guidance when appropriate
    - For legal matters, include appropriate disclaimers about consulting HR or legal counsel

    **Response Length Guidelines:**
    - Quick: 100-200 words
    - Detailed: 250-400 words
    - Expert: 400-600 words (comprehensive but focused)

    **Response Format:**
    - Use clear paragraphs
    - Bold key concepts and policy names (use **bold**)
    - Use numbered lists for steps, requirements, or multiple points
    - Use bullet points for benefits or features

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
    4. Contact TechNova Inc. HR Department for additional assistance

    **Available HR Knowledge Base Topics:**
    - Employment Law (FMLA, ADA, anti-discrimination, FLSA, COBRA/WARN)
    - Benefits (health insurance, 401k, leave benefits)
    - Company Policies (code of conduct, performance management)
    - Payroll Compliance (payroll processing, taxes, workers compensation)
    - Employee Handbook (onboarding, workplace safety)
    - Company Policies (remote work, PTO, and more)

    I'm here to help with questions about TechNova Inc. HR policies, benefits, and employment compliance."""

    def _get_example_qas(self, difficulty: str) -> str:
        """Provide example Q&As for few-shot learning in HR context"""

        examples = {
            "quick": """
    **Example 1:**
    Q: How much PTO do new employees get?
    A: New employees at TechNova Inc. receive 15 days of paid time off annually. This includes vacation days, personal days, and sick leave combined. PTO accrues monthly and unused days can be carried over with manager approval.

    **Example 2:**
    Q: Is the 401k match available immediately?
    A: The 401k match becomes available after a 6-month employment period. TechNova Inc. matches 100% of contributions up to 3% of your salary. Contributions before the match date are still allowed.""",
            "detailed": """
    **Example:**
    Q: What does FMLA protect and who is eligible?
    A: The Family and Medical Leave Act (FMLA) protects eligible employees' right to take unpaid, job-protected leave for specific family and medical reasons.

    **Eligibility Requirements:**
    - Work for a covered employer (50+ employees)
    - Employed for at least 12 months
    - Worked at least 1,250 hours in the past 12 months
    - Work at a location with 50+ employees within 75 miles

    **Covered Reasons:**
    - Birth or adoption of a child
    - Care for spouse, child, or parent with serious health condition
    - Employee's own serious health condition
    - Military family leave

    **TechNova Inc. Application:** Employees meeting these criteria can take up to 12 weeks unpaid leave in a 12-month period while maintaining health insurance and job protection.""",
            "expert": """
    **Example:**
    Q: How do ADA reasonable accommodations interact with attendance policies under FMLA?
    A: The Americans with Disabilities Act (ADA) and Family and Medical Leave Act (FMLA) create overlapping but distinct protections requiring careful integration in HR policy.

    **Legal Framework:**
    - **FMLA**: Provides 12 weeks unprotected leave for serious health conditions; job protection is absolute within the statutory entitlement
    - **ADA**: Requires reasonable accommodations for known disabilities; accommodations may include modified schedules, leave, or flexibility
    - **Interaction**: FMLA leave counts toward the 12-week entitlement, but ADA accommodations (like flexible hours) may prevent FMLA designation

    **Compliance Considerations:**
    1. Assess whether absences qualify as ADA accommodations before designating FMLA
    2. Use the most favorable standard for the employee (ADA may provide additional protections)
    3. Document individualized assessment for each employee's disability-related needs
    4. Track ADA accommodations separately from FMLA usage to maintain legal compliance
    5. Ensure consistent application across similar cases to avoid discrimination claims

    **TechNova Inc. Protocol:** HR must coordinate between FMLA and ADA determinations, ensuring employees receive maximum statutory protection while maintaining defensible documentation.""",
        }

        return examples.get(difficulty, examples["detailed"])


# ---------- Quick test ----------


def test_rag():
    print("=" * 60)
    print("🏢 Testing TechNova Inc. HR Knowledge Base")
    print("=" * 60)

    rag = HRKnowledgeBase()
    rag.load_documents_for_topic("benefits")

    query = "What is the 401k match?"
    answer = rag.generate_answer(query, "benefits", difficulty="detailed")

    print("\n" + "=" * 60)
    print("ANSWER:")
    print("=" * 60)
    print(answer)
    print("=" * 60)


if __name__ == "__main__":
    test_rag()
