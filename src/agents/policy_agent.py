"""
Policy and Compliance Agent (AGENT-002) for HR multi-agent platform.

Handles policy searches, compliance verification, and citation generation
using RAG pipeline for authoritative policy information.
"""

import logging
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent, BaseAgentState
from ..core.rag_pipeline import RAGPipeline, RAGResult
from ..core.multi_jurisdiction import MultiJurisdictionEngine, Jurisdiction
from ..connectors.hris_interface import HRISConnector

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PolicyAgent(BaseAgent):
    """
    Specialist agent for policy search and compliance verification.
    
    Provides tools for:
    - Searching company policies using RAG
    - Verifying compliance with policy requirements
    - Generating proper citations for policy references
    - Providing authoritative policy guidance
    
    All responses include disclaimer about AI-generated guidance.
    """
    
    def __init__(
        self,
        llm=None,
        rag_pipeline: Optional[RAGPipeline] = None,
        compliance_engine: Optional[MultiJurisdictionEngine] = None,
        hris_connector: Optional[HRISConnector] = None,
    ):
        """
        Initialize Policy Agent.

        Args:
            llm: Language model instance (passed from RouterAgent)
            rag_pipeline: RAG pipeline instance for policy search
            compliance_engine: Multi-jurisdiction compliance engine
            hris_connector: HRIS connector for employee context
        """
        self.rag_pipeline = rag_pipeline
        self.compliance_engine = compliance_engine or MultiJurisdictionEngine()
        self.hris_connector = hris_connector
        super().__init__(llm=llm)
    
    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "policy"
    
    def get_system_prompt(self) -> str:
        """Return system prompt for policy specialist."""
        return (
            "You are a Policy and Compliance specialist agent. "
            "You search company policies, verify compliance, and provide authoritative answers with citations. "
            "Always include proper citations from the policy documents you reference. "
            "Include the following disclaimer in all responses: "
            "'Note: This is AI-generated guidance. Please consult HR for official decisions.' "
            "Be precise, reference specific policy sections, and explain how policies apply to scenarios."
        )
    
    def get_tools(self) -> Dict[str, Any]:
        """
        Return available tools for policy search and compliance.
        
        Tools:
        - rag_policy_search: Search policies by query
        - compliance_check: Verify if scenario complies with policies
        - citation_generator: Format search results as proper citations
        
        Returns:
            Dict of tool_name -> tool_function with description attribute
        """
        tools = {}
        
        # Tool 1: RAG Policy Search
        def rag_policy_search(query: str, collection: Optional[str] = None, top_k: int = 5, employee_id: Optional[str] = None) -> Dict[str, Any]:
            """
            Search company policies using RAG, with optional employee-context personalization.
            
            Args:
                query: Policy search query
                collection: Policy collection name (optional, defaults to policies)
                top_k: Number of results to return
                employee_id: Optional employee ID for personalized context
                
            Returns:
                List of relevant policy documents and excerpts
            """
            try:
                if not self.rag_pipeline:
                    return {"error": "RAG pipeline not available"}
                
                logger.info(f"RAG_SEARCH: Searching policies for: {query[:50]}")
                
                # Enrich query with employee context if available
                employee_context = ""
                if employee_id and self.hris_connector:
                    try:
                        emp = self.hris_connector.get_employee(employee_id)
                        if emp:
                            employee_context = (
                                f" (Employee context: {emp.job_title} in {emp.department}, "
                                f"location: {getattr(emp, 'location', 'N/A')})"
                            )
                            logger.info(f"RAG_SEARCH: Enriched with employee context for {employee_id}")
                    except Exception as ctx_err:
                        logger.warning(f"RAG_SEARCH: Could not get employee context: {ctx_err}")
                
                enriched_query = query + employee_context
                
                # Use "policies" collection by default
                collection_name = collection or "policies"
                
                # Search RAG pipeline
                results = self.rag_pipeline.search(
                    query=enriched_query,
                    collection=collection_name,
                    top_k=top_k,
                    min_score=0.3
                )
                
                if not results:
                    return {
                        "error": f"No policies found matching: {query}",
                        "suggestion": "Try refining your search query or contact HR for clarification."
                    }
                
                logger.info(f"RAG_SEARCH: Found {len(results)} results")
                
                # Format results for LLM
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "content": result.content,
                        "source": result.source,
                        "score": result.score,
                        "metadata": result.metadata,
                    })
                
                return {
                    "results": formatted_results,
                    "count": len(results),
                    "sources": list({r["source"] for r in formatted_results}),
                    "query": query,
                    "employee_context": employee_context.strip() if employee_context else None,
                }
                
            except Exception as e:
                logger.error(f"RAG_SEARCH failed: {e}")
                return {"error": f"Policy search failed: {str(e)}"}
        
        rag_policy_search.description = (
            "Search company policies using natural language query. "
            "Returns relevant policy excerpts with sources and relevance scores."
        )
        tools["rag_policy_search"] = rag_policy_search
        
        # Tool 2: Compliance Check
        def compliance_check(scenario: str, policy_query: Optional[str] = None) -> Dict[str, Any]:
            """
            Verify if a scenario complies with company policies.
            
            Args:
                scenario: Description of scenario to check
                policy_query: Optional specific policy to check against
                
            Returns:
                Compliance verdict with supporting citations
            """
            try:
                if not self.rag_pipeline:
                    return {"error": "RAG pipeline not available"}
                
                logger.info(f"COMPLIANCE_CHECK: Checking scenario: {scenario[:50]}")
                
                # Use provided query or extract key terms from scenario
                search_query = policy_query or scenario
                
                # Search relevant policies
                results = self.rag_pipeline.search(
                    query=search_query,
                    collection="policies",
                    top_k=5,
                    min_score=0.3
                )
                
                if not results:
                    return {
                        "compliant": "unknown",
                        "reason": "No relevant policies found",
                        "recommendation": "Contact HR for compliance verification",
                    }
                
                # Perform multi-jurisdiction compliance check
                jurisdiction_results = []
                try:
                    jurisdiction_check = self.compliance_engine.check_compliance(
                        data={"action": scenario, "scenario": scenario},
                    )
                    if jurisdiction_check:
                        jurisdiction_results = jurisdiction_check if isinstance(jurisdiction_check, list) else [jurisdiction_check]
                except Exception as comp_err:
                    logger.warning(f"COMPLIANCE_CHECK: Jurisdiction check failed: {comp_err}")
                
                # Analyze compliance using LLM if available
                compliance_verdict = "needs_review"
                llm_analysis = ""
                if self.llm:
                    try:
                        from langchain_core.messages import SystemMessage, HumanMessage
                        policy_excerpts = "\n\n".join(
                            [f"[{r.source}]: {r.content[:300]}" for r in results[:3]]
                        )
                        analysis_prompt = (
                            f"Based on these policy excerpts, determine if the following scenario "
                            f"is compliant:\n\nScenario: {scenario}\n\nPolicies:\n{policy_excerpts}\n\n"
                            f"Reply with a JSON: {{\"compliant\": \"yes\"/\"no\"/\"partial\", "
                            f"\"reasoning\": \"brief explanation\"}}"
                        )
                        response = self.llm.invoke([
                            SystemMessage(content="You are an HR compliance analyst."),
                            HumanMessage(content=analysis_prompt),
                        ])
                        raw = getattr(response, "content", str(response))
                        import json, re
                        match = re.search(r'\{[^{}]*\}', raw)
                        if match:
                            analysis = json.loads(match.group(0))
                            compliance_verdict = analysis.get("compliant", "needs_review")
                            llm_analysis = analysis.get("reasoning", "")
                    except Exception as llm_err:
                        logger.warning(f"COMPLIANCE_CHECK: LLM analysis failed: {llm_err}")
                
                compliance_analysis = {
                    "scenario": scenario,
                    "compliant": compliance_verdict,
                    "llm_reasoning": llm_analysis,
                    "matching_policies": len(results),
                    "jurisdiction_checks": len(jurisdiction_results),
                    "relevant_excerpts": [],
                    "sources": [],
                }
                
                for result in results:
                    compliance_analysis["relevant_excerpts"].append({
                        "content": result.content[:200],  # First 200 chars
                        "source": result.source,
                    })
                    if result.source not in compliance_analysis["sources"]:
                        compliance_analysis["sources"].append(result.source)
                
                return compliance_analysis
                
            except Exception as e:
                logger.error(f"COMPLIANCE_CHECK failed: {e}")
                return {"error": f"Compliance check failed: {str(e)}"}
        
        compliance_check.description = (
            "Verify if a scenario complies with company policies. "
            "Returns yes/no verdict with supporting citations from relevant policies."
        )
        tools["compliance_check"] = compliance_check
        
        # Tool 3: Citation Generator
        def citation_generator(rag_results: List[Dict[str, Any]]) -> Dict[str, List[str]]:
            """
            Format RAG results as proper citations.
            
            Args:
                rag_results: List of RAG result dicts with content, source, metadata
                
            Returns:
                Formatted citations in academic style
            """
            try:
                logger.info(f"CITATION_GENERATOR: Formatting {len(rag_results)} citations")
                
                citations = []
                
                for result in rag_results:
                    source = result.get("source", "Unknown")
                    content = result.get("content", "")[:100]  # First 100 chars
                    metadata = result.get("metadata", {})
                    
                    # Extract section if available
                    section = metadata.get("section", "")
                    page = metadata.get("page", "")
                    
                    # Format citation
                    if section and page:
                        citation = f"{source}, Section {section}, Page {page}: \"{content}...\""
                    elif section:
                        citation = f"{source}, Section {section}: \"{content}...\""
                    elif page:
                        citation = f"{source}, Page {page}: \"{content}...\""
                    else:
                        citation = f"{source}: \"{content}...\""
                    
                    citations.append(citation)
                
                return {
                    "citations": citations,
                    "count": len(citations),
                    "format": "Chicago Manual of Style (inline)",
                }
                
            except Exception as e:
                logger.error(f"CITATION_GENERATOR failed: {e}")
                return {"error": f"Citation generation failed: {str(e)}"}
        
        citation_generator.description = (
            "Format RAG results as proper citations. "
            "Converts search results into formatted citations with document, section, and page references."
        )
        tools["citation_generator"] = citation_generator
        
        return tools
    
    def _plan_node(self, state: BaseAgentState) -> BaseAgentState:
        """
        Create execution plan specific to policy queries.
        
        Determines search strategy based on query type:
        - Direct policy search: rag_policy_search + citation_generator
        - Compliance verification: compliance_check
        - Policy interpretation: rag_policy_search + citation_generator
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with plan
        """
        query = state.get("query", "").lower()
        plan = []
        
        logger.info(f"PLAN: Analyzing policy query: {query[:50]}")
        
        # Determine query type
        if any(word in query for word in ["compliant", "compliance", "allowed", "permitted", "can i"]):
            plan.append("Use compliance_check to verify scenario against policies")
            plan.append("Use rag_policy_search if additional context needed")
            plan.append("Use citation_generator to format policy references")
        elif any(word in query for word in ["find", "search", "look up", "what is", "tell me about"]):
            plan.append("Use rag_policy_search to find relevant policies")
            plan.append("Use citation_generator to format citations")
        elif any(word in query for word in ["interpret", "explain", "how do", "process"]):
            plan.append("Use rag_policy_search to find relevant policies")
            plan.append("Use citation_generator for proper citations")
        else:
            # Default: search then cite
            plan.append("Use rag_policy_search to find relevant policies")
            plan.append("Use citation_generator to format citations")
        
        state["plan"] = plan
        state["current_step"] = 0
        state.setdefault("reasoning_trace", []).append(f"Created policy plan with {len(plan)} steps")
        logger.info(f"PLAN: {plan}")
        
        return state
    
    def _finish_node(self, state: BaseAgentState) -> BaseAgentState:
        """
        Synthesize final answer with compliance disclaimer.
        
        Overrides base implementation to add disclaimer to all responses.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with final answer including disclaimer
        """
        # Call parent finish node
        state = super()._finish_node(state)
        
        # Add disclaimer to final answer
        final_answer = state.get("final_answer", "")
        disclaimer = (
            "\n\n---\n"
            "Note: This is AI-generated guidance. Please consult HR for official decisions."
        )
        
        state["final_answer"] = final_answer + disclaimer
        logger.info("FINISH: Added compliance disclaimer to response")
        
        return state


# Register agent class for discovery
__all__ = ["PolicyAgent"]
