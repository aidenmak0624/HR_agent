"""Sample data seeding script for HR platform development and demo.

This script creates realistic sample data for testing and demonstration:
- 10 employees across 4 departments
- Leave balances and requests
- Workflow examples
- Notifications
- Policy documents for RAG ingestion
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import models if available
try:
    from src.repositories.models import (
        Employee, LeaveBalance, LeaveRequest, Workflow,
        WorkflowStep, Notification, PolicyDocument
    )
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine
    print("Successfully imported models")
except ImportError as e:
    print(f"Note: Could not import models - {e}")
    print("Creating sample data structure instead")


class SampleDataSeeder:
    """Generate sample data for development and testing."""

    def __init__(self):
        """Initialize seeder."""
        self.stats = {
            'employees': 0,
            'leave_balances': 0,
            'leave_requests': 0,
            'workflows': 0,
            'notifications': 0,
            'policy_documents': 0,
        }

    def create_sample_employees(self) -> Dict[str, Any]:
        """Create 10 sample employees across 4 departments."""
        employees = [
            {
                'id': 'EMP-001',
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@company.com',
                'department': 'Engineering',
                'role': 'Senior Software Engineer',
                'manager_id': 'MGR-001',
                'hire_date': (datetime.utcnow() - timedelta(days=1095)).isoformat(),
                'status': 'active',
            },
            {
                'id': 'EMP-002',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'email': 'jane.smith@company.com',
                'department': 'Engineering',
                'role': 'Software Engineer',
                'manager_id': 'MGR-001',
                'hire_date': (datetime.utcnow() - timedelta(days=730)).isoformat(),
                'status': 'active',
            },
            {
                'id': 'EMP-003',
                'first_name': 'Alice',
                'last_name': 'Johnson',
                'email': 'alice.johnson@company.com',
                'department': 'Product',
                'role': 'Product Manager',
                'manager_id': 'MGR-002',
                'hire_date': (datetime.utcnow() - timedelta(days=365)).isoformat(),
                'status': 'active',
            },
            {
                'id': 'EMP-004',
                'first_name': 'Bob',
                'last_name': 'Wilson',
                'email': 'bob.wilson@company.com',
                'department': 'Sales',
                'role': 'Sales Executive',
                'manager_id': 'MGR-003',
                'hire_date': (datetime.utcnow() - timedelta(days=540)).isoformat(),
                'status': 'active',
            },
            {
                'id': 'EMP-005',
                'first_name': 'Carol',
                'last_name': 'Martinez',
                'email': 'carol.martinez@company.com',
                'department': 'Human Resources',
                'role': 'HR Specialist',
                'manager_id': 'MGR-004',
                'hire_date': (datetime.utcnow() - timedelta(days=450)).isoformat(),
                'status': 'active',
            },
            {
                'id': 'EMP-006',
                'first_name': 'David',
                'last_name': 'Brown',
                'email': 'david.brown@company.com',
                'department': 'Engineering',
                'role': 'DevOps Engineer',
                'manager_id': 'MGR-001',
                'hire_date': (datetime.utcnow() - timedelta(days=600)).isoformat(),
                'status': 'active',
            },
            {
                'id': 'EMP-007',
                'first_name': 'Emma',
                'last_name': 'Davis',
                'email': 'emma.davis@company.com',
                'department': 'Product',
                'role': 'UX Designer',
                'manager_id': 'MGR-002',
                'hire_date': (datetime.utcnow() - timedelta(days=380)).isoformat(),
                'status': 'active',
            },
            {
                'id': 'EMP-008',
                'first_name': 'Frank',
                'last_name': 'Miller',
                'email': 'frank.miller@company.com',
                'department': 'Sales',
                'role': 'Account Executive',
                'manager_id': 'MGR-003',
                'hire_date': (datetime.utcnow() - timedelta(days=270)).isoformat(),
                'status': 'active',
            },
            {
                'id': 'EMP-009',
                'first_name': 'Grace',
                'last_name': 'Lee',
                'email': 'grace.lee@company.com',
                'department': 'Human Resources',
                'role': 'Recruiter',
                'manager_id': 'MGR-004',
                'hire_date': (datetime.utcnow() - timedelta(days=180)).isoformat(),
                'status': 'active',
            },
            {
                'id': 'EMP-010',
                'first_name': 'Henry',
                'last_name': 'Taylor',
                'email': 'henry.taylor@company.com',
                'department': 'Engineering',
                'role': 'QA Engineer',
                'manager_id': 'MGR-001',
                'hire_date': (datetime.utcnow() - timedelta(days=120)).isoformat(),
                'status': 'active',
            },
        ]

        self.stats['employees'] = len(employees)
        return {emp['id']: emp for emp in employees}

    def create_leave_balances(self, employees: Dict[str, Any]) -> Dict[str, Any]:
        """Create leave balances for all employees."""
        leave_balances = {}

        for emp_id in employees:
            leave_balances[f'LB-{emp_id}'] = {
                'employee_id': emp_id,
                'leave_type': 'Annual',
                'total_entitlement': 20,
                'taken': 5,
                'balance': 15,
                'year': datetime.utcnow().year,
            }

        self.stats['leave_balances'] = len(leave_balances)
        return leave_balances

    def create_leave_requests(self) -> Dict[str, Any]:
        """Create 3 sample leave requests in different states."""
        leave_requests = {
            'LR-001': {
                'employee_id': 'EMP-001',
                'leave_type': 'Annual',
                'start_date': (datetime.utcnow() + timedelta(days=10)).isoformat(),
                'end_date': (datetime.utcnow() + timedelta(days=14)).isoformat(),
                'duration_days': 5,
                'reason': 'Vacation',
                'status': 'approved',
                'approver_id': 'MGR-001',
                'approved_at': datetime.utcnow().isoformat(),
            },
            'LR-002': {
                'employee_id': 'EMP-003',
                'leave_type': 'Sick Leave',
                'start_date': (datetime.utcnow() + timedelta(days=1)).isoformat(),
                'end_date': (datetime.utcnow() + timedelta(days=2)).isoformat(),
                'duration_days': 2,
                'reason': 'Medical appointment',
                'status': 'pending',
                'approver_id': 'MGR-002',
            },
            'LR-003': {
                'employee_id': 'EMP-005',
                'leave_type': 'Personal',
                'start_date': (datetime.utcnow() - timedelta(days=15)).isoformat(),
                'end_date': (datetime.utcnow() - timedelta(days=13)).isoformat(),
                'duration_days': 3,
                'reason': 'Family matter',
                'status': 'rejected',
                'approver_id': 'MGR-004',
                'rejected_at': (datetime.utcnow() - timedelta(days=14)).isoformat(),
                'rejection_reason': 'Insufficient notice',
            },
        }

        self.stats['leave_requests'] = len(leave_requests)
        return leave_requests

    def create_workflows(self) -> Dict[str, Any]:
        """Create 2 sample workflows."""
        workflows = {
            'WF-001': {
                'workflow_id': 'WF-001',
                'entity_type': 'leave_request',
                'entity_id': 'LR-002',
                'created_by': 'EMP-003',
                'status': 'pending',
                'created_at': datetime.utcnow().isoformat(),
                'steps': [
                    {
                        'step_id': 1,
                        'approver_role': 'manager',
                        'approver_id': 'MGR-002',
                        'status': 'pending',
                        'order': 1,
                    }
                ],
            },
            'WF-002': {
                'workflow_id': 'WF-002',
                'entity_type': 'compensation_change',
                'entity_id': 'COMP-001',
                'created_by': 'MGR-001',
                'status': 'approved',
                'created_at': (datetime.utcnow() - timedelta(days=7)).isoformat(),
                'completed_at': datetime.utcnow().isoformat(),
                'steps': [
                    {
                        'step_id': 1,
                        'approver_role': 'manager',
                        'approver_id': 'MGR-001',
                        'status': 'approved',
                        'approved_at': (datetime.utcnow() - timedelta(days=5)).isoformat(),
                        'order': 1,
                    },
                    {
                        'step_id': 2,
                        'approver_role': 'hr_admin',
                        'approver_id': 'MGR-004',
                        'status': 'approved',
                        'approved_at': (datetime.utcnow() - timedelta(days=3)).isoformat(),
                        'order': 2,
                    },
                ],
            },
        }

        self.stats['workflows'] = len(workflows)
        return workflows

    def create_notifications(self) -> Dict[str, Any]:
        """Create 5 sample notifications."""
        notifications = {
            'NOTIF-001': {
                'recipient_id': 'EMP-001',
                'type': 'leave_approved',
                'title': 'Leave Request Approved',
                'message': 'Your leave request for 2024-02-15 to 2024-02-19 has been approved.',
                'read': True,
                'created_at': (datetime.utcnow() - timedelta(days=5)).isoformat(),
            },
            'NOTIF-002': {
                'recipient_id': 'EMP-003',
                'type': 'leave_pending_approval',
                'title': 'Leave Request Awaiting Approval',
                'message': 'Your leave request is pending approval from your manager.',
                'read': False,
                'created_at': (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            },
            'NOTIF-003': {
                'recipient_id': 'MGR-002',
                'type': 'action_required',
                'title': 'Approval Required',
                'message': 'EMP-003 has submitted a leave request requiring your approval.',
                'read': False,
                'created_at': (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            },
            'NOTIF-004': {
                'recipient_id': 'EMP-005',
                'type': 'leave_rejected',
                'title': 'Leave Request Denied',
                'message': 'Your leave request for 2024-01-25 has been rejected due to insufficient notice.',
                'read': True,
                'created_at': (datetime.utcnow() - timedelta(days=14)).isoformat(),
            },
            'NOTIF-005': {
                'recipient_id': 'EMP-010',
                'type': 'system_announcement',
                'title': 'Policy Update',
                'message': 'HR policies have been updated. Please review the new guidelines.',
                'read': False,
                'created_at': (datetime.utcnow() - timedelta(days=1)).isoformat(),
            },
        }

        self.stats['notifications'] = len(notifications)
        return notifications

    def create_policy_documents(self) -> Dict[str, Any]:
        """Create sample HR policy documents for RAG ingestion."""
        policies = {
            'POL-001': {
                'policy_id': 'POL-001',
                'title': 'Annual Leave Policy',
                'content': '''
                Annual Leave Policy - 2024

                1. Entitlement
                - All full-time employees are entitled to 20 days of annual leave per calendar year
                - Part-time employees receive pro-rata leave based on hours worked

                2. Accrual
                - Leave accrues monthly at a rate of 1.67 days per month
                - Leave balance resets on January 1st each year

                3. Request Process
                - Submit leave requests at least 2 weeks in advance
                - Manager approval is required before leave is confirmed
                - Emergency leave requires notification within 24 hours

                4. Carryover
                - Maximum 5 days can be carried over to the next calendar year
                - Carryover leave must be taken within Q1 of the following year

                5. Exceptions
                - Public holidays do not count towards annual leave entitlement
                - Sick leave and personal leave are managed separately
                ''',
                'category': 'leave',
                'created_at': (datetime.utcnow() - timedelta(days=365)).isoformat(),
                'version': '1.0',
            },
            'POL-002': {
                'policy_id': 'POL-002',
                'title': 'Remote Work Policy',
                'content': '''
                Remote Work Policy

                1. Eligibility
                - All positions are eligible for remote work arrangements
                - Manager approval required based on role requirements

                2. Frequency
                - Employees may work remotely up to 3 days per week
                - At least 2 days per week should be spent in the office for collaboration

                3. Equipment
                - Company provides laptop and necessary equipment
                - Internet stipend provided for home office setup

                4. Communication
                - Employees must be reachable during business hours
                - Participation in all team meetings is required

                5. Home Office Setup
                - Employees are responsible for maintaining a safe work environment
                - Ergonomic assessment available upon request
                ''',
                'category': 'work_arrangements',
                'created_at': (datetime.utcnow() - timedelta(days=180)).isoformat(),
                'version': '2.1',
            },
            'POL-003': {
                'policy_id': 'POL-003',
                'title': 'Compensation and Benefits',
                'content': '''
                Compensation and Benefits Policy

                1. Salary Reviews
                - Annual salary reviews conducted in Q1
                - Merit increases based on performance ratings
                - Market rate adjustments considered annually

                2. Benefits Package
                - Health insurance (medical, dental, vision)
                - Life insurance (2x annual salary)
                - 401(k) with 4% company match
                - Professional development budget: $1,500/year

                3. Bonus Program
                - Annual performance bonus (target: 10-15% of salary)
                - Based on individual and company performance
                - Paid in December

                4. Equity
                - Stock options for eligible employees
                - Vesting schedule: 4-year cliff with 1-year cliff

                5. Time Off Benefits
                - 20 days annual leave
                - 10 public holidays
                - Sick leave: 5 days/year
                - Parental leave: 12 weeks
                ''',
                'category': 'compensation',
                'created_at': (datetime.utcnow() - timedelta(days=90)).isoformat(),
                'version': '1.5',
            },
        }

        self.stats['policy_documents'] = len(policies)
        return policies

    def print_summary(self):
        """Print a summary of created data."""
        print("\n" + "=" * 60)
        print("SAMPLE DATA CREATION SUMMARY")
        print("=" * 60)
        print(f"Employees Created:        {self.stats['employees']}")
        print(f"Leave Balances Created:   {self.stats['leave_balances']}")
        print(f"Leave Requests Created:   {self.stats['leave_requests']}")
        print(f"Workflows Created:        {self.stats['workflows']}")
        print(f"Notifications Created:    {self.stats['notifications']}")
        print(f"Policy Documents Created: {self.stats['policy_documents']}")
        print("=" * 60)
        print("\nSample data ready for development and testing!")
        print("=" * 60 + "\n")

    def run(self):
        """Generate all sample data."""
        print("\nGenerating sample data...\n")

        # Create all data
        employees = self.create_sample_employees()
        leave_balances = self.create_leave_balances(employees)
        leave_requests = self.create_leave_requests()
        workflows = self.create_workflows()
        notifications = self.create_notifications()
        policies = self.create_policy_documents()

        # Print summary
        self.print_summary()

        return {
            'employees': employees,
            'leave_balances': leave_balances,
            'leave_requests': leave_requests,
            'workflows': workflows,
            'notifications': notifications,
            'policies': policies,
        }


def main():
    """Main entry point."""
    seeder = SampleDataSeeder()
    data = seeder.run()

    # Save sample data to JSON for reference
    import json
    output_file = os.path.join(
        os.path.dirname(__file__),
        '..',
        'data',
        'sample_data.json'
    )

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Convert datetime objects to strings for JSON serialization
    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2, default=json_serializer)

    print(f"Sample data saved to: {output_file}")


if __name__ == '__main__':
    main()
