"""
PLAT-001: No-Code Workflow Builder
Workflow builder platform for creating, managing, and executing HR workflows.

Supports visual workflow design with nodes, edges, conditions, and state tracking.
Includes built-in templates for common HR processes.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    """Workflow node types."""
    START = "start"
    END = "end"
    APPROVAL = "approval"
    CONDITION = "condition"
    ACTION = "action"
    NOTIFICATION = "notification"
    DELAY = "delay"
    PARALLEL_GATEWAY = "parallel_gateway"


@dataclass
class WorkflowNode:
    """Workflow node configuration."""

    node_id: str = field(default_factory=lambda: str(uuid4()))
    node_type: NodeType = NodeType.ACTION
    title: str = ""
    description: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, str] = field(default_factory=dict)
    outputs: List[str] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "title": self.title,
            "description": self.description,
            "config": self.config,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "position": {"x": self.x, "y": self.y},
        }


@dataclass
class WorkflowEdge:
    """Workflow edge (connection) between nodes."""

    edge_id: str = field(default_factory=lambda: str(uuid4()))
    source_node_id: str = ""
    target_node_id: str = ""
    condition: Optional[str] = None
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "edge_id": self.edge_id,
            "source": self.source_node_id,
            "target": self.target_node_id,
            "condition": self.condition,
            "label": self.label,
        }


@dataclass
class WorkflowDefinition:
    """Complete workflow definition."""

    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    nodes: Dict[str, WorkflowNode] = field(default_factory=dict)
    edges: Dict[str, WorkflowEdge] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "created_at": self.created_at.isoformat(),
            "version": self.version,
            "active": self.active,
        }


class WorkflowBuilder:
    """No-code workflow builder for HR processes."""

    def __init__(self):
        """Initialize workflow builder."""
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.templates: Dict[str, WorkflowDefinition] = {}
        self._initialize_templates()

    def _initialize_templates(self) -> None:
        """Initialize built-in workflow templates."""
        # Leave approval workflow template
        leave_workflow = self._create_leave_approval_template()
        self.templates["leave_approval"] = leave_workflow

        # Onboarding workflow template
        onboarding_workflow = self._create_onboarding_template()
        self.templates["onboarding"] = onboarding_workflow

        # Performance review workflow template
        perf_workflow = self._create_performance_review_template()
        self.templates["performance_review"] = perf_workflow

        logger.info(f"Initialized {len(self.templates)} workflow templates")

    def _create_leave_approval_template(self) -> WorkflowDefinition:
        """Create leave approval workflow template."""
        workflow = WorkflowDefinition(
            name="Leave Request Approval",
            description="Standard workflow for leave request submission and approval"
        )

        # Nodes
        start = WorkflowNode(node_type=NodeType.START, title="Start")
        validate = WorkflowNode(
            node_type=NodeType.ACTION,
            title="Validate Leave Request",
            config={"action": "validate_leave", "agent": "leave_request"}
        )
        manager_approval = WorkflowNode(
            node_type=NodeType.APPROVAL,
            title="Manager Approval",
            config={"role": "manager", "timeout_hours": 48}
        )
        hr_approval = WorkflowNode(
            node_type=NodeType.APPROVAL,
            title="HR Approval",
            config={"role": "hr_generalist", "timeout_hours": 24}
        )
        notify = WorkflowNode(
            node_type=NodeType.NOTIFICATION,
            title="Notify Employee",
            config={"message_type": "leave_approved"}
        )
        end = WorkflowNode(node_type=NodeType.END, title="Complete")

        workflow.nodes = {
            start.node_id: start,
            validate.node_id: validate,
            manager_approval.node_id: manager_approval,
            hr_approval.node_id: hr_approval,
            notify.node_id: notify,
            end.node_id: end,
        }

        # Edges
        edges = [
            WorkflowEdge(start.node_id, validate.node_id, label="Start"),
            WorkflowEdge(validate.node_id, manager_approval.node_id, label="Valid"),
            WorkflowEdge(manager_approval.node_id, hr_approval.node_id, label="Approved"),
            WorkflowEdge(hr_approval.node_id, notify.node_id, label="Approved"),
            WorkflowEdge(notify.node_id, end.node_id, label="Done"),
        ]

        workflow.edges = {e.edge_id: e for e in edges}
        return workflow

    def _create_onboarding_template(self) -> WorkflowDefinition:
        """Create employee onboarding workflow template."""
        workflow = WorkflowDefinition(
            name="Employee Onboarding",
            description="Complete onboarding process for new employees"
        )

        start = WorkflowNode(node_type=NodeType.START, title="Start")
        collect_info = WorkflowNode(
            node_type=NodeType.ACTION,
            title="Collect Employee Info",
            config={"agent": "employee_info"}
        )
        it_setup = WorkflowNode(
            node_type=NodeType.ACTION,
            title="IT Setup",
            config={"action": "provision_account"}
        )
        benefits = WorkflowNode(
            node_type=NodeType.ACTION,
            title="Benefits Enrollment",
            config={"agent": "benefits"}
        )
        training = WorkflowNode(
            node_type=NodeType.ACTION,
            title="Assign Training",
            config={"action": "create_training_plan"}
        )
        welcome = WorkflowNode(
            node_type=NodeType.NOTIFICATION,
            title="Send Welcome Email"
        )
        end = WorkflowNode(node_type=NodeType.END, title="Onboarding Complete")

        workflow.nodes = {
            start.node_id: start,
            collect_info.node_id: collect_info,
            it_setup.node_id: it_setup,
            benefits.node_id: benefits,
            training.node_id: training,
            welcome.node_id: welcome,
            end.node_id: end,
        }

        edges = [
            WorkflowEdge(start.node_id, collect_info.node_id),
            WorkflowEdge(collect_info.node_id, it_setup.node_id),
            WorkflowEdge(it_setup.node_id, benefits.node_id),
            WorkflowEdge(benefits.node_id, training.node_id),
            WorkflowEdge(training.node_id, welcome.node_id),
            WorkflowEdge(welcome.node_id, end.node_id),
        ]

        workflow.edges = {e.edge_id: e for e in edges}
        return workflow

    def _create_performance_review_template(self) -> WorkflowDefinition:
        """Create performance review workflow template."""
        workflow = WorkflowDefinition(
            name="Performance Review Cycle",
            description="Annual performance review process"
        )

        start = WorkflowNode(node_type=NodeType.START, title="Start")
        notify_managers = WorkflowNode(
            node_type=NodeType.NOTIFICATION,
            title="Notify Managers"
        )
        manager_review = WorkflowNode(
            node_type=NodeType.ACTION,
            title="Manager Review",
            config={"action": "create_review"}
        )
        self_review = WorkflowNode(
            node_type=NodeType.ACTION,
            title="Employee Self-Review"
        )
        hr_review = WorkflowNode(
            node_type=NodeType.APPROVAL,
            title="HR Review",
            config={"role": "hr_generalist"}
        )
        archive = WorkflowNode(
            node_type=NodeType.ACTION,
            title="Archive Reviews"
        )
        end = WorkflowNode(node_type=NodeType.END, title="Complete")

        workflow.nodes = {
            start.node_id: start,
            notify_managers.node_id: notify_managers,
            manager_review.node_id: manager_review,
            self_review.node_id: self_review,
            hr_review.node_id: hr_review,
            archive.node_id: archive,
            end.node_id: end,
        }

        edges = [
            WorkflowEdge(start.node_id, notify_managers.node_id),
            WorkflowEdge(notify_managers.node_id, manager_review.node_id),
            WorkflowEdge(manager_review.node_id, self_review.node_id),
            WorkflowEdge(self_review.node_id, hr_review.node_id),
            WorkflowEdge(hr_review.node_id, archive.node_id),
            WorkflowEdge(archive.node_id, end.node_id),
        ]

        workflow.edges = {e.edge_id: e for e in edges}
        return workflow

    def create_workflow(self, name: str, description: str = "") -> str:
        """Create new workflow."""
        workflow = WorkflowDefinition(name=name, description=description)
        self.workflows[workflow.workflow_id] = workflow
        logger.info(f"Created workflow: {workflow.workflow_id}")
        return workflow.workflow_id

    def create_workflow_from_template(self, template_name: str) -> str:
        """Create workflow from template."""
        if template_name not in self.templates:
            raise ValueError(f"Template not found: {template_name}")

        template = self.templates[template_name]
        workflow = WorkflowDefinition(
            name=f"{template.name} (Copy)",
            description=template.description
        )

        # Deep copy nodes and edges
        workflow.nodes = {
            k: WorkflowNode(
                node_id=str(uuid4()),
                node_type=v.node_type,
                title=v.title,
                description=v.description,
                config=v.config.copy(),
                inputs=v.inputs.copy(),
                outputs=v.outputs.copy(),
            )
            for k, v in template.nodes.items()
        }

        self.workflows[workflow.workflow_id] = workflow
        logger.info(f"Created workflow from template: {workflow.workflow_id}")
        return workflow.workflow_id

    def add_node(
        self,
        workflow_id: str,
        node_type: NodeType,
        title: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add node to workflow."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        node = WorkflowNode(
            node_type=node_type,
            title=title,
            config=config or {}
        )

        workflow.nodes[node.node_id] = node
        workflow.updated_at = datetime.utcnow()
        logger.info(f"Added node {node.node_id} to workflow {workflow_id}")
        return node.node_id

    def add_edge(
        self,
        workflow_id: str,
        source_node_id: str,
        target_node_id: str,
        condition: Optional[str] = None,
    ) -> str:
        """Add edge between nodes."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        edge = WorkflowEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            condition=condition
        )

        workflow.edges[edge.edge_id] = edge
        workflow.updated_at = datetime.utcnow()
        logger.info(f"Added edge {edge.edge_id} to workflow {workflow_id}")
        return edge.edge_id

    def remove_node(self, workflow_id: str, node_id: str) -> bool:
        """Remove node from workflow."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        if node_id not in workflow.nodes:
            raise ValueError(f"Node not found: {node_id}")

        # Remove node and related edges
        del workflow.nodes[node_id]
        related_edges = [
            e for e in workflow.edges.values()
            if e.source_node_id == node_id or e.target_node_id == node_id
        ]
        for edge in related_edges:
            del workflow.edges[edge.edge_id]

        workflow.updated_at = datetime.utcnow()
        logger.info(f"Removed node {node_id} from workflow {workflow_id}")
        return True

    def remove_edge(self, workflow_id: str, edge_id: str) -> bool:
        """Remove edge from workflow."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        if edge_id not in workflow.edges:
            raise ValueError(f"Edge not found: {edge_id}")

        del workflow.edges[edge_id]
        workflow.updated_at = datetime.utcnow()
        logger.info(f"Removed edge {edge_id} from workflow {workflow_id}")
        return True

    def validate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Validate workflow connectivity and structure."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        errors = []
        warnings = []

        # Check for start node
        start_nodes = [n for n in workflow.nodes.values() if n.node_type == NodeType.START]
        if len(start_nodes) != 1:
            errors.append("Must have exactly one START node")

        # Check for end node
        end_nodes = [n for n in workflow.nodes.values() if n.node_type == NodeType.END]
        if len(end_nodes) != 1:
            errors.append("Must have exactly one END node")

        # Check for orphaned nodes
        connected_nodes = set()
        for edge in workflow.edges.values():
            connected_nodes.add(edge.source_node_id)
            connected_nodes.add(edge.target_node_id)

        for node_id in workflow.nodes:
            if node_id not in connected_nodes and workflow.nodes[node_id].node_type != NodeType.START:
                warnings.append(f"Node {node_id} is not connected")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def execute_workflow(self, workflow_id: str, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow (simulated)."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        # Validate before execution
        validation = self.validate_workflow(workflow_id)
        if not validation["valid"]:
            raise ValueError(f"Workflow validation failed: {validation['errors']}")

        state = initial_state.copy()
        state["_start_time"] = datetime.utcnow().isoformat()
        state["_execution_log"] = []

        # Find start node
        start_nodes = [n for n in workflow.nodes.values() if n.node_type == NodeType.START]
        if not start_nodes:
            raise ValueError("No start node found")

        current_node_id = start_nodes[0].node_id
        visited = set()
        max_steps = 100

        steps = 0
        while steps < max_steps and current_node_id:
            if current_node_id in visited:
                state["_execution_log"].append(f"Cycle detected at {current_node_id}")
                break

            visited.add(current_node_id)
            node = workflow.nodes.get(current_node_id)

            if not node:
                break

            state["_execution_log"].append(f"Executing {node.node_type.value}: {node.title}")

            if node.node_type == NodeType.END:
                break

            # Find next node
            outgoing_edges = [e for e in workflow.edges.values() if e.source_node_id == current_node_id]
            if outgoing_edges:
                current_node_id = outgoing_edges[0].target_node_id
            else:
                break

            steps += 1

        state["_end_time"] = datetime.utcnow().isoformat()
        state["_steps_executed"] = steps
        return state

    def serialize(self, workflow_id: str) -> str:
        """Serialize workflow to JSON."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        return json.dumps(workflow.to_dict(), indent=2)

    def deserialize(self, json_str: str) -> str:
        """Deserialize workflow from JSON."""
        data = json.loads(json_str)
        workflow = WorkflowDefinition(
            workflow_id=data.get("workflow_id"),
            name=data.get("name"),
            description=data.get("description"),
        )

        # Reconstruct nodes
        for node_data in data.get("nodes", []):
            node = WorkflowNode(
                node_id=node_data["node_id"],
                node_type=NodeType(node_data["node_type"]),
                title=node_data["title"],
                config=node_data.get("config", {}),
            )
            workflow.nodes[node.node_id] = node

        # Reconstruct edges
        for edge_data in data.get("edges", []):
            edge = WorkflowEdge(
                edge_id=edge_data["edge_id"],
                source_node_id=edge_data["source"],
                target_node_id=edge_data["target"],
                condition=edge_data.get("condition"),
            )
            workflow.edges[edge.edge_id] = edge

        self.workflows[workflow.workflow_id] = workflow
        logger.info(f"Deserialized workflow: {workflow.workflow_id}")
        return workflow.workflow_id

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Get workflow by ID."""
        return self.workflows.get(workflow_id)

    def list_workflows(self) -> List[WorkflowDefinition]:
        """List all workflows."""
        return list(self.workflows.values())

    def list_templates(self) -> List[str]:
        """List available templates."""
        return list(self.templates.keys())
