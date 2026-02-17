"""
Router Agent (CORE-001) for HR multi-agent platform.

The RouterAgent is the supervisor that:
1. Classifies user intents
2. Checks permissions via RBAC
3. Dispatches to appropriate specialist agents
4. Merges responses from multiple agents if needed
"""

from typing import Any, Dict, List, Optional, TypedDict
import logging
import json

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import func as sa_func

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class RouterState(TypedDict, total=False):
    """
    State for routing decisions and multi-agent orchestration.
    
    Tracks:
    - Input: query, user_context
    - Classification: intent, confidence, target_agents
    - Execution: agent_results
    - Output: final_response
    """
    
    # Input
    query: str
    user_context: Dict[str, Any]
    conversation_history: List[Dict[str, str]]
    
    # Classification
    intent: str
    confidence: float
    target_agents: List[str]
    requires_clarification: bool
    clarification_question: Optional[str]
    
    # Execution
    agent_results: List[Dict[str, Any]]
    
    # Output
    final_response: Dict[str, Any]


class RouterAgent:
    """
    Supervisor agent that orchestrates specialist agents.
    
    NOT extending BaseAgent - this is a coordinator, not a specialist.
    
    Responsibilities:
    1. Intent classification (query -> intent category)
    2. Permission checking (user_context + intent -> allowed?)
    3. Agent dispatch (intent -> specialist agent)
    4. Response merging (multi-agent results -> unified response)
    
    Intent Categories:
    - employee_info: Employee directory, profiles, compensation
    - policy: HR policies, compliance, procedures
    - leave: Time off, PTO, sick leave management
    - onboarding: New hire process, documentation
    - benefits: Health insurance, retirement, perks
    - performance: Reviews, goals, feedback
    - analytics: Reports, dashboards, trends
    - unclear: Ambiguous queries requiring clarification
    - multi_intent: Query spans multiple categories
    """
    
    # Intent categories with examples
    INTENT_CATEGORIES = {
        "employee_info": ["who is", "employee profile", "contact", "department", "report to"],
        "policy": ["policy", "procedure", "compliance", "guideline", "rule"],
        "leave": ["leave balance", "time off balance", "remaining pto", "how many days",
                  "sick leave", "vacation", "time off", "annual leave", "maternity leave",
                  "paternity leave", "bereavement leave", "leave request", "pto"],
        "leave_request": ["request leave", "submit leave", "take time off", "book vacation", "request pto", "apply for leave"],
        "onboarding": ["onboarding", "new hire", "orientation", "induction", "welcome"],
        "benefits": ["benefits", "health", "insurance", "retirement", "401k", "pto"],
        "performance": ["performance", "review", "goal", "feedback", "evaluation"],
        "analytics": ["report", "analytics", "statistics", "trend", "dashboard", "headcount"],
        "compliance": ["gdpr", "dsar", "data subject", "data request", "erasure", "right to be forgotten",
                       "data portability", "pii", "personal data", "privacy", "data protection",
                       "ccpa", "consent", "data breach"],
    }

    # Agent registry: intent -> agent class name
    AGENT_REGISTRY = {
        "employee_info": "EmployeeInfoAgent",
        "policy": "PolicyAgent",
        "leave": "LeaveAgent",
        "leave_request": "LeaveRequestAgent",
        "onboarding": "OnboardingAgent",
        "benefits": "BenefitsAgent",
        "performance": "PerformanceAgent",
        "analytics": "PerformanceAgent",  # Analytics handled by performance agent (no standalone analytics agent)
        "compliance": "ComplianceAgent",
    }
    
    def __init__(self, llm: Any):
        """
        Initialize router agent.
        
        Args:
            llm: Language model instance (e.g., ChatGoogleGenerativeAI)
        """
        self.llm = llm
        self.agent_cache = {}  # Cache instantiated agents
    
    # ==================== Intent Classification ====================
    
    def classify_intent(self, query: str) -> tuple[str, float]:
        """
        Classify user query intent using fast LLM classification.
        
        Fast implementation: checks keywords first, then uses LLM if ambiguous.
        
        Args:
            query: User query/question
            
        Returns:
            Tuple of (intent, confidence) where intent is one of INTENT_CATEGORIES,
            confidence is 0.0-1.0
        """
        logger.info(f"CLASSIFY: Analyzing query: {query[:60]}...")
        
        query_lower = query.lower()

        # Quick keyword matching — longer keyword phrases get bonus weight
        # so "sick leave" (10 chars) beats "policy" (6 chars) for specificity
        intent_scores = {}
        for intent, keywords in self.INTENT_CATEGORIES.items():
            score = 0
            for kw in keywords:
                if kw in query_lower:
                    # Longer keyword = more specific match = higher score
                    score += 1 + len(kw) / 20.0
            if score > 0:
                intent_scores[intent] = score

        # If keyword match found, use it
        if intent_scores:
            sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
            max_intent, max_score = sorted_intents[0]
            second_best = sorted_intents[1][1] if len(sorted_intents) > 1 else 0

            # High confidence: clear dominant keyword(s)
            if max_score >= 2 or (max_score == 1 and len(intent_scores) == 1):
                logger.info(f"CLASSIFY: Keyword match → {max_intent} (confidence=0.9)")
                return (max_intent, 0.9)

            # Medium confidence: top intent beats second-best
            if max_score > second_best:
                logger.info(f"CLASSIFY: Keyword match → {max_intent} (confidence=0.8)")
                return (max_intent, 0.8)

            # Tied intents: still route to first match with moderate confidence
            if max_score >= 1:
                logger.info(f"CLASSIFY: Keyword tie-break → {max_intent} (confidence=0.7)")
                return (max_intent, 0.7)
        
        # Use LLM for ambiguous/complex queries
        logger.info("CLASSIFY: Ambiguous query, using LLM")
        classification_prompt = f"""Classify the HR query intent.

QUERY: {query}

Intent options:
- employee_info: Information about employees, profiles, compensation
- policy: HR policies, compliance, procedures
- leave: Time off, vacation, sick leave
- onboarding: New hire process, orientation
- benefits: Health insurance, retirement, perks
- performance: Reviews, goals, feedback
- analytics: Reports, statistics, trends
- multi_intent: Query spans multiple categories

Return JSON:
{{
  "intent": "intent_name",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}"""
        
        messages = [
            SystemMessage(content="You are an HR query classification expert."),
            HumanMessage(content=classification_prompt),
        ]
        
        try:
            response = self.llm.invoke(messages)
            raw = getattr(response, "content", str(response))
            data = self._parse_json_response(raw)
            
            intent = data.get("intent", "unclear")
            confidence = float(data.get("confidence", 0.5))
            
            # Validate intent
            if intent not in self.INTENT_CATEGORIES and intent != "unclear":
                logger.warning(f"CLASSIFY: Invalid intent '{intent}', using 'unclear'")
                intent = "unclear"
            
            logger.info(f"CLASSIFY: LLM → {intent} (confidence={confidence})")
            return (intent, confidence)
            
        except Exception as e:
            logger.error(f"CLASSIFY: LLM failed: {e}")
            return ("unclear", 0.3)
    
    # ==================== Permission Checking ====================
    
    def check_permissions(self, user_context: Dict[str, Any], intent: str) -> bool:
        """
        Check if user has permission for intent using RBAC.
        
        Args:
            user_context: Dict with user_id, role, department, etc.
            intent: Intent category
            
        Returns:
            True if allowed, False otherwise
        """
        role = user_context.get("role", "employee").lower()
        
        # Permission matrix: intent -> required role
        required_roles = {
            "employee_info": ["employee", "manager", "hr_generalist", "hr_admin"],
            "policy": ["employee", "manager", "hr_generalist", "hr_admin"],
            "leave": ["employee", "manager", "hr_generalist", "hr_admin"],
            "leave_request": ["employee", "manager", "hr_generalist", "hr_admin"],
            "onboarding": ["employee", "manager", "hr_generalist", "hr_admin"],
            "benefits": ["employee", "manager", "hr_generalist", "hr_admin"],
            "performance": ["manager", "hr_generalist", "hr_admin"],
            "analytics": ["manager", "hr_generalist", "hr_admin"],
            "compliance": ["employee", "manager", "hr_generalist", "hr_admin"],
            "unclear": ["employee", "manager", "hr_generalist", "hr_admin"],
        }
        
        allowed_roles = required_roles.get(intent, ["employee"])
        
        if role in allowed_roles:
            logger.info(f"PERMISSION: {role} allowed for {intent}")
            return True
        
        logger.warning(f"PERMISSION: {role} denied for {intent}")
        return False
    
    # ==================== Agent Dispatch ====================
    
    def dispatch_to_agent(
        self,
        intent: str,
        query: str,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch query to appropriate specialist agent.
        
        Instantiates agent if not cached, then runs it.
        
        Args:
            intent: Intent category
            query: User query
            user_context: User info
            
        Returns:
            Dict with agent result (answer, sources, confidence, etc.)
        """
        logger.info(f"DISPATCH: {intent} agent for query: {query[:50]}...")
        
        agent_class_name = self.AGENT_REGISTRY.get(intent)
        
        if not agent_class_name:
            logger.warning(f"DISPATCH: No agent for intent '{intent}'")
            return {
                "answer": f"No specialist agent available for {intent}",
                "confidence": 0.0,
                "agent_type": "none",
                "error": "No agent registered",
            }
        
        # Try to get or create agent instance
        try:
            if agent_class_name not in self.agent_cache:
                # Dynamically import the specialist agent
                logger.info(f"DISPATCH: Instantiating {agent_class_name}")
                agent_instance = self._import_agent(intent, agent_class_name)
                self.agent_cache[agent_class_name] = agent_instance

            agent = self.agent_cache.get(agent_class_name)

            if agent is None:
                # Fallback: use the LLM directly with a specialist prompt
                logger.info(f"DISPATCH: Using LLM fallback for {intent}")
                return self._llm_fallback(intent, query, user_context)

            # Run agent — if it fails (e.g. LLM unavailable), use fallback
            try:
                result = agent.run(query, user_context)
                # Check if agent returned a valid answer
                if result.get("confidence", 0) > 0:
                    return result
                # Agent returned zero confidence — try LLM fallback
                logger.warning(f"DISPATCH: Agent returned low confidence, trying fallback")
                return self._llm_fallback(intent, query, user_context)
            except Exception as agent_err:
                logger.warning(f"DISPATCH: Agent execution failed ({agent_err}), using fallback")
                return self._llm_fallback(intent, query, user_context)

        except Exception as e:
            logger.error(f"DISPATCH: Failed to dispatch: {e}")
            return self._llm_fallback(intent, query, user_context)
    
    # ==================== Multi-Intent Handling ====================
    
    def handle_multi_intent(
        self,
        intents: List[tuple[str, float]],
        query: str,
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Handle queries that span multiple intents.
        
        Dispatches to multiple agents and collects results.
        
        Args:
            intents: List of (intent, confidence) tuples, sorted by confidence
            query: User query
            user_context: User info
            
        Returns:
            List of agent results
        """
        logger.info(f"MULTI_INTENT: Handling {len(intents)} intents")
        
        results = []
        
        for intent, confidence in intents:
            if confidence < 0.4:
                logger.info(f"MULTI_INTENT: Skipping {intent} (confidence={confidence})")
                continue
            
            if not self.check_permissions(user_context, intent):
                logger.warning(f"MULTI_INTENT: Permission denied for {intent}")
                results.append({
                    "intent": intent,
                    "error": "Permission denied",
                    "confidence": 0.0,
                })
                continue
            
            result = self.dispatch_to_agent(intent, query, user_context)
            result["intent"] = intent
            results.append(result)
        
        return results
    
    # ==================== Response Merging ====================
    
    def merge_responses(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multi-agent results into unified response.
        
        Args:
            results: List of agent results
            
        Returns:
            Merged response dict
        """
        logger.info(f"MERGE: Combining {len(results)} agent results")
        
        if not results:
            return {
                "answer": "No results to merge",
                "sources": [],
                "agents_used": [],
                "confidence": 0.0,
            }
        
        if len(results) == 1:
            return results[0]
        
        # Merge multiple results
        merged_answer = "Based on multiple analyses:\n\n"
        all_sources = []
        agents_used = []
        confidence_sum = 0.0
        
        for i, result in enumerate(results, 1):
            answer = result.get("answer", f"Agent {i} response")
            merged_answer += f"{i}. {answer}\n"
            
            all_sources.extend(result.get("sources", []))
            agents_used.append(result.get("agent_type", "unknown"))
            confidence_sum += result.get("confidence", 0.0)
        
        avg_confidence = confidence_sum / len(results) if results else 0.0
        
        return {
            "answer": merged_answer,
            "sources": list({str(s) for s in all_sources}),  # Deduplicate
            "agents_used": agents_used,
            "confidence": avg_confidence,
        }
    
    # ==================== Public Interface ====================
    
    def run(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Run router agent to process query and dispatch to specialists.
        
        Main entry point for multi-agent orchestration.
        
        Args:
            query: User question/request
            user_context: User info (id, role, department, etc.)
            conversation_history: Prior conversation context
            
        Returns:
            Dict with keys:
            - answer: Final response from specialist agent(s)
            - sources: List of source references
            - agent_type: "router"
            - confidence: Confidence score
            - intents: List of (intent, confidence) tuples
            - agents_used: Names of specialist agents invoked
        """
        if user_context is None:
            user_context = {
                "user_id": "unknown",
                "role": "employee",
                "department": "unknown",
            }
        
        logger.info(f"ROUTER: Processing query: {query[:60]}...")
        
        # Step 1: Classify intent(s)
        intent, confidence = self.classify_intent(query)
        intents = [(intent, confidence)]
        
        # Step 2: Check if clarification needed
        if confidence < 0.5:
            logger.info(f"ROUTER: Low confidence ({confidence}), seeking clarification")
            clarification = self._generate_clarification(query)
            return {
                "answer": clarification,
                "requires_clarification": True,
                "confidence": confidence,
                "agent_type": "router",
                "intents": intents,
            }
        
        # Step 3: Check permissions
        if not self.check_permissions(user_context, intent):
            return {
                "answer": f"You do not have permission to access {intent} information",
                "confidence": 1.0,
                "agent_type": "router",
                "error": "Permission denied",
                "intents": intents,
            }
        
        # Step 4: Dispatch and execute
        if intent == "multi_intent":
            results = self.handle_multi_intent(intents, query, user_context)
            merged = self.merge_responses(results)
            merged["agent_type"] = "router"
            merged["intents"] = intents
            return merged
        else:
            result = self.dispatch_to_agent(intent, query, user_context)
            result["agent_type"] = "router"
            result["intents"] = intents
            return result
    
    # ==================== Helper Methods ====================

    def _import_agent(self, intent: str, class_name: str):
        """Attempt to dynamically import and instantiate a specialist agent."""
        if self.llm is None:
            logger.info(f"DISPATCH: LLM not available, skipping agent import for {class_name}")
            return None

        agent_modules = {
            "employee_info": "src.agents.employee_info_agent",
            "policy": "src.agents.policy_agent",
            "leave": "src.agents.leave_agent",
            "leave_request": "src.agents.leave_request_agent",
            "onboarding": "src.agents.onboarding_agent",
            "benefits": "src.agents.benefits_agent",
            "performance": "src.agents.performance_agent",
            "analytics": "src.agents.performance_agent",
            "compliance": "src.agents.compliance_agent",
        }
        module_path = agent_modules.get(intent)
        if not module_path:
            return None
        try:
            import importlib
            import inspect
            mod = importlib.import_module(module_path)
            agent_cls = getattr(mod, class_name, None)
            if agent_cls:
                sig = inspect.signature(agent_cls.__init__)
                kwargs = {}

                # Inject HRIS connector
                if "hris_connector" in sig.parameters:
                    try:
                        from src.connectors.local_db import LocalDBConnector
                        kwargs["hris_connector"] = LocalDBConnector()
                        logger.info(f"DISPATCH: Injecting LocalDBConnector into {class_name}")
                    except Exception as conn_err:
                        logger.warning(f"DISPATCH: Could not inject connector: {conn_err}")

                # Inject NotificationService
                if "notification_service" in sig.parameters:
                    try:
                        from src.core.notifications import NotificationService
                        kwargs["notification_service"] = NotificationService()
                        logger.info(f"DISPATCH: Injecting NotificationService into {class_name}")
                    except Exception as notif_err:
                        logger.warning(f"DISPATCH: Could not inject NotificationService: {notif_err}")

                # Inject BiasAuditor
                if "bias_auditor" in sig.parameters:
                    try:
                        from src.core.bias_audit import BiasAuditor
                        kwargs["bias_auditor"] = BiasAuditor()
                        logger.info(f"DISPATCH: Injecting BiasAuditor into {class_name}")
                    except Exception as bias_err:
                        logger.warning(f"DISPATCH: Could not inject BiasAuditor: {bias_err}")

                # Inject ComplianceEngine
                if "compliance_engine" in sig.parameters:
                    try:
                        from src.core.multi_jurisdiction import MultiJurisdictionEngine
                        kwargs["compliance_engine"] = MultiJurisdictionEngine()
                        logger.info(f"DISPATCH: Injecting ComplianceEngine into {class_name}")
                    except Exception as comp_err:
                        logger.warning(f"DISPATCH: Could not inject ComplianceEngine: {comp_err}")

                # Inject RAG pipeline
                if "rag_pipeline" in sig.parameters:
                    try:
                        from src.core.rag_pipeline import RAGPipeline
                        kwargs["rag_pipeline"] = RAGPipeline()
                        logger.info(f"DISPATCH: Injecting RAGPipeline into {class_name}")
                    except Exception as rag_err:
                        logger.warning(f"DISPATCH: Could not inject RAGPipeline: {rag_err}")

                # Inject PII stripper
                if "pii_stripper" in sig.parameters:
                    try:
                        from src.middleware.pii_stripper import PIIStripper
                        kwargs["pii_stripper"] = PIIStripper()
                        logger.info(f"DISPATCH: Injecting PIIStripper into {class_name}")
                    except Exception as pii_err:
                        logger.warning(f"DISPATCH: Could not inject PIIStripper: {pii_err}")

                # Inject DSAR Repository
                if "dsar_repository" in sig.parameters:
                    try:
                        from src.repositories.gdpr_repository import DSARRepository
                        kwargs["dsar_repository"] = DSARRepository()
                        logger.info(f"DISPATCH: Injecting DSARRepository into {class_name}")
                    except Exception as dsar_err:
                        logger.warning(f"DISPATCH: Could not inject DSARRepository: {dsar_err}")

                # Inject GDPR Repository
                if "gdpr_repository" in sig.parameters:
                    try:
                        from src.repositories.gdpr_repository import GDPRRepository
                        kwargs["gdpr_repository"] = GDPRRepository()
                        logger.info(f"DISPATCH: Injecting GDPRRepository into {class_name}")
                    except Exception as gdpr_err:
                        logger.warning(f"DISPATCH: Could not inject GDPRRepository: {gdpr_err}")

                return agent_cls(self.llm, **kwargs)
        except Exception as e:
            logger.warning(f"DISPATCH: Could not import {class_name}: {e}")
        return None

    def _llm_fallback(
        self, intent: str, query: str, user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Answer the query directly via the LLM when no specialist agent is available."""
        # Static knowledge base for when LLM is not available
        static_responses = {
            "policy": "Our company policies cover areas including remote work, code of conduct, anti-harassment, data privacy, and workplace safety. Key policies: employees must follow the acceptable use policy for IT resources, maintain confidentiality of proprietary information, and comply with all applicable employment laws. For specific policy details, please contact HR or check the employee handbook on the company intranet.",
            "leave": "Our leave policy includes: Annual PTO (15-25 days based on tenure), Sick Leave (10 days/year), Personal Days (3 days/year), Parental Leave (12 weeks paid), Bereavement Leave (3-5 days), and Jury Duty leave. PTO requests should be submitted at least 2 weeks in advance through the HR portal. Unused PTO can be carried over up to 5 days. For FMLA-eligible leave, please contact HR directly.",
            "benefits": "Employee benefits include: Medical/Dental/Vision insurance (company covers 80% of premiums), 401(k) with 4% company match, Life Insurance (2x salary), Short/Long-term Disability, Employee Assistance Program (EAP), Education Reimbursement ($5,250/year), Commuter Benefits, and Wellness Program credits. Open enrollment is in November each year.",
            "employee_info": "You can view and update your employee profile through the HR self-service portal. This includes personal contact information, emergency contacts, tax withholding (W-4), direct deposit, and benefits elections. For compensation questions, please speak with your manager or HR Business Partner.",
            "onboarding": "New hire onboarding includes: Day 1 orientation (HR paperwork, office tour, IT setup), Week 1 (team introductions, role overview, system access), Month 1 (buddy program, initial training, 30-day check-in), and Month 3 (90-day performance review). All onboarding materials are available in the New Hire portal.",
            "performance": "Performance management includes: quarterly goal-setting, mid-year reviews, annual performance evaluations, and continuous feedback through the 360-review system. Annual reviews are conducted in Q4. Merit increases and promotions are determined based on performance ratings, market data, and budget availability.",
            "analytics": "HR analytics dashboards are available for authorized managers showing: headcount trends, turnover rates, time-to-fill metrics, diversity statistics, and engagement scores. For custom reports, submit a request through the HR analytics portal.",
            "leave_request": "To submit a leave request, specify the leave type (vacation, sick, or personal), start date, and end date. Your request will be submitted for manager approval. You can track the status in the Leave Management section.",
            "compliance": "The company is committed to data privacy and GDPR compliance. You can exercise your data subject rights including: Right of Access (request a copy of your personal data), Right to Erasure, Right to Rectification, and Right to Data Portability. To submit a Data Subject Access Request (DSAR), contact the Data Protection Officer at dpo@company.com. DSARs are processed within 30 days per GDPR Article 12. For CCPA requests (California employees), the response deadline is 45 days.",
        }

        # If LLM is not available, use static responses
        if self.llm is None:
            static_answer = static_responses.get(intent)
            if static_answer:
                return {
                    "answer": static_answer,
                    "confidence": 0.75,
                    "agent_type": intent,
                    "sources": ["company_knowledge_base"],
                }
            return {
                "answer": f"Your question about '{intent}' has been noted. Please contact HR directly for detailed information, or try again when the LLM service is available.",
                "confidence": 0.4,
                "agent_type": intent,
                "sources": [],
            }

        specialist_prompts = {
            "employee_info": "You are an HR employee information specialist. Answer questions about employee profiles, compensation, and contact details.",
            "policy": "You are an HR policy expert. Answer questions about company policies, compliance rules, procedures, and guidelines.",
            "leave": "You are an HR leave management specialist. Answer questions about PTO, sick leave, vacation, and time-off policies.",
            "onboarding": "You are an HR onboarding specialist. Answer questions about new-hire orientation, documentation, and onboarding processes.",
            "benefits": "You are an HR benefits specialist. Answer questions about health insurance, retirement plans, 401k, and employee perks.",
            "performance": "You are an HR performance management specialist. Answer questions about reviews, goals, feedback, and development plans.",
            "analytics": "You are an HR analytics specialist. Answer questions about workforce reports, statistics, and trends.",
            "leave_request": "You are an HR leave management specialist. Help employees submit leave requests, specifying leave type, dates, and reason.",
            "compliance": "You are a data privacy and compliance specialist. Answer questions about GDPR, CCPA, data subject rights, DSARs, PII handling, and multi-jurisdiction compliance requirements.",
        }
        system_msg = specialist_prompts.get(
            intent,
            "You are a helpful HR assistant. Answer the employee's question accurately and concisely.",
        )

        # Enrich prompt with real DB context when available
        db_context = ""
        try:
            from src.connectors.local_db import LocalDBConnector
            connector = LocalDBConnector()
            uid = user_context.get("user_id", "")

            if intent in ("leave", "leave_request") and uid and uid != "unknown":
                balances = connector.get_leave_balance(uid)
                if balances:
                    bal_lines = [f"  - {b.leave_type.value}: {b.available_days:.0f} of {b.total_days:.0f} days remaining" for b in balances]
                    db_context += f"\n\nCurrent leave balances for this employee:\n" + "\n".join(bal_lines)
                requests = connector.get_leave_requests(uid)
                if requests:
                    req_lines = [f"  - {r.leave_type.value} {r.start_date.strftime('%Y-%m-%d')} to {r.end_date.strftime('%Y-%m-%d')} ({r.status.value})" for r in requests[:5]]
                    db_context += f"\n\nRecent leave requests:\n" + "\n".join(req_lines)

            elif intent == "employee_info" and uid and uid != "unknown":
                emp = connector.get_employee(uid)
                if emp:
                    db_context += f"\n\nAsking employee: {emp.first_name} {emp.last_name}, {emp.job_title} in {emp.department}."

            elif intent == "analytics":
                from src.core.database import SessionLocal, Employee as DBEmp
                if SessionLocal:
                    s = SessionLocal()
                    try:
                        total = s.query(DBEmp).filter_by(status="active").count()
                        depts = s.query(DBEmp.department, sa_func.count()).filter_by(status="active").group_by(DBEmp.department).all()
                        dept_str = ", ".join(f"{d}: {c}" for d, c in depts[:8])
                        db_context += f"\n\nCurrent org: {total} active employees. By department: {dept_str}."
                    except Exception:
                        pass
                    finally:
                        s.close()
        except Exception as ctx_err:
            logger.debug(f"DISPATCH: Could not enrich LLM context: {ctx_err}")

        messages = [
            SystemMessage(content=system_msg + db_context),
            HumanMessage(content=query),
        ]
        try:
            response = self.llm.invoke(messages)
            answer = getattr(response, "content", str(response))
            return {
                "answer": answer,
                "confidence": 0.85,
                "agent_type": intent,
                "sources": [],
            }
        except Exception as e:
            logger.error(f"DISPATCH: LLM fallback failed: {e}")
            return {
                "answer": f"I understand you're asking about {intent}. I'm unable to process this right now — please try again shortly.",
                "confidence": 0.3,
                "agent_type": intent,
                "error": str(e),
            }

    def _generate_clarification(self, query: str) -> str:
        """
        Generate clarification question for ambiguous queries.
        
        Args:
            query: Original query
            
        Returns:
            Clarification question string
        """
        clarification_prompt = f"""Generate a brief clarification question for this ambiguous HR query.

QUERY: {query}

Return a natural clarification question (1-2 sentences) to help narrow the request."""
        
        messages = [
            SystemMessage(content="You are an HR assistant."),
            HumanMessage(content=clarification_prompt),
        ]
        
        try:
            response = self.llm.invoke(messages)
            return getattr(response, "content", str(response))
        except Exception as e:
            logger.error(f"Clarification generation failed: {e}")
            return f"Could you clarify your question about: {query[:30]}...?"
    
    @staticmethod
    def _parse_json_response(text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response.
        
        Args:
            text: Response text
            
        Returns:
            Parsed JSON dict
            
        Raises:
            ValueError: If no valid JSON found
        """
        import re
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"No valid JSON found in response")


# Example usage demonstrating the router
def example_router_usage():
    """Example showing how RouterAgent is used."""
    # from langchain_google_genai import ChatGoogleGenerativeAI
    # llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", ...)
    # router = RouterAgent(llm)
    # result = router.run(
    #     query="What's the policy on remote work?",
    #     user_context={"user_id": "emp123", "role": "employee", "department": "engineering"}
    # )
    # print(result["answer"])
    pass
