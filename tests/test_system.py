#!/usr/bin/env python3
"""
Test script for Human Rights Education Platform
Tests both simple RAG and agent modes
"""

import requests
import json
import time
try:
    from colorama import init, Fore, Style
    _COLORAMA_AVAILABLE = True
except Exception:
    # Fallback definitions if colorama is not installed or import fails
    _COLORAMA_AVAILABLE = False
    def init(*args, **kwargs):
        return None
    class _Dummy:
        def __getattr__(self, name):
            return ""
    Fore = _Dummy()
    Style = _Dummy()

# Initialize colorama for colored output (no-op if missing)
init(autoreset=True)

API_BASE = "http://localhost:5050"

def print_header(text):
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{text}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

def print_success(text):
    print(f"{Fore.GREEN}✅ {text}{Style.RESET_ALL}")

def print_error(text):
    print(f"{Fore.RED}❌ {text}{Style.RESET_ALL}")

def print_info(text):
    print(f"{Fore.YELLOW}ℹ️  {text}{Style.RESET_ALL}")

def test_health():
    """Test health endpoint"""
    print_header("Testing Health Endpoint")
    try:
        response = requests.get(f"{API_BASE}/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success("Health check passed")
            print_info(f"RAG initialized: {data.get('rag_initialized')}")
            print_info(f"Agent initialized: {data.get('agent_initialized')}")
            if data.get('agent_tools'):
                print_info(f"Agent tools: {', '.join(data.get('agent_tools'))}")
            return True
        else:
            print_error(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Health check error: {e}")
        return False

def test_topics():
    """Test topics endpoint"""
    print_header("Testing Topics Endpoint")
    try:
        response = requests.get(f"{API_BASE}/api/topics", timeout=5)
        if response.status_code == 200:
            data = response.json()
            topics = data.get('topics', [])
            print_success(f"Found {len(topics)} topics")
            for topic in topics:
                print(f"  • {topic['name']} ({topic['id']})")
            return True
        else:
            print_error(f"Topics request failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Topics error: {e}")
        return False

def test_simple_rag():
    """Test simple RAG mode"""
    print_header("Testing Simple RAG Mode (/api/chat)")
    
    query = "What are human rights?"
    print_info(f"Query: {query}")
    
    try:
        start = time.time()
        response = requests.post(
            f"{API_BASE}/api/chat",
            json={
                "query": query,
                "topic": "foundational_rights",
                "difficulty": "intermediate"
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"RAG completed in {elapsed:.2f}s")
            print(f"\n{Fore.WHITE}Answer:{Style.RESET_ALL}")
            print(data.get('answer', 'No answer')[:300] + "...")
            print(f"\n{Fore.WHITE}Sources: {Style.RESET_ALL}{', '.join(data.get('sources', []))}")
            print(f"{Fore.WHITE}Confidence: {Style.RESET_ALL}{data.get('confidence', 0):.2f}")
            return True
        else:
            print_error(f"RAG request failed: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print_error(f"RAG error: {e}")
        return False

def test_agent_mode():
    """Test agent mode"""
    print_header("Testing Agent Mode (/api/agent/chat)")
    
    query = "Explain freedom of expression"
    print_info(f"Query: {query}")
    
    try:
        start = time.time()
        response = requests.post(
            f"{API_BASE}/api/agent/chat",
            json={
                "query": query,
                "topic": "freedom_expression",
                "difficulty": "intermediate"
            },
            headers={"Content-Type": "application/json"},
            timeout=60  # Agent may take longer
        )
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Agent completed in {elapsed:.2f}s")
            print(f"\n{Fore.WHITE}Answer:{Style.RESET_ALL}")
            print(data.get('answer', 'No answer')[:300] + "...")
            print(f"\n{Fore.WHITE}Sources: {Style.RESET_ALL}{', '.join(data.get('sources', []))}")
            print(f"{Fore.WHITE}Tools used: {Style.RESET_ALL}{' → '.join(data.get('tools_used', []))}")
            print(f"{Fore.WHITE}Confidence: {Style.RESET_ALL}{data.get('confidence', 0):.2f}")
            
            if data.get('reasoning_trace'):
                print(f"\n{Fore.WHITE}Reasoning trace:{Style.RESET_ALL}")
                for i, step in enumerate(data['reasoning_trace'][:3], 1):
                    print(f"  {i}. {step[:80]}...")
            
            return True
        else:
            print_error(f"Agent request failed: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print_error(f"Agent error: {e}")
        return False

def test_error_handling():
    """Test error handling"""
    print_header("Testing Error Handling")
    
    # Test 1: Missing query
    try:
        response = requests.post(
            f"{API_BASE}/api/chat",
            json={"topic": "foundational_rights"},
            timeout=5
        )
        if response.status_code == 400:
            print_success("Missing query validation works")
        else:
            print_error(f"Expected 400, got {response.status_code}")
    except Exception as e:
        print_error(f"Error test failed: {e}")
    
    # Test 2: Invalid difficulty
    try:
        response = requests.post(
            f"{API_BASE}/api/agent/chat",
            json={
                "query": "test",
                "topic": "foundational_rights",
                "difficulty": "invalid"
            },
            timeout=5
        )
        if response.status_code == 400:
            print_success("Invalid difficulty validation works")
        else:
            print_error(f"Expected 400, got {response.status_code}")
    except Exception as e:
        print_error(f"Error test failed: {e}")

def run_all_tests():
    """Run all tests"""
    print(f"\n{Fore.MAGENTA}{'='*60}")
    print(f"{Fore.MAGENTA}Human Rights Platform - System Tests")
    print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}\n")
    
    print_info("Make sure the Flask server is running on http://localhost:5050")
    input("Press Enter to continue...")
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("Topics", test_topics()))
    results.append(("Simple RAG", test_simple_rag()))
    results.append(("Agent Mode", test_agent_mode()))
    test_error_handling()
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        color = Fore.GREEN if result else Fore.RED
        print(f"{color}{status}{Style.RESET_ALL} - {name}")
    
    print(f"\n{Fore.CYAN}Total: {passed}/{total} tests passed{Style.RESET_ALL}\n")
    
    if passed == total:
        print_success("All tests passed! Your system is working correctly.")
    else:
        print_error(f"{total - passed} test(s) failed. Check the logs above.")

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Tests interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print_error(f"Test suite error: {e}")