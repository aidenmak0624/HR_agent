#!/usr/bin/env python3
"""
Comprehensive chatbot test script for HR platform API v2
Tests 30+ queries across 12 categories against the /api/v2/query endpoint
"""

import requests
import json
import time
from typing import Dict, List, Tuple
from datetime import datetime
import sys

# Configuration
API_URL = "http://localhost:5050/api/v2/query"
OUTPUT_FILE = "/sessions/beautiful-amazing-lamport/mnt/HR_agent/tests/e2e/chatbot_test_results.json"

# Default user context
DEFAULT_USER_CONTEXT = {"user_id": "user_123", "role": "employee", "department": "Engineering"}

# Test categories with test cases
TEST_CATEGORIES = {
    "Greetings": {
        "expected_agent": ["general_assistant"],
        "expected_confidence_min": 0.85,
        "queries": ["Hello", "Hi there", "Hey", "What's up", "Good morning"],
    },
    "Capabilities": {
        "expected_agent": ["general_assistant"],
        "expected_confidence_min": 0.85,
        "queries": [
            "What do you do?",
            "Help me",
            "What can you help with?",
            "Tell me about your capabilities",
            "What are you able to do?",
        ],
    },
    "Identity": {
        "expected_agent": ["general_assistant"],
        "expected_confidence_min": 0.85,
        "queries": ["Who are you?", "What are you?", "Who is this?", "What is your name?"],
    },
    "Farewell": {
        "expected_agent": ["general_assistant"],
        "expected_confidence_min": 0.85,
        "queries": ["Bye", "Goodbye", "Thanks", "Thank you", "See you later"],
    },
    "Leave Queries": {
        "expected_agent": ["leave_agent", "policy_agent"],
        "expected_confidence_min": 0.70,
        "queries": [
            "How many vacation days do I have?",
            "Can I take sick leave?",
            "What is the leave policy?",
            "I want to apply for leave",
            "How much PTO do I have left?",
            "When can I take vacation?",
        ],
    },
    "Benefits Queries": {
        "expected_agent": ["benefits_agent"],
        "expected_confidence_min": 0.70,
        "queries": [
            "Do we have health insurance?",
            "What about 401k?",
            "Do you cover dental?",
            "Tell me about benefits",
            "Health insurance options",
            "Retirement benefits",
        ],
    },
    "Policy Queries": {
        "expected_agent": ["policy_agent"],
        "expected_confidence_min": 0.70,
        "queries": [
            "Can I work remotely?",
            "What are the working hours?",
            "What's the dress code?",
            "Remote work policy",
            "Are pets allowed in office?",
            "Parental leave policy",
        ],
    },
    "Payroll Queries": {
        "expected_agent": ["payroll_agent"],
        "expected_confidence_min": 0.70,
        "queries": [
            "When is payday?",
            "How do I set up direct deposit?",
            "What's my salary?",
            "Can I get a pay stub?",
            "Tax withholding information",
        ],
    },
    "Onboarding Queries": {
        "expected_agent": ["onboarding_agent"],
        "expected_confidence_min": 0.70,
        "queries": [
            "I'm a new employee, what do I do?",
            "What's required for first day?",
            "How do I get onboarded?",
            "New employee checklist",
            "First day orientation",
        ],
    },
    "Document Queries": {
        "expected_agent": ["hr_agent", "document_agent"],
        "expected_confidence_min": 0.70,
        "queries": [
            "Can I get an employment certificate?",
            "I need my offer letter",
            "Can I request my employment records?",
            "How do I get a reference letter?",
        ],
    },
    "Edge Cases": {
        "expected_agent": None,
        "expected_confidence_min": 0.0,
        "queries": [
            "asfghjkl zxcvbnm qwerty",
            "Can I have a query with many many many many many words " * 5,
            "Query with special chars: !@#$%^&*()",
            "123456789 0987654321",
            "SELECT * FROM users DROP TABLE;",
        ],
    },
    "Mixed Queries": {
        "expected_agent": None,
        "expected_confidence_min": 0.50,
        "queries": [
            "I want to take vacation and know about health insurance",
            "What's the leave policy and remote work policy?",
            "Can I apply for leave and also get my pay stub?",
            "Tell me about benefits and onboarding process",
        ],
    },
}


class ChatbotTestRunner:
    def __init__(self):
        self.results = []
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.start_time = datetime.now()

    def run_query(self, query: str, user_context: Dict = None) -> Tuple[Dict, float]:
        """
        Run a single query against the API
        Returns: (response_dict, response_time_ms)
        """
        if user_context is None:
            user_context = DEFAULT_USER_CONTEXT.copy()

        payload = {"query": query, "user_context": user_context}

        start = time.time()
        try:
            response = self.session.post(API_URL, json=payload, timeout=10)
            elapsed_ms = (time.time() - start) * 1000

            if response.status_code == 200:
                return response.json(), elapsed_ms
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "data": {},
                }, elapsed_ms
        except requests.exceptions.Timeout:
            elapsed_ms = (time.time() - start) * 1000
            return {"success": False, "error": "Request timeout", "data": {}}, elapsed_ms
        except requests.exceptions.ConnectionError:
            elapsed_ms = (time.time() - start) * 1000
            return {"success": False, "error": "Connection error", "data": {}}, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            return {"success": False, "error": str(e), "data": {}}, elapsed_ms

    def evaluate_test(
        self,
        category: str,
        query: str,
        response: Dict,
        expected_agents: List[str],
        expected_confidence: float,
    ) -> Dict:
        """Evaluate if a test passed"""
        test_result = {
            "category": category,
            "query": query,
            "success": False,
            "pass": False,
            "reason": "",
            "response": {},
            "response_time_ms": 0,
            "agent_type": None,
            "confidence": None,
        }

        # Check if response is successful
        if not response.get("success", False):
            test_result["success"] = False
            test_result["reason"] = f"API returned error: {response.get('error', 'Unknown error')}"
            return test_result

        test_result["success"] = True

        # Extract data
        data = response.get("data", {})
        answer = data.get("answer", "")
        agent_type = data.get("agent_type", "")
        confidence = data.get("confidence", 0)

        test_result["response"]["answer"] = answer[:200] if answer else ""
        test_result["agent_type"] = agent_type
        test_result["confidence"] = confidence

        # Check pass conditions
        pass_conditions = []

        # Condition 1: Valid answer
        if answer and isinstance(answer, str) and len(answer) > 0:
            pass_conditions.append(True)
        else:
            pass_conditions.append(False)
            test_result["reason"] += "No valid answer returned. "

        # Condition 2: Agent type check (if expectations exist)
        if expected_agents is not None:
            if agent_type in expected_agents:
                pass_conditions.append(True)
            else:
                pass_conditions.append(False)
                test_result["reason"] += f"Expected agent in {expected_agents}, got {agent_type}. "
        else:
            pass_conditions.append(True)

        # Condition 3: Confidence check
        if confidence >= expected_confidence:
            pass_conditions.append(True)
        else:
            pass_conditions.append(False)
            test_result[
                "reason"
            ] += f"Confidence {confidence:.2f} below threshold {expected_confidence:.2f}. "

        test_result["pass"] = all(pass_conditions)
        if not test_result["reason"]:
            test_result["reason"] = "All checks passed"

        return test_result

    def run_all_tests(self):
        """Run all test categories"""
        print("\n" + "=" * 80)
        print("CHATBOT API E2E TEST RUNNER")
        print("=" * 80)
        print(f"Testing against: {API_URL}")
        print(f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total test queries: {sum(len(cat['queries']) for cat in TEST_CATEGORIES.values())}")
        print("=" * 80 + "\n")

        for category_name, category_config in TEST_CATEGORIES.items():
            print(f"\n[{category_name}]")
            print("-" * 80)

            expected_agents = category_config["expected_agent"]
            expected_confidence = category_config["expected_confidence_min"]

            for query in category_config["queries"]:
                # Run the query
                response, response_time = self.run_query(query)

                # Evaluate the test
                test_result = self.evaluate_test(
                    category_name, query, response, expected_agents, expected_confidence
                )
                test_result["response_time_ms"] = response_time

                # Store result
                self.results.append(test_result)

                # Print result
                status = "PASS" if test_result["pass"] else "FAIL"
                status_symbol = "✓" if test_result["pass"] else "✗"

                print(f"{status_symbol} {status}: {query[:60]}")

                confidence_str = (
                    f"{test_result['confidence']:.2f}"
                    if test_result["confidence"] is not None
                    else "N/A"
                )
                agent_str = test_result["agent_type"] if test_result["agent_type"] else "N/A"

                print(
                    f"  Agent: {agent_str} | Confidence: {confidence_str} | Time: {response_time:.0f}ms"
                )

                if test_result["response"].get("answer"):
                    answer_preview = test_result["response"]["answer"][:80].replace("\n", " ")
                    print(f"  Answer: {answer_preview}...")

                if not test_result["pass"]:
                    print(f"  Reason: {test_result['reason']}")
                print()

        return self.results

    def print_summary_table(self):
        """Print a summary table of all results"""
        print("\n" + "=" * 120)
        print("TEST RESULTS SUMMARY TABLE")
        print("=" * 120)
        print(
            f"{'#':<4} {'Category':<20} {'Query':<35} {'Status':<6} {'Agent':<18} {'Conf':<6} {'Time(ms)':<8}"
        )
        print("-" * 120)

        for i, result in enumerate(self.results, 1):
            query_short = result["query"][:35].ljust(35)
            agent = result["agent_type"] if result["agent_type"] else "N/A"

            if result["confidence"] is not None:
                confidence = f"{result['confidence']:.2f}"
            else:
                confidence = "N/A"

            status = "PASS" if result["pass"] else "FAIL"
            time_ms = f"{result['response_time_ms']:.0f}"

            print(
                f"{i:<4} {result['category']:<20} {query_short} {status:<6} {agent:<18} {confidence:<6} {time_ms:<8}"
            )

        print("-" * 120)

        # Statistics
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["pass"])
        failed_tests = total_tests - passed_tests
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        avg_time = (
            sum(r["response_time_ms"] for r in self.results) / total_tests if total_tests > 0 else 0
        )

        print(f"\nTotal Tests: {total_tests}")
        print(f"Passed: {passed_tests} ({pass_rate:.1f}%)")
        print(f"Failed: {failed_tests} ({100-pass_rate:.1f}%)")
        print(f"Average Response Time: {avg_time:.0f}ms")
        print("=" * 120 + "\n")

        # Results by category
        print("\nRESULTS BY CATEGORY")
        print("-" * 80)
        categories = {}
        for result in self.results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = {"passed": 0, "total": 0}
            categories[cat]["total"] += 1
            if result["pass"]:
                categories[cat]["passed"] += 1

        for cat in sorted(categories.keys()):
            stats = categories[cat]
            rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            print(f"{cat:<30} {stats['passed']}/{stats['total']} passed ({rate:.1f}%)")

        print("\n")

    def save_results(self):
        """Save results to JSON file"""
        output = {
            "test_run_info": {
                "timestamp": datetime.now().isoformat(),
                "api_url": API_URL,
                "total_tests": len(self.results),
                "passed_tests": sum(1 for r in self.results if r["pass"]),
                "failed_tests": sum(1 for r in self.results if not r["pass"]),
                "pass_rate": sum(1 for r in self.results if r["pass"]) / len(self.results) * 100
                if self.results
                else 0,
            },
            "results": self.results,
        }

        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2)

        print(f"Results saved to: {OUTPUT_FILE}")
        return output


def main():
    """Main entry point"""
    try:
        runner = ChatbotTestRunner()

        # Check if API is reachable
        try:
            response = runner.session.get(API_URL.rsplit("/", 1)[0], timeout=5)
        except:
            print(f"ERROR: Cannot reach API at {API_URL}")
            print("Please ensure the Flask HR platform server is running on localhost:5050")
            sys.exit(1)

        # Run all tests
        runner.run_all_tests()

        # Print summary
        runner.print_summary_table()

        # Save results
        runner.save_results()

        print("\nTest execution completed successfully!")

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
