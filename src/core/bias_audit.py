"""
PLAT-004: Bias Audit Framework
Algorithmic bias detection and audit framework for HR multi-agent platform.

Provides systematic detection of potential biases in agent responses, compensation
data, and HR decisions. Supports multiple bias categories with configurable severity
levels and actionable recommendations for bias remediation.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ProtectedCategory(str, Enum):
    """Protected categories under employment law (EEO compliance)."""
    GENDER = "gender"
    RACE = "race"
    AGE = "age"
    DISABILITY = "disability"
    VETERAN_STATUS = "veteran_status"
    RELIGION = "religion"


class BiasSeverity(str, Enum):
    """Severity levels for detected bias incidents."""
    LOW = "low"              # Language concern, minimal impact
    MEDIUM = "medium"        # Clear pattern, moderate concern
    HIGH = "high"            # Systematic bias, significant legal risk
    CRITICAL = "critical"    # Explicit discrimination, immediate action needed


@dataclass
class BiasIncident:
    """Record of detected bias incident."""
    incident_id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    category: ProtectedCategory = ProtectedCategory.GENDER
    severity: BiasSeverity = BiasSeverity.LOW
    description: str = ""
    agent_type: str = ""  # Agent that generated the response (e.g., "compensation")
    query: str = ""  # Original query that triggered response
    response: str = ""  # Agent's response containing bias
    timestamp: datetime = field(default_factory=datetime.utcnow)
    evidence: str = ""  # Specific text flagged as biased
    recommendations: List[str] = field(default_factory=list)


class BiasAuditor:
    """
    Detects and audits algorithmic bias in HR agent responses.

    Scans for biased language, stereotypes, exclusionary patterns, and
    compensation equity issues. Maintains audit trail and generates reports.
    """

    # Biased language lexicon by category
    BIAS_LEXICON: Dict[ProtectedCategory, Dict[str, List[str]]] = {
        ProtectedCategory.GENDER: {
            "terms": [
                "aggressive", "bossy", "pushy", "emotional", "bitchy",
                "hysterical", "shrill", "demanding", "difficult woman",
                "not a team player", "not confident", "stay-at-home mom",
            ],
            "patterns": [
                r"(he|she)\s+(is\s+)?(too\s+)?(emotional|hormonal|sensitive)",
                r"(man|woman|girl|boy)\s+(doesn't|can't)\s+\w+",
            ]
        },
        ProtectedCategory.RACE: {
            "terms": [
                "articulate", "well-spoken", "professional", "urban",
                "inner-city", "diverse", "quota", "special hire",
                "affirmative action", "urban market",
            ],
            "patterns": [
                r"(cultural fit|team fit)\s+concern",
                r"(minority|ethnic|race)\s+(candidate|person)",
            ]
        },
        ProtectedCategory.AGE: {
            "terms": [
                "digital native", "old school", "not tech-savvy",
                "overqualified", "underqualified", "energetic", "dynamic",
                "fresh perspective", "set in ways", "legacy system",
            ],
            "patterns": [
                r"(too\s+)?(young|old)\s+(to|for)",
                r"(generation\s+)?(z|y|x|millennial|boomer)",
            ]
        },
        ProtectedCategory.DISABILITY: {
            "terms": [
                "crippled", "retarded", "slow", "lazy", "drug addict",
                "crazy", "mental", "defective", "burden", "liability",
            ],
            "patterns": [
                r"(can't|unable)\s+\w+\s+(due to|because of|with)\s+(disability|condition)",
                r"(special accommodations|special treatment)",
            ]
        },
        ProtectedCategory.VETERAN_STATUS: {
            "terms": [
                "militant", "aggressive", "PTSD", "uncontrollable",
                "loose cannon", "ticking time bomb", "damaged",
            ],
            "patterns": [
                r"(military|armed forces|veteran)\s+(training|background)",
                r"(war|combat)\s+(trauma|stress)",
            ]
        },
        ProtectedCategory.RELIGION: {
            "terms": [
                "religious extremist", "zealot", "fundamentalist",
                "uncivilized", "primitive", "backwards", "un-American",
            ],
            "patterns": [
                r"(faith|religion|belief|prayer)\s+(concern|issue|problem)",
                r"(christian|jewish|muslim|hindu|atheist)\s+(values|practices)",
            ]
        }
    }

    # Stereotype patterns
    STEREOTYPE_PATTERNS: Dict[ProtectedCategory, List[str]] = {
        ProtectedCategory.GENDER: [
            r"women.*emotional",
            r"men.*logical",
            r"female.*weak",
            r"male.*strong",
            r"women.*sensitive",
            r"mothers.*distracted",
            r"fathers.*providers",
        ],
        ProtectedCategory.RACE: [
            r"asian.*math",
            r"asian.*tech",
            r"african.*athletic",
            r"hispanic.*service",
            r"white.*privilege",
        ],
        ProtectedCategory.AGE: [
            r"young.*inexperienced",
            r"old.*slow",
            r"elderly.*forgetful",
            r"young.*ambitious",
            r"generation.*values",
        ],
        ProtectedCategory.DISABILITY: [
            r"disabled.*pity",
            r"blind.*helpless",
            r"deaf.*unable",
        ],
        ProtectedCategory.RELIGION: [
            r"religious.*intolerant",
            r"atheist.*immoral",
        ]
    }

    # Exclusionary language patterns
    EXCLUSIONARY_PATTERNS: Dict[str, List[str]] = {
        "gendered_pronouns": [
            r"he (must|should|will)",
            r"she (must|should|will)",
            r"guys", r"ladies",
        ],
        "ability_assumptions": [
            r"must be able to.*work.*overtime",
            r"(standing|sitting).*8\s+hours",
            r"physical (demands|requirements)",
        ],
        "appearance": [
            r"must look.*professional",
            r"appearance (matters|important)",
            r"(tattoo|piercing|hair).*policy",
        ],
        "socioeconomic": [
            r"graduate of.*university",
            r"extensive experience.*required",
            r"(bachelor|master)\s+degree.*required",
        ]
    }

    def __init__(self) -> None:
        """Initialize bias auditor."""
        self.incidents: List[BiasIncident] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for performance."""
        self.compiled_patterns: Dict[str, Any] = {}

        for category in ProtectedCategory:
            if category in self.BIAS_LEXICON:
                patterns = self.BIAS_LEXICON[category].get("patterns", [])
                self.compiled_patterns[f"{category.value}_patterns"] = [
                    re.compile(p, re.IGNORECASE) for p in patterns
                ]

            if category in self.STEREOTYPE_PATTERNS:
                self.compiled_patterns[f"{category.value}_stereotypes"] = [
                    re.compile(p, re.IGNORECASE)
                    for p in self.STEREOTYPE_PATTERNS[category]
                ]

        for category, patterns in self.EXCLUSIONARY_PATTERNS.items():
            self.compiled_patterns[f"exclusionary_{category}"] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def scan_response(
        self,
        agent_type: str,
        query: str,
        response: str,
    ) -> List[BiasIncident]:
        """Scan agent response for potential bias.

        Args:
            agent_type: Type of agent generating response
            query: Original user query
            response: Agent's response text

        Returns:
            List of BiasIncident objects found

        Example:
            incidents = auditor.scan_response(
                agent_type="compensation",
                query="What salary should I offer this candidate?",
                response="For a woman in this role, $60k is appropriate."
            )
        """
        incidents = []

        # Check for biased language
        language_incidents = self._check_biased_language(response)
        incidents.extend(language_incidents)

        # Check for stereotypes
        stereotype_incidents = self._check_stereotypes(response)
        incidents.extend(stereotype_incidents)

        # Check for exclusionary patterns
        exclusion_incidents = self._check_exclusionary_patterns(response)
        incidents.extend(exclusion_incidents)

        # Enrich incidents with context
        for incident in incidents:
            incident.agent_type = agent_type
            incident.query = query
            incident.response = response
            self.incidents.append(incident)

        if incidents:
            logger.warning(
                f"Detected {len(incidents)} bias incidents in {agent_type} response"
            )

        return incidents

    def check_compensation_equity(
        self,
        data_points: List[Dict[str, Any]],
    ) -> List[BiasIncident]:
        """Check compensation data for equity issues.

        Analyzes compensation patterns to detect systematic bias in pay.

        Args:
            data_points: List of employee data with compensation info.
                        Expected fields: job_title, level, gender, race, age,
                        base_salary, bonus, total_comp

        Returns:
            List of BiasIncident objects detecting equity issues

        Example:
            employees = [
                {"name": "Alice", "job_title": "Engineer", "gender": "F", "salary": 100000},
                {"name": "Bob", "job_title": "Engineer", "gender": "M", "salary": 120000},
            ]
            incidents = auditor.check_compensation_equity(employees)
        """
        incidents = []

        if not data_points:
            return incidents

        # Group by job title and level
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for point in data_points:
            key = f"{point.get('job_title', 'unknown')}_{point.get('level', 'unknown')}"
            if key not in groups:
                groups[key] = []
            groups[key].append(point)

        # Analyze each group for disparities
        for group_key, group in groups.items():
            # Check gender pay gap
            gender_gap = self._check_gender_pay_gap(group)
            incidents.extend(gender_gap)

            # Check race pay gap
            race_gap = self._check_race_pay_gap(group)
            incidents.extend(race_gap)

            # Check age pay gap
            age_gap = self._check_age_pay_gap(group)
            incidents.extend(age_gap)

        for incident in incidents:
            incident.agent_type = "compensation"
            self.incidents.append(incident)

        return incidents

    def generate_audit_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Generate comprehensive bias audit report.

        Args:
            start_date: Report start date (default: 30 days ago)
            end_date: Report end date (default: now)

        Returns:
            Report dictionary with findings and recommendations

        Example:
            report = auditor.generate_audit_report()
            print(f"Total incidents: {report['total_incidents']}")
            print(f"Critical severity: {report['critical_count']}")
        """
        from datetime import timedelta

        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Filter incidents by date range
        filtered = [
            i for i in self.incidents
            if start_date <= i.timestamp <= end_date
        ]

        # Count by category and severity
        category_counts: Dict[str, int] = {}
        severity_counts: Dict[str, int] = {}

        for incident in filtered:
            cat = incident.category.value
            sev = incident.severity.value

            category_counts[cat] = category_counts.get(cat, 0) + 1
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Generate recommendations
        recommendations = self._generate_recommendations(filtered)

        return {
            "report_date": datetime.utcnow().isoformat(),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_incidents": len(filtered),
            "incident_counts": {
                "critical": severity_counts.get("critical", 0),
                "high": severity_counts.get("high", 0),
                "medium": severity_counts.get("medium", 0),
                "low": severity_counts.get("low", 0),
            },
            "category_breakdown": category_counts,
            "findings": self._summarize_findings(filtered),
            "recommendations": recommendations,
            "high_risk_areas": self._identify_high_risk_areas(filtered),
        }

    def get_incidents(
        self,
        severity_filter: Optional[BiasSeverity] = None,
        category_filter: Optional[ProtectedCategory] = None,
    ) -> List[BiasIncident]:
        """Get incidents with optional filtering.

        Args:
            severity_filter: Filter by severity level
            category_filter: Filter by protected category

        Returns:
            List of filtered incidents

        Example:
            critical = auditor.get_incidents(
                severity_filter=BiasSeverity.CRITICAL
            )
        """
        incidents = self.incidents

        if severity_filter:
            incidents = [
                i for i in incidents
                if i.severity == severity_filter
            ]

        if category_filter:
            incidents = [
                i for i in incidents
                if i.category == category_filter
            ]

        return incidents

    def _check_biased_language(self, text: str) -> List[BiasIncident]:
        """Detect biased language in text.

        Args:
            text: Text to analyze

        Returns:
            List of BiasIncident for detected biased language
        """
        incidents = []

        for category in ProtectedCategory:
            if category not in self.BIAS_LEXICON:
                continue

            # Check direct terms
            terms = self.BIAS_LEXICON[category].get("terms", [])
            for term in terms:
                if term.lower() in text.lower():
                    incidents.append(
                        BiasIncident(
                            category=category,
                            severity=BiasSeverity.MEDIUM,
                            description=f"Biased term detected: '{term}'",
                            evidence=term,
                            recommendations=[
                                "Review and rewrite response without biased language",
                                f"Consult EEO guidelines for {category.value} language",
                            ],
                        )
                    )

            # Check regex patterns
            pattern_key = f"{category.value}_patterns"
            if pattern_key in self.compiled_patterns:
                for pattern in self.compiled_patterns[pattern_key]:
                    matches = pattern.findall(text)
                    if matches:
                        incidents.append(
                            BiasIncident(
                                category=category,
                                severity=BiasSeverity.HIGH,
                                description=f"Biased pattern detected in {category.value} category",
                                evidence=str(matches[0]) if matches else "",
                                recommendations=[
                                    "Rewrite to remove category-specific assumptions",
                                    "Use neutral, objective language",
                                ],
                            )
                        )

        return incidents

    def _check_stereotypes(self, text: str) -> List[BiasIncident]:
        """Detect stereotype patterns in text.

        Args:
            text: Text to analyze

        Returns:
            List of BiasIncident for detected stereotypes
        """
        incidents = []

        for category in ProtectedCategory:
            if category not in self.STEREOTYPE_PATTERNS:
                continue

            pattern_key = f"{category.value}_stereotypes"
            if pattern_key in self.compiled_patterns:
                for pattern in self.compiled_patterns[pattern_key]:
                    matches = pattern.findall(text)
                    if matches:
                        incidents.append(
                            BiasIncident(
                                category=category,
                                severity=BiasSeverity.HIGH,
                                description=f"Stereotype detected: {category.value}",
                                evidence=str(matches[0]) if matches else "",
                                recommendations=[
                                    "Avoid generalizations about groups",
                                    "Focus on individual qualifications",
                                    "Use data-driven assessment criteria",
                                ],
                            )
                        )

        return incidents

    def _check_exclusionary_patterns(self, text: str) -> List[BiasIncident]:
        """Detect exclusionary language patterns.

        Args:
            text: Text to analyze

        Returns:
            List of BiasIncident for detected exclusionary patterns
        """
        incidents = []

        for pattern_category, patterns in self.EXCLUSIONARY_PATTERNS.items():
            pattern_key = f"exclusionary_{pattern_category}"
            if pattern_key in self.compiled_patterns:
                for pattern in self.compiled_patterns[pattern_key]:
                    matches = pattern.findall(text)
                    if matches:
                        severity = (
                            BiasSeverity.CRITICAL
                            if "gendered" in pattern_category
                            else BiasSeverity.MEDIUM
                        )
                        incidents.append(
                            BiasIncident(
                                category=ProtectedCategory.GENDER,
                                severity=severity,
                                description=f"Exclusionary language ({pattern_category})",
                                evidence=str(matches[0]) if matches else "",
                                recommendations=[
                                    "Use inclusive language",
                                    "Focus on essential job functions",
                                    "Provide reasonable accommodations where applicable",
                                ],
                            )
                        )

        return incidents

    def _check_gender_pay_gap(
        self,
        group: List[Dict[str, Any]],
    ) -> List[BiasIncident]:
        """Analyze gender pay gap in a peer group.

        Args:
            group: List of employee records in same role/level

        Returns:
            List of BiasIncident if significant gap detected
        """
        incidents = []

        male_salaries = [
            p.get("base_salary", 0) for p in group
            if p.get("gender", "").lower() == "m"
        ]
        female_salaries = [
            p.get("base_salary", 0) for p in group
            if p.get("gender", "").lower() == "f"
        ]

        if male_salaries and female_salaries:
            male_avg = sum(male_salaries) / len(male_salaries)
            female_avg = sum(female_salaries) / len(female_salaries)

            if male_avg > 0:
                gap_pct = ((male_avg - female_avg) / male_avg) * 100

                if gap_pct > 5:  # More than 5% gap
                    severity = (
                        BiasSeverity.CRITICAL if gap_pct > 15
                        else BiasSeverity.HIGH if gap_pct > 10
                        else BiasSeverity.MEDIUM
                    )
                    incidents.append(
                        BiasIncident(
                            category=ProtectedCategory.GENDER,
                            severity=severity,
                            description=f"Gender pay gap detected: {gap_pct:.1f}%",
                            evidence=f"Male avg: ${male_avg:.0f}, Female avg: ${female_avg:.0f}",
                            recommendations=[
                                "Conduct formal pay equity analysis",
                                "Review compensation criteria for bias",
                                "Consider pay adjustments for equity",
                                "Document decision-making rationale",
                            ],
                        )
                    )

        return incidents

    def _check_race_pay_gap(
        self,
        group: List[Dict[str, Any]],
    ) -> List[BiasIncident]:
        """Analyze race pay gap in a peer group.

        Args:
            group: List of employee records in same role/level

        Returns:
            List of BiasIncident if significant gap detected
        """
        incidents = []

        # Group by race
        by_race: Dict[str, List[float]] = {}
        for person in group:
            race = person.get("race", "unknown")
            salary = person.get("base_salary", 0)
            if salary > 0:
                if race not in by_race:
                    by_race[race] = []
                by_race[race].append(salary)

        # Compare minority vs majority
        if "white" in by_race or "majority" in by_race:
            majority_key = "white" if "white" in by_race else "majority"
            majority_avg = sum(by_race[majority_key]) / len(by_race[majority_key])

            for minority_key, salaries in by_race.items():
                if minority_key != majority_key and salaries:
                    minority_avg = sum(salaries) / len(salaries)
                    gap_pct = ((majority_avg - minority_avg) / majority_avg) * 100

                    if gap_pct > 5:
                        severity = (
                            BiasSeverity.CRITICAL if gap_pct > 15
                            else BiasSeverity.HIGH if gap_pct > 10
                            else BiasSeverity.MEDIUM
                        )
                        incidents.append(
                            BiasIncident(
                                category=ProtectedCategory.RACE,
                                severity=severity,
                                description=f"Race-based pay gap: {minority_key} vs {majority_key} ({gap_pct:.1f}%)",
                                evidence=f"{majority_key} avg: ${majority_avg:.0f}, {minority_key} avg: ${minority_avg:.0f}",
                                recommendations=[
                                    "Conduct EEO audit",
                                    "Review promotion patterns",
                                    "Analyze hiring practices",
                                    "Ensure objective evaluation criteria",
                                ],
                            )
                        )

        return incidents

    def _check_age_pay_gap(
        self,
        group: List[Dict[str, Any]],
    ) -> List[BiasIncident]:
        """Analyze age-based pay disparities.

        Args:
            group: List of employee records in same role/level

        Returns:
            List of BiasIncident if significant disparity detected
        """
        incidents = []

        # Group by age ranges
        young = [p.get("base_salary", 0) for p in group if p.get("age", 0) < 40]
        old = [p.get("base_salary", 0) for p in group if p.get("age", 0) >= 40]

        if young and old:
            young_avg = sum(young) / len(young)
            old_avg = sum(old) / len(old)

            # ADEA concerns if younger paid significantly more
            if young_avg > 0 and (old_avg / young_avg) < 0.85:
                incidents.append(
                    BiasIncident(
                        category=ProtectedCategory.AGE,
                        severity=BiasSeverity.HIGH,
                        description="Potential age discrimination in compensation",
                        evidence=f"Younger (< 40) avg: ${young_avg:.0f}, Older (>= 40) avg: ${old_avg:.0f}",
                        recommendations=[
                            "Review ADEA compliance",
                            "Analyze tenure vs compensation correlation",
                            "Ensure objective criteria",
                        ],
                    )
                )

        return incidents

    def _generate_recommendations(
        self,
        incidents: List[BiasIncident],
    ) -> List[str]:
        """Generate overall recommendations from incidents.

        Args:
            incidents: List of bias incidents

        Returns:
            List of recommendations
        """
        recommendations = set()

        severity_counts = {}
        for i in incidents:
            severity_counts[i.severity.value] = severity_counts.get(i.severity.value, 0) + 1

        if severity_counts.get("critical", 0) > 0:
            recommendations.add("URGENT: Escalate critical incidents to Legal/Compliance")
            recommendations.add("URGENT: Implement immediate remediation actions")

        if severity_counts.get("high", 0) > 0:
            recommendations.add("Conduct bias awareness training for all managers")
            recommendations.add("Review and revise HR policies and procedures")
            recommendations.add("Implement bias detection in hiring systems")

        if severity_counts.get("medium", 0) > 0:
            recommendations.add("Establish bias review checklist for HR decisions")
            recommendations.add("Increase diversity in decision-making teams")

        recommendations.add("Document all bias findings and remediation actions")
        recommendations.add("Schedule quarterly bias audits")

        return sorted(list(recommendations))

    def _summarize_findings(
        self,
        incidents: List[BiasIncident],
    ) -> List[str]:
        """Summarize key findings from incidents.

        Args:
            incidents: List of bias incidents

        Returns:
            List of finding summaries
        """
        findings = []

        category_counts: Dict[str, int] = {}
        for incident in incidents:
            cat = incident.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            findings.append(f"{category.title()}: {count} incidents detected")

        critical_count = sum(1 for i in incidents if i.severity == BiasSeverity.CRITICAL)
        if critical_count > 0:
            findings.insert(0, f"CRITICAL: {critical_count} critical incidents requiring immediate action")

        return findings

    def _identify_high_risk_areas(
        self,
        incidents: List[BiasIncident],
    ) -> Dict[str, int]:
        """Identify agent types or processes with highest bias risk.

        Args:
            incidents: List of bias incidents

        Returns:
            Dictionary mapping agent type to incident count
        """
        risk_areas: Dict[str, int] = {}

        for incident in incidents:
            if incident.severity in (BiasSeverity.CRITICAL, BiasSeverity.HIGH):
                agent = incident.agent_type or "unknown"
                risk_areas[agent] = risk_areas.get(agent, 0) + 1

        return dict(sorted(risk_areas.items(), key=lambda x: x[1], reverse=True))


class BiasAuditMiddleware:
    """
    Flask middleware for intercepting and auditing responses for bias.

    Scans outgoing responses before delivery to catch bias before user exposure.
    """

    def __init__(self, app=None, auditor: Optional[BiasAuditor] = None) -> None:
        """Initialize bias audit middleware.

        Args:
            app: Flask application instance
            auditor: BiasAuditor instance (creates new if not provided)
        """
        self.app = app
        self.auditor = auditor or BiasAuditor()

        if app:
            self.init_app(app)

    def init_app(self, app) -> None:
        """Initialize middleware with Flask app.

        Args:
            app: Flask application instance
        """
        self.app = app
        app.after_request(self.check_response)

    def check_response(self, response):
        """Middleware hook to scan response for bias.

        Args:
            response: Flask response object

        Returns:
            Modified response (with bias flags if needed)
        """
        try:
            # Only scan JSON responses
            if "application/json" not in response.content_type:
                return response

            # Extract response text and query from request context if available
            response_text = response.get_data(as_text=True)
            agent_type = self.app.request.args.get("agent_type", "unknown")
            query = self.app.request.args.get("query", "")

            # Scan for bias
            incidents = self.auditor.scan_response(
                agent_type=agent_type,
                query=query,
                response=response_text,
            )

            # Add bias flags to response if critical incidents found
            if any(i.severity == BiasSeverity.CRITICAL for i in incidents):
                response.headers["X-Bias-Alert"] = "CRITICAL"
                logger.error(f"Critical bias detected in {agent_type} response")

        except Exception as e:
            logger.warning(f"Error in bias audit middleware: {e}")

        return response
