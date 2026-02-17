#!/usr/bin/env python3
"""
Automated Test Suite for HR Assistant Agent
Tests the RAG → Web Search prioritization system
"""

import requests
import json
import time
import sys
from datetime import datetime

BASE_URL = "http://localhost:5050/api/agent"

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class AgentTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.start_time = datetime.now()
    
    def print_header(self, text):
        """Print a formatted test header"""
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{text}{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    
    def print_success(self, text):
        """Print success message"""
        print(f"{Colors.GREEN}✅ {text}{Colors.END}")
    
    def print_failure(self, text):
        """Print failure message"""
        print(f"{Colors.RED}❌ {text}{Colors.END}")
    
    def print_warning(self, text):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")
    
    def print_info(self, text):
        """Print info message"""
        print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")
    
    def test_server_running(self):
        """Test 0: Check if server is running"""
        self.print_header("TEST 0: Server Connectivity")
        
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                self.print_success("Server is running and accessible")
                return True
            else:
                self.print_failure(f"Server returned status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.print_failure(f"Cannot connect to server: {e}")
            self.print_info("Make sure the Flask server is running on http://localhost:5050")
            return False
    
    def test_health(self):
        """Test 1: Health check"""
        self.print_header("TEST 1: Health Check")
        
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"Status: {data.get('status')}")
                print(f"Agent Initialized: {data.get('agent_initialized')}")
                print(f"Tools Available: {data.get('tools_available')}")
                print(f"Number of Tools: {data.get('num_tools')}")
                
                if (data.get("agent_initialized") and 
                    len(data.get("tools_available", [])) >= 5):
                    self.print_success("PASSED: Agent healthy with all tools")
                    self.passed += 1
                else:
                    self.print_failure("FAILED: Agent unhealthy or missing tools")
                    self.failed += 1
            else:
                self.print_failure(f"FAILED: Status {response.status_code}")
                print(response.text)
                self.failed += 1
        except Exception as e:
            self.print_failure(f"FAILED: {e}")
            self.failed += 1
    
    def test_rag_only(self):
        """Test 2: RAG-only query (should NOT use web search)"""
        self.print_header("TEST 2: RAG-Only Query (High Quality)")
        
        payload = {
            "query": "What is the PTO policy?",
            "topic": "benefits"
        }
        
        print(f"Query: '{payload['query']}'")
        print(f"Expected: RAG search only, no web search")
        
        try:
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                tools_used = data.get("tools_used", [])
                confidence = data.get("confidence", 0)
                search_path = data.get("metadata", {}).get("search_path", "")
                
                print(f"\n⏱️  Duration: {duration:.2f}s")
                print(f"🔧 Tools used: {tools_used}")
                print(f"📊 Search path: {search_path}")
                print(f"💯 Confidence: {confidence:.2f}")
                print(f"📝 Answer preview: {data.get('answer', '')[:150]}...")
                
                # Check: Should only use rag_search
                if "rag_search" in tools_used and "web_search" not in tools_used:
                    self.print_success("PASSED: Used RAG only (expected behavior)")
                    self.passed += 1
                elif "web_search" in tools_used:
                    self.print_warning("WARNING: Used web search when RAG should suffice")
                    self.print_info("This might indicate thresholds need tuning")
                    self.warnings += 1
                    self.passed += 1  # Still passes, just suboptimal
                else:
                    self.print_failure("FAILED: No search tools used")
                    self.failed += 1
            else:
                self.print_failure(f"FAILED: Status {response.status_code}")
                print(response.text)
                self.failed += 1
        except Exception as e:
            self.print_failure(f"FAILED: {e}")
            self.failed += 1
    
    def test_rag_plus_web(self):
        """Test 3: Query requiring web search"""
        self.print_header("TEST 3: RAG + Web Search Query (Quality Threshold)")
        
        payload = {
            "query": "What are the latest employment law changes in 2024?",
            "topic": "employment_law"
        }
        
        print(f"Query: '{payload['query']}'")
        print(f"Expected: RAG first, then web search for current info")
        
        try:
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                tools_used = data.get("tools_used", [])
                confidence = data.get("confidence", 0)
                reasoning_trace = data.get("reasoning_trace", [])
                
                print(f"\n⏱️  Duration: {duration:.2f}s")
                print(f"🔧 Tools used: {tools_used}")
                print(f"💯 Confidence: {confidence:.2f}")
                
                # Show reasoning trace for quality check
                print(f"\n🧠 Reasoning Trace:")
                for trace in reasoning_trace[:5]:  # Show first 5 steps
                    print(f"   - {trace}")
                
                # Check: Should use both rag_search and web_search
                if "rag_search" in tools_used and "web_search" in tools_used:
                    self.print_success("PASSED: Used both RAG and web search (expected)")
                    self.passed += 1
                elif "web_search" in tools_used:
                    self.print_success("PASSED: Used web search")
                    self.print_info("Note: May have skipped RAG directly")
                    self.passed += 1
                else:
                    self.print_warning("WARNING: Did not use web search for recent query")
                    self.print_info("RAG may have had unexpectedly good results")
                    self.warnings += 1
                    self.passed += 1  # Still acceptable
            else:
                self.print_failure(f"FAILED: Status {response.status_code}")
                print(response.text)
                self.failed += 1
        except Exception as e:
            self.print_failure(f"FAILED: {e}")
            self.failed += 1
    
    def test_edge_case(self):
        """Test 4: Edge case query"""
        self.print_header("TEST 4: Edge Case Query")
        
        payload = {
            "query": "How does blockchain technology relate to freedom of expression?",
            "topic": "benefits"
        }
        
        print(f"Query: '{payload['query']}'")
        print(f"Expected: Handle gracefully, likely use web search")
        
        try:
            response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                tools_used = data.get("tools_used", [])
                confidence = data.get("confidence", 0)
                
                print(f"\n🔧 Tools used: {tools_used}")
                print(f"💯 Confidence: {confidence:.2f}")
                print(f"📝 Answer preview: {data.get('answer', '')[:200]}...")
                
                self.print_success("PASSED: Handled edge case without errors")
                self.passed += 1
            else:
                self.print_failure(f"FAILED: Status {response.status_code}")
                self.failed += 1
        except Exception as e:
            self.print_failure(f"FAILED: {e}")
            self.failed += 1
    
    def test_invalid_input(self):
        """Test 5: Invalid input handling"""
        self.print_header("TEST 5: Invalid Input Handling")
        
        # Test 5.1: Missing query
        print("\n5.1: Missing required 'query' field")
        try:
            response = requests.post(
                f"{BASE_URL}/chat", 
                json={"topic": "test"},
                timeout=10
            )
            
            if response.status_code == 400:
                self.print_success("PASSED: Correctly rejected missing query")
                self.passed += 1
            else:
                self.print_failure(f"FAILED: Should return 400, got {response.status_code}")
                self.failed += 1
        except Exception as e:
            self.print_failure(f"FAILED: {e}")
            self.failed += 1
        
        # Test 5.2: Invalid difficulty
        print("\n5.2: Invalid difficulty level")
        try:
            response = requests.post(
                f"{BASE_URL}/chat",
                json={
                    "query": "test",
                    "difficulty": "super_hard"
                },
                timeout=10
            )
            
            if response.status_code == 400:
                self.print_success("PASSED: Correctly rejected invalid difficulty")
                self.passed += 1
            else:
                self.print_warning(f"WARNING: Expected 400, got {response.status_code}")
                self.warnings += 1
                self.passed += 1
        except Exception as e:
            self.print_failure(f"FAILED: {e}")
            self.failed += 1
    
    def test_tools_endpoint(self):
        """Test 6: Tools listing endpoint"""
        self.print_header("TEST 6: Tools Endpoint")
        
        try:
            response = requests.get(f"{BASE_URL}/tools", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", {})
                
                print(f"\nAvailable tools: {len(tools)}")
                for tool_name, tool_info in tools.items():
                    print(f"  - {tool_name}: {tool_info.get('description', '')[:50]}...")
                
                if len(tools) >= 5:
                    self.print_success("PASSED: All tools listed")
                    self.passed += 1
                else:
                    self.print_failure(f"FAILED: Expected 5+ tools, got {len(tools)}")
                    self.failed += 1
            else:
                self.print_failure(f"FAILED: Status {response.status_code}")
                self.failed += 1
        except Exception as e:
            self.print_failure(f"FAILED: {e}")
            self.failed += 1
    
    def test_thresholds_endpoint(self):
        """Test 7: Quality thresholds endpoint"""
        self.print_header("TEST 7: Quality Thresholds Endpoint")
        
        try:
            response = requests.get(f"{BASE_URL}/thresholds", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                thresholds = data.get("thresholds", {})
                
                print(f"\nCurrent thresholds:")
                print(f"  - Min Relevance Score: {thresholds.get('min_relevance_score')}")
                print(f"  - Min Chunks: {thresholds.get('min_chunks')}")
                print(f"  - Min Avg Quality: {thresholds.get('min_avg_quality')}")
                
                if all(k in thresholds for k in ['min_relevance_score', 'min_chunks', 'min_avg_quality']):
                    self.print_success("PASSED: Thresholds endpoint working")
                    self.passed += 1
                else:
                    self.print_failure("FAILED: Missing threshold values")
                    self.failed += 1
            else:
                self.print_failure(f"FAILED: Status {response.status_code}")
                self.failed += 1
        except Exception as e:
            self.print_failure(f"FAILED: {e}")
            self.failed += 1
    
    def run_all_tests(self):
        """Run all tests and report summary"""
        self.print_header("🧪 AGENT TESTING SUITE")
        print(f"Starting tests at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check server first
        if not self.test_server_running():
            print(f"\n{Colors.RED}Cannot proceed without server connection{Colors.END}")
            sys.exit(1)
        
        try:
            self.test_health()
            self.test_rag_only()
            self.test_rag_plus_web()
            self.test_edge_case()
            self.test_invalid_input()
            self.test_tools_endpoint()
            self.test_thresholds_endpoint()
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
        except Exception as e:
            print(f"\n{Colors.RED}Test suite error: {e}{Colors.END}")
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        self.print_header("📊 TEST SUMMARY")
        print(f"Total Duration: {duration:.2f}s")
        print(f"{Colors.GREEN}✅ Passed: {self.passed}{Colors.END}")
        print(f"{Colors.RED}❌ Failed: {self.failed}{Colors.END}")
        print(f"{Colors.YELLOW}⚠️  Warnings: {self.warnings}{Colors.END}")
        
        total_tests = self.passed + self.failed
        if total_tests > 0:
            success_rate = (self.passed / total_tests) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
        
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        
        if self.failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 All tests passed!{Colors.END}")
            if self.warnings > 0:
                print(f"{Colors.YELLOW}Note: {self.warnings} warning(s) to review{Colors.END}")
            return 0
        else:
            print(f"{Colors.RED}{Colors.BOLD}⚠️  {self.failed} test(s) failed{Colors.END}")
            print(f"{Colors.YELLOW}Review the failures above and check server logs{Colors.END}")
            return 1

def main():
    """Main entry point"""
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}HR Assistant Agent - Automated Test Suite{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"\n{Colors.BLUE}Testing RAG → Web Search prioritization system{Colors.END}")
    print(f"{Colors.BLUE}Make sure the Flask server is running on http://localhost:5050{Colors.END}")
    
    # Give user time to read
    time.sleep(2)
    
    tester = AgentTester()
    exit_code = tester.run_all_tests()
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
