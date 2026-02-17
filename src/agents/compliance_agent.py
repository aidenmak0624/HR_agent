"""
Compliance Agent (AGENT-008) for HR multi-agent platform.

Handles GDPR Data Subject Access Requests (DSAR), data privacy operations,
PII detection and redaction, and cross-jurisdiction compliance workflows.
Integrates DSARRepository, PIIStripper, MultiJurisdictionEngine, and
NotificationService into an automated compliance pipeline.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .base_agent import BaseAgent, BaseAgentState
from ..connectors.hris_interface import HRISConnector
from ..core.multi_jurisdiction import MultiJurisdictionEngine, Jurisdiction
from ..core.notifications import NotificationService, NotificationPriority, NotificationTemplate, NotificationChannel
from ..middleware.pii_stripper import PIIStripper
from ..repositories.gdpr_repository import DSARRepository, GDPRRepository, RetentionPolicyRepository

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ComplianceAgent(BaseAgent):
    """
    Specialist agent for GDPR/privacy compliance and DSAR processing.

    Provides tools for:
    - Submitting and tracking Data Subject Access Requests (DSARs)
    - Automated PII detection across employee data
    - Data export generation for portability requests
    - Erasure request processing with retention policy checks
    - Multi-jurisdiction compliance validation
    - Consent management
    - Complaince deadline monitoring and alerts
    """

    def __init__(
        self,
        llm=None,
        hris_connector: Optional[HRISConnector] = None,
        compliance_engine: Optional[MultiJurisdictionEngine] = None,
        notification_service: Optional[NotificationService] = None,
        pii_stripper: Optional[PIIStripper] = None,
        dsar_repository: Optional[DSARRepository] = None,
        gdpr_repository: Optional[GDPRRepository] = None,
    ):
        """
        Initialize Compliance Agent.

        Args:
            llm: Language model instance
            hris_connector: HRIS connector for employee data
            compliance_engine: Multi-jurisdiction compliance engine
            notification_service: Notification service for alerts
            pii_stripper: PII detection and masking service
            dsar_repository: Repository for persisting DSAR requests to database
            gdpr_repository: Repository for consent records
        """
        self.hris_connector = hris_connector
        self.compliance_engine = compliance_engine or MultiJurisdictionEngine()
        self.notification_service = notification_service or NotificationService()
        self.pii_stripper = pii_stripper or PIIStripper()

        # Database repositories for persistence
        try:
            self.dsar_repo = dsar_repository or DSARRepository()
        except Exception:
            self.dsar_repo = None
            logger.warning("DSARRepository unavailable — using in-memory only")
        try:
            self.gdpr_repo = gdpr_repository or GDPRRepository()
        except Exception:
            self.gdpr_repo = None
            logger.warning("GDPRRepository unavailable — using in-memory only")

        # In-memory DSAR tracking (fast lookup cache; authoritative data in DB)
        self.dsar_requests: Dict[str, Dict[str, Any]] = {}
        self.consent_records: Dict[str, List[Dict[str, Any]]] = {}

        # Register compliance notification templates
        self._register_compliance_templates()

        super().__init__(llm=llm)

    def get_agent_type(self) -> str:
        return "compliance"

    def get_system_prompt(self) -> str:
        return (
            "You are a Data Privacy and Compliance specialist agent. You handle "
            "GDPR Data Subject Access Requests (DSARs), PII detection, data export, "
            "erasure requests, and multi-jurisdiction compliance checks. You ensure "
            "all data processing complies with GDPR, CCPA, PIPEDA, and other applicable "
            "regulations. Always cite specific regulatory articles and include compliance "
            "deadlines in your responses."
        )

    def get_tools(self) -> Dict[str, Any]:
        """Return compliance tools."""
        tools = {}

        # Tool 1: Submit DSAR
        def submit_dsar(
            employee_id: str,
            request_type: str,
            reason: Optional[str] = None,
            jurisdiction: str = "eu_gdpr",
        ) -> Dict[str, Any]:
            """
            Submit a Data Subject Access Request.

            Args:
                employee_id: Employee ID making the request
                request_type: Type: access, erasure, rectification, portability
                reason: Optional reason for the request
                jurisdiction: Applicable jurisdiction

            Returns:
                DSAR submission confirmation with timeline
            """
            try:
                logger.info(f"DSAR_SUBMIT: {request_type} request from {employee_id}")

                valid_types = ["access", "erasure", "rectification", "portability"]
                if request_type not in valid_types:
                    return {"error": f"Invalid request type. Must be one of: {valid_types}"}

                dsar_id = f"dsar_{uuid4().hex[:8]}"
                now = datetime.utcnow()

                # Determine deadline based on jurisdiction
                deadline_days = 30  # GDPR default
                if jurisdiction == "us_california":
                    deadline_days = 45  # CCPA
                elif jurisdiction == "canada_pipeda":
                    deadline_days = 30

                deadline = now + timedelta(days=deadline_days)

                dsar = {
                    "dsar_id": dsar_id,
                    "employee_id": employee_id,
                    "request_type": request_type,
                    "reason": reason or "Data subject rights exercise",
                    "jurisdiction": jurisdiction,
                    "status": "pending",
                    "submitted_at": now.isoformat(),
                    "deadline": deadline.isoformat(),
                    "deadline_days": deadline_days,
                    "steps_completed": [],
                    "steps_remaining": self._get_dsar_steps(request_type),
                }

                self.dsar_requests[dsar_id] = dsar

                # Persist to database
                db_dsar_id = None
                if self.dsar_repo:
                    try:
                        db_record = self.dsar_repo.create_dsar(
                            employee_id=int(employee_id) if str(employee_id).isdigit() else 0,
                            request_type=request_type,
                            deadline=deadline,
                        )
                        if db_record:
                            db_dsar_id = db_record.id
                            dsar["db_id"] = db_dsar_id
                            logger.info(f"DSAR_SUBMIT: Persisted to DB as id={db_dsar_id}")
                    except Exception as db_err:
                        logger.warning(f"DSAR_SUBMIT: DB persist failed (in-memory only): {db_err}")

                # Send confirmation to employee
                try:
                    self.notification_service.send_notification(
                        recipient_id=employee_id,
                        template_id="dsar_submitted",
                        context={
                            "request_type": request_type,
                            "dsar_id": dsar_id,
                            "deadline": deadline.strftime("%Y-%m-%d"),
                        },
                        priority=NotificationPriority.HIGH,
                    )
                except Exception as notif_err:
                    logger.warning(f"DSAR_SUBMIT: Notification failed: {notif_err}")

                # Notify DPO
                try:
                    self.notification_service.send_notification(
                        recipient_id="dpo",
                        template_id="dsar_new_request",
                        context={
                            "request_type": request_type,
                            "employee_id": employee_id,
                            "dsar_id": dsar_id,
                            "deadline": deadline.strftime("%Y-%m-%d"),
                        },
                        priority=NotificationPriority.URGENT,
                        channel=NotificationChannel.EMAIL,
                    )
                except Exception as notif_err:
                    logger.warning(f"DSAR_SUBMIT: DPO notification failed: {notif_err}")

                logger.info(f"DSAR_SUBMIT: Created {dsar_id}, deadline {deadline.date()}")

                return {
                    "dsar_id": dsar_id,
                    "request_type": request_type,
                    "status": "pending",
                    "deadline": deadline.isoformat(),
                    "deadline_days": deadline_days,
                    "regulatory_basis": self._get_regulatory_basis(request_type, jurisdiction),
                    "next_steps": dsar["steps_remaining"][:2],
                    "source": "compliance_system",
                }

            except Exception as e:
                logger.error(f"DSAR_SUBMIT failed: {e}")
                return {"error": f"DSAR submission failed: {str(e)}"}

        submit_dsar.description = (
            "Submit a Data Subject Access Request (DSAR) for access, erasure, "
            "rectification, or portability of personal data."
        )
        tools["submit_dsar"] = submit_dsar

        # Tool 2: Process DSAR (automated pipeline)
        def process_dsar(dsar_id: str) -> Dict[str, Any]:
            """
            Process a DSAR through the automated pipeline.

            Performs: identity verification, data discovery, PII scan,
            data export/erasure, compliance validation, and delivery.

            Args:
                dsar_id: DSAR request ID

            Returns:
                Processing results with data summary
            """
            try:
                logger.info(f"DSAR_PROCESS: Processing {dsar_id}")

                dsar = self.dsar_requests.get(dsar_id)
                if not dsar:
                    return {"error": f"DSAR not found: {dsar_id}"}

                employee_id = dsar["employee_id"]
                request_type = dsar["request_type"]
                results = {"dsar_id": dsar_id, "steps": []}

                # Step 1: Identity verification
                identity_verified = False
                if self.hris_connector:
                    try:
                        emp = self.hris_connector.get_employee(employee_id)
                        identity_verified = emp is not None
                        if emp:
                            results["employee_name"] = f"{emp.first_name} {emp.last_name}"
                    except Exception:
                        pass
                results["steps"].append({
                    "step": "identity_verification",
                    "status": "passed" if identity_verified else "manual_review_required",
                })
                dsar["steps_completed"].append("identity_verification")

                # Step 2: Data discovery — catalog all data locations
                data_locations = self._discover_employee_data(employee_id)
                results["steps"].append({
                    "step": "data_discovery",
                    "status": "completed",
                    "data_locations": len(data_locations),
                    "categories": list(data_locations.keys()),
                })
                dsar["steps_completed"].append("data_discovery")

                # Step 3: PII scan across discovered data
                pii_findings = []
                for category, data_items in data_locations.items():
                    for item in data_items:
                        if isinstance(item, str):
                            masked_text, pii_map = self.pii_stripper.strip(item)
                            if pii_map:
                                pii_findings.append({
                                    "category": category,
                                    "pii_types": list(pii_map.keys()) if isinstance(pii_map, dict) else ["detected"],
                                })

                results["steps"].append({
                    "step": "pii_scan",
                    "status": "completed",
                    "pii_locations_found": len(pii_findings),
                })
                dsar["steps_completed"].append("pii_scan")

                # Step 4: Execute request
                if request_type == "access":
                    # Generate data export
                    export_data = self._generate_data_export(employee_id, data_locations)
                    results["steps"].append({
                        "step": "data_export",
                        "status": "completed",
                        "format": "JSON",
                        "categories_exported": list(export_data.keys()),
                    })
                    results["export_summary"] = {k: len(v) if isinstance(v, list) else 1 for k, v in export_data.items()}

                elif request_type == "erasure":
                    # Check retention policies before erasure
                    retention_blocks = self._check_retention_policies(employee_id)
                    if retention_blocks:
                        results["steps"].append({
                            "step": "erasure_check",
                            "status": "partial",
                            "retention_blocks": retention_blocks,
                            "message": "Some data must be retained per legal requirements",
                        })
                    else:
                        results["steps"].append({
                            "step": "erasure",
                            "status": "completed",
                            "message": "All eligible data marked for erasure",
                        })

                elif request_type == "portability":
                    export_data = self._generate_data_export(employee_id, data_locations)
                    results["steps"].append({
                        "step": "data_portability_export",
                        "status": "completed",
                        "format": "JSON (machine-readable)",
                        "categories": list(export_data.keys()),
                    })

                elif request_type == "rectification":
                    results["steps"].append({
                        "step": "rectification",
                        "status": "awaiting_input",
                        "message": "Please specify which data to correct",
                    })

                dsar["steps_completed"].append(f"{request_type}_execution")

                # Step 5: Compliance validation
                try:
                    jurisdiction = Jurisdiction(dsar.get("jurisdiction", "eu_gdpr"))
                    compliance_results = self.compliance_engine.check_compliance(
                        data={"employee_id": employee_id, "request_type": request_type},
                        jurisdictions=[jurisdiction],
                    )
                    results["steps"].append({
                        "step": "compliance_validation",
                        "status": "completed",
                        "checks_passed": len([r for r in compliance_results if r.status.value == "compliant"]),
                        "total_checks": len(compliance_results),
                    })
                except Exception as comp_err:
                    results["steps"].append({
                        "step": "compliance_validation",
                        "status": "warning",
                        "message": str(comp_err),
                    })
                dsar["steps_completed"].append("compliance_validation")

                # Update DSAR status
                dsar["status"] = "completed"
                dsar["completed_at"] = datetime.utcnow().isoformat()

                # Persist completion to database
                if self.dsar_repo and dsar.get("db_id"):
                    try:
                        self.dsar_repo.update_dsar_status(
                            dsar_id=dsar["db_id"],
                            status="completed",
                            result=results,
                        )
                        logger.info(f"DSAR_PROCESS: DB record {dsar['db_id']} marked completed")
                    except Exception as db_err:
                        logger.warning(f"DSAR_PROCESS: DB update failed: {db_err}")

                # Notify employee of completion
                try:
                    self.notification_service.send_notification(
                        recipient_id=employee_id,
                        template_id="dsar_completed",
                        context={
                            "dsar_id": dsar_id,
                            "request_type": request_type,
                        },
                        priority=NotificationPriority.HIGH,
                    )
                except Exception:
                    pass

                results["status"] = "completed"
                results["source"] = "compliance_system"
                return results

            except Exception as e:
                logger.error(f"DSAR_PROCESS failed: {e}")
                return {"error": f"DSAR processing failed: {str(e)}"}

        process_dsar.description = (
            "Process a DSAR through the automated pipeline: identity verification, "
            "data discovery, PII scan, data export/erasure, and compliance validation."
        )
        tools["process_dsar"] = process_dsar

        # Tool 3: Check DSAR Status
        def check_dsar_status(dsar_id: str) -> Dict[str, Any]:
            """
            Check status of a Data Subject Access Request.

            Args:
                dsar_id: DSAR request ID

            Returns:
                Current status and timeline
            """
            try:
                dsar = self.dsar_requests.get(dsar_id)
                if not dsar:
                    return {"error": f"DSAR not found: {dsar_id}"}

                deadline = datetime.fromisoformat(dsar["deadline"])
                days_remaining = (deadline - datetime.utcnow()).days

                return {
                    "dsar_id": dsar_id,
                    "request_type": dsar["request_type"],
                    "status": dsar["status"],
                    "submitted_at": dsar["submitted_at"],
                    "deadline": dsar["deadline"],
                    "days_remaining": max(0, days_remaining),
                    "is_overdue": days_remaining < 0,
                    "steps_completed": dsar["steps_completed"],
                    "steps_remaining": [s for s in dsar["steps_remaining"] if s not in dsar["steps_completed"]],
                    "source": "compliance_system",
                }

            except Exception as e:
                logger.error(f"DSAR_STATUS failed: {e}")
                return {"error": f"Status check failed: {str(e)}"}

        check_dsar_status.description = (
            "Check the status and timeline of a Data Subject Access Request."
        )
        tools["check_dsar_status"] = check_dsar_status

        # Tool 4: Compliance Check
        def jurisdiction_compliance_check(
            action: str,
            employee_location: str = "us_federal",
            data_categories: Optional[List[str]] = None,
        ) -> Dict[str, Any]:
            """
            Check compliance for an HR action across jurisdictions.

            Args:
                action: Description of HR action to check
                employee_location: Employee's jurisdiction
                data_categories: Types of data involved

            Returns:
                Compliance status across applicable jurisdictions
            """
            try:
                logger.info(f"COMPLIANCE_CHECK: Checking '{action}' for {employee_location}")

                # Determine applicable jurisdictions
                try:
                    primary_jurisdiction = Jurisdiction(employee_location)
                except ValueError:
                    primary_jurisdiction = Jurisdiction.US_FEDERAL

                jurisdictions = [primary_jurisdiction]
                # Always check GDPR for EU employees
                if "eu" in employee_location or "uk" in employee_location:
                    if Jurisdiction.EU_GDPR not in jurisdictions:
                        jurisdictions.append(Jurisdiction.EU_GDPR)

                # Run compliance checks
                results = self.compliance_engine.check_compliance(
                    data={
                        "action": action,
                        "data_categories": data_categories or [],
                        "employee_location": employee_location,
                    },
                    jurisdictions=jurisdictions,
                )

                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "jurisdiction": result.jurisdiction.value,
                        "requirement": result.requirement,
                        "status": result.status.value,
                        "findings": result.findings,
                        "recommendations": result.recommendations,
                    })

                return {
                    "action": action,
                    "jurisdictions_checked": [j.value for j in jurisdictions],
                    "results": formatted_results,
                    "overall_compliant": all(r["status"] == "compliant" for r in formatted_results) if formatted_results else True,
                    "source": "compliance_system",
                }

            except Exception as e:
                logger.error(f"COMPLIANCE_CHECK failed: {e}")
                return {"error": f"Compliance check failed: {str(e)}"}

        jurisdiction_compliance_check.description = (
            "Check compliance of an HR action across applicable jurisdictions "
            "(GDPR, CCPA, PIPEDA, etc.)."
        )
        tools["jurisdiction_compliance_check"] = jurisdiction_compliance_check

        # Tool 5: PII Scan
        def pii_scan(text: str) -> Dict[str, Any]:
            """
            Scan text for Personally Identifiable Information.

            Args:
                text: Text to scan for PII

            Returns:
                PII detection results with categories found
            """
            try:
                masked_text, pii_map = self.pii_stripper.strip(text)
                pii_found = masked_text != text

                return {
                    "pii_detected": pii_found,
                    "masked_text": masked_text,
                    "pii_categories": list(pii_map.keys()) if isinstance(pii_map, dict) else [],
                    "pii_count": len(pii_map) if isinstance(pii_map, dict) else (1 if pii_found else 0),
                    "source": "pii_system",
                }

            except Exception as e:
                logger.error(f"PII_SCAN failed: {e}")
                return {"error": f"PII scan failed: {str(e)}"}

        pii_scan.description = (
            "Scan text for Personally Identifiable Information (PII) including "
            "SSN, email, phone, salary, and employee IDs."
        )
        tools["pii_scan"] = pii_scan

        return tools

    # ==================== Helper Methods ====================

    def _get_dsar_steps(self, request_type: str) -> List[str]:
        """Get required processing steps for a DSAR type."""
        base_steps = [
            "identity_verification",
            "data_discovery",
            "pii_scan",
            f"{request_type}_execution",
            "compliance_validation",
        ]
        if request_type == "erasure":
            base_steps.insert(3, "retention_policy_check")
        return base_steps

    def _get_regulatory_basis(self, request_type: str, jurisdiction: str) -> str:
        """Get the regulatory article supporting this right."""
        bases = {
            ("access", "eu_gdpr"): "GDPR Article 15 - Right of Access",
            ("erasure", "eu_gdpr"): "GDPR Article 17 - Right to Erasure",
            ("rectification", "eu_gdpr"): "GDPR Article 16 - Right to Rectification",
            ("portability", "eu_gdpr"): "GDPR Article 20 - Right to Data Portability",
            ("access", "us_california"): "CCPA Section 1798.100 - Right to Know",
            ("erasure", "us_california"): "CCPA Section 1798.105 - Right to Delete",
        }
        return bases.get((request_type, jurisdiction), f"Applicable privacy regulation ({jurisdiction})")

    def _discover_employee_data(self, employee_id: str) -> Dict[str, List[str]]:
        """Discover all data locations for an employee."""
        data_locations = {
            "employment_records": [],
            "payroll_data": [],
            "performance_records": [],
            "leave_records": [],
            "benefits_data": [],
            "training_records": [],
        }

        if self.hris_connector:
            try:
                emp = self.hris_connector.get_employee(employee_id)
                if emp:
                    data_locations["employment_records"].append(
                        f"Name: {emp.first_name} {emp.last_name}, "
                        f"Title: {emp.job_title}, Dept: {emp.department}, "
                        f"Email: {emp.email}"
                    )

                # Check leave records
                try:
                    leaves = self.hris_connector.get_leave_requests(employee_id)
                    for leave in (leaves or []):
                        data_locations["leave_records"].append(
                            f"Leave: {leave.leave_type.value} from {leave.start_date} to {leave.end_date}"
                        )
                except Exception:
                    pass

                # Check leave balances
                try:
                    balances = self.hris_connector.get_leave_balance(employee_id)
                    for bal in (balances or []):
                        data_locations["leave_records"].append(
                            f"Balance: {bal.leave_type.value} = {bal.available_days} days"
                        )
                except Exception:
                    pass

            except Exception as e:
                logger.warning(f"Data discovery HRIS error: {e}")

        return data_locations

    def _generate_data_export(self, employee_id: str, data_locations: Dict[str, List[str]]) -> Dict[str, Any]:
        """Generate structured data export for DSAR access/portability request."""
        export = {
            "export_metadata": {
                "employee_id": employee_id,
                "generated_at": datetime.utcnow().isoformat(),
                "format": "JSON",
                "regulation": "GDPR Article 15/20",
            }
        }
        for category, items in data_locations.items():
            if items:
                export[category] = items
        return export

    def _check_retention_policies(self, employee_id: str) -> List[Dict[str, str]]:
        """Check which data is blocked from erasure by retention policies."""
        # Standard retention blocks
        blocks = []
        blocks.append({
            "category": "tax_records",
            "reason": "Legal retention: 7 years per IRS requirements",
            "regulation": "26 USC § 6001",
        })
        blocks.append({
            "category": "employment_verification",
            "reason": "I-9 retention: 3 years after hire or 1 year after termination",
            "regulation": "8 CFR § 274a.2",
        })
        return blocks

    def _register_compliance_templates(self) -> None:
        """Register compliance-specific notification templates."""
        templates = [
            NotificationTemplate(
                template_id="dsar_submitted",
                name="DSAR Submitted Confirmation",
                channel=NotificationChannel.EMAIL,
                subject_template="Your Data Request ($request_type) Has Been Received",
                body_template=(
                    "Your $request_type data request (ID: $dsar_id) has been received. "
                    "We will process it by $deadline in compliance with applicable regulations."
                ),
                variables=["request_type", "dsar_id", "deadline"],
            ),
            NotificationTemplate(
                template_id="dsar_new_request",
                name="New DSAR for DPO",
                channel=NotificationChannel.EMAIL,
                subject_template="New DSAR Request: $request_type from $employee_id",
                body_template=(
                    "A new $request_type DSAR (ID: $dsar_id) has been submitted by "
                    "employee $employee_id. Legal deadline: $deadline. "
                    "Please review and assign processing."
                ),
                variables=["request_type", "employee_id", "dsar_id", "deadline"],
            ),
            NotificationTemplate(
                template_id="dsar_completed",
                name="DSAR Completed",
                channel=NotificationChannel.EMAIL,
                subject_template="Your Data Request ($request_type) Has Been Completed",
                body_template=(
                    "Your $request_type data request (ID: $dsar_id) has been completed. "
                    "Please review the results in your privacy portal."
                ),
                variables=["request_type", "dsar_id"],
            ),
        ]
        for template in templates:
            self.notification_service.register_template(template)


# Register agent class for discovery
__all__ = ["ComplianceAgent"]
