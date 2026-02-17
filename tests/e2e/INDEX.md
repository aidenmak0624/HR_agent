# Chatbot E2E Test Results - File Index

## Quick Start

Start here for a quick overview:
1. Read `README_TEST_RESULTS.md` (this directory) - 2-3 min read
2. Check metrics above in "Key Results"
3. Explore specific files based on your needs

## Key Results at a Glance

| Metric | Value |
|--------|-------|
| Total Tests | 60 |
| Tests Passed | 9 (15%) |
| Tests Failed | 51 (85%) |
| API Success Rate | 100% |
| Avg Response Time | 3ms |

## Files by Purpose

### Need a Quick Summary? (5 min)
- **README_TEST_RESULTS.md** - Overview, key findings, how to use files

### Need High-Level Report? (10 min)
- **TEST_EXECUTION_SUMMARY.md** - Executive summary, results by category, metrics

### Need Detailed Analysis? (30 min)
- **CHATBOT_TEST_REPORT.md** - Complete analysis, all 12 categories, root causes, recommendations

### Need Raw Data?
- **chatbot_test_results.json** - Machine-readable format, import to analysis tools
- **chatbot_test_results.csv** - Spreadsheet format, filter/sort in Excel/Google Sheets

### Need to Run Tests?
- **chatbot_test_runner.py** - Executable test framework, generates all results

## File Descriptions

### 1. chatbot_test_runner.py
**Type:** Python Script (Executable)  
**Size:** 16 KB, 449 lines  
**Purpose:** Main test framework

**Contains:**
- Test categories and 60+ test queries
- API request/response handling
- Result evaluation logic
- JSON/CSV output generation
- Summary table printing

**To Run:**
```bash
python3 chatbot_test_runner.py
```

**Output:**
- Console: Formatted test results table
- chatbot_test_results.json - Machine-readable
- chatbot_test_results.csv - Spreadsheet-friendly

### 2. chatbot_test_results.json
**Type:** JSON Data  
**Size:** 29 KB, 791 lines  
**Purpose:** Complete test results in JSON format

**Contains:**
```json
{
  "test_run_info": {
    "timestamp": "2026-02-08T00:24:33.791533",
    "api_url": "http://localhost:5050/api/v2/query",
    "total_tests": 60,
    "passed_tests": 9,
    "failed_tests": 51,
    "pass_rate": 15.0
  },
  "results": [
    {
      "category": "...",
      "query": "...",
      "success": true/false,
      "pass": true/false,
      "reason": "...",
      "response": {"answer": "..."},
      "response_time_ms": 0.0,
      "agent_type": "...",
      "confidence": 0.0-1.0
    },
    ...
  ]
}
```

**Use For:**
- Import to analysis tools
- Automated processing
- Data warehousing
- Machine learning

### 3. chatbot_test_results.csv
**Type:** CSV Spreadsheet Data  
**Size:** 13 KB, 61 lines  
**Purpose:** Results in spreadsheet-friendly format

**Columns:**
- Test # - Sequential number
- Category - Test category name
- Query - Input query
- Status - PASS/FAIL
- API Success - API call succeeded
- Agent Type - Detected agent
- Confidence - Confidence score (0.0-1.0)
- Response Time (ms) - Latency
- Answer (first 100 chars) - Answer preview
- Failure Reason - Why it failed

**Use For:**
- Open in Excel/Google Sheets
- Sort by category or status
- Filter by pass/fail
- Pivot table analysis

### 4. README_TEST_RESULTS.md
**Type:** Markdown Documentation  
**Size:** 13 KB  
**Purpose:** Complete guide to test results

**Contains:**
- Quick summary
- All 6 file descriptions
- Test results summary
- Critical issues identified
- Performance metrics
- Confidence score analysis
- Recommendations
- How to use files
- Test expectations vs actual
- API endpoint details
- Next steps

**Best For:** First-time readers, overall understanding

### 5. TEST_EXECUTION_SUMMARY.md
**Type:** Markdown Report  
**Size:** 8.1 KB  
**Purpose:** High-level executive summary

**Contains:**
- Overall results (60 tests, 9 passed)
- Results by category table
- Key findings and issues
- Detailed category breakdown (1-12)
- Sample test results
- API response characteristics
- Performance metrics
- Recommendations
- Test execution files reference

**Best For:** Quick overview, management reporting

### 6. CHATBOT_TEST_REPORT.md
**Type:** Markdown Report  
**Size:** 19 KB, 500+ lines  
**Purpose:** Comprehensive detailed analysis

**Contains:**
- Executive summary with metrics
- All 12 category results with detailed tables
- Detailed analysis section
- Response time statistics
- Agent routing analysis
- Confidence score distribution
- Pass/fail breakdown
- Root cause analysis (4 issues)
- Test data summary (36 queries at 0.30, 23 at 0.75, etc.)
- Sample test results (JSON format)
- Recommendations with 3 priority levels
- Testing methodology details
- Deliverables reference
- Conclusion and next steps

**Best For:** Developers, technical analysis, implementation planning

## Test Categories (12 Total)

| # | Category | Tests | Expected Agent | Expected Conf | Passed |
|---|----------|-------|-----------------|---------------|--------|
| 1 | Greetings | 5 | general_assistant | 0.85+ | 0 |
| 2 | Capabilities | 5 | general_assistant | 0.85+ | 0 |
| 3 | Identity | 4 | general_assistant | 0.85+ | 0 |
| 4 | Farewell | 5 | general_assistant | 0.85+ | 0 |
| 5 | Leave Queries | 6 | leave_agent | 0.70+ | 0 |
| 6 | Benefits Queries | 6 | benefits_agent | 0.70+ | 0 |
| 7 | Policy Queries | 6 | policy_agent | 0.70+ | 0 |
| 8 | Payroll Queries | 5 | payroll_agent | 0.70+ | 0 |
| 9 | Onboarding Queries | 5 | onboarding_agent | 0.70+ | 0 |
| 10 | Document Queries | 4 | hr_agent | 0.70+ | 0 |
| 11 | Edge Cases | 5 | any | any | 5 |
| 12 | Mixed Queries | 4 | any | 0.50+ | 4 |

## Critical Issues Found

### Issue #1: Improper Agent Routing [CRITICAL]
- All 60 queries return `agent_type: "router"`
- Expected 7 different specialized agents
- Affects 51 failing tests

### Issue #2: Low Confidence Scoring [CRITICAL]
- 36 queries return 0.30 confidence (expected 0.70+)
- Indicates intent recognition failures
- Affects 60% of queries

### Issue #3: Inconsistent Scoring [HIGH]
- Similar queries return different confidence
- Reduces reliability

### Issue #4: Permission Issues [MEDIUM]
- Some queries return "no permission" errors

## How to Use These Files

### For Executives/Managers
1. Read this file (INDEX.md)
2. Read "Key Results" above
3. Skim TEST_EXECUTION_SUMMARY.md

### For QA/Testers
1. Read README_TEST_RESULTS.md
2. Review CHATBOT_TEST_REPORT.md
3. Open chatbot_test_results.csv in Excel
4. Filter and analyze by category

### For Developers
1. Read CHATBOT_TEST_REPORT.md fully
2. Review chatbot_test_results.json
3. Study chatbot_test_runner.py
4. Implement fixes using recommendations

### For Data Analysts
1. Import chatbot_test_results.json or CSV
2. Create pivot tables
3. Analyze confidence score patterns
4. Generate custom reports

## Test Execution Command

To re-run all tests:
```bash
cd /sessions/beautiful-amazing-lamport/mnt/HR_agent/tests/e2e
python3 chatbot_test_runner.py
```

Results will be:
- Printed to console (summary table)
- Saved to chatbot_test_results.json
- Saved to chatbot_test_results.csv

## Key Metrics Summary

**Pass Rate:** 15% (9/60)  
**API Success:** 100% (all requests succeeded)  
**Performance:** 3ms average (EXCELLENT)  
**Reliability:** 100% (no errors/timeouts)

**Passing:** Edge Cases (100%), Mixed Queries (100%)  
**Failing:** All single-topic categories (0%)

## Next Steps

1. **Review** - Read the appropriate files for your role
2. **Understand** - Study root causes in CHATBOT_TEST_REPORT.md
3. **Plan** - Use Priority 1/2/3 recommendations
4. **Implement** - Deploy intent classifier and agents
5. **Validate** - Re-run tests to verify improvements

## File Locations

All files are located in:
```
/sessions/beautiful-amazing-lamport/mnt/HR_agent/tests/e2e/
```

- chatbot_test_runner.py
- chatbot_test_results.json
- chatbot_test_results.csv
- README_TEST_RESULTS.md
- TEST_EXECUTION_SUMMARY.md
- CHATBOT_TEST_REPORT.md
- INDEX.md (this file)

## Support

Questions about test results? Check:
1. README_TEST_RESULTS.md - "How to Use These Files" section
2. CHATBOT_TEST_REPORT.md - Detailed analysis sections
3. Specific category section in CHATBOT_TEST_REPORT.md

---

**Test Date:** 2026-02-08  
**API:** http://localhost:5050/api/v2/query  
**Status:** Complete & Ready for Review
