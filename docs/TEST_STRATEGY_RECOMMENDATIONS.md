# Test Strategy Recommendations for iterm-mcp

**Based on:** [TEST_AUDIT.md](./TEST_AUDIT.md)  
**Date:** December 5, 2025  
**Priority:** High  
**Owner:** Development Team

## Quick Summary

This document provides actionable recommendations based on the audit of claude-code-mcp test patterns. Recommendations are prioritized by impact and effort.

---

## Priority 1: Critical Improvements (Do First)

### 1.1 Implement MCPTestClient

**Why:** Enable protocol-level testing of MCP servers without manual JSON-RPC construction.

**What to build:**
```python
# tests/utils/mcp_test_client.py
class MCPTestClient:
    """Test client for MCP servers using subprocess communication."""
    
    def __init__(self, server_command: list[str], env: dict = None)
    async def connect(self) -> None
    async def disconnect(self) -> None
    async def send_request(self, method: str, params: dict = None) -> dict
    async def call_tool(self, name: str, args: dict) -> Any
    async def list_tools(self) -> list[dict]
    async def list_resources(self) -> list[dict]
```

**Usage example:**
```python
async def test_list_sessions():
    client = MCPTestClient(['python', '-m', 'iterm_mcpy.fastmcp_server'])
    await client.connect()
    
    tools = await client.list_tools()
    assert 'list_sessions' in [t['name'] for t in tools]
    
    result = await client.call_tool('list_sessions', {})
    assert 'sessions' in result
    
    await client.disconnect()
```

**Effort:** 4-6 hours  
**Impact:** High - enables comprehensive MCP protocol testing

---

### 1.2 Separate Unit and Integration Tests

**Why:** Unit tests should run fast in CI without macOS/iTerm2 dependencies.

**Directory structure:**
```
tests/
├── unit/              # No external dependencies (runs on Linux CI)
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_layouts.py
│   ├── test_agent_registry_unit.py
│   └── test_grpc_client_unit.py
├── integration/       # Requires iTerm2 (runs on macOS CI)
│   ├── __init__.py
│   ├── test_basic_functionality.py
│   ├── test_advanced_features.py
│   ├── test_persistent_session.py
│   └── test_command_tracking.py
├── edge_cases/        # Edge scenarios and validation
│   ├── __init__.py
│   ├── test_input_validation.py
│   ├── test_special_characters.py
│   └── test_concurrency.py
└── utils/             # Shared test utilities
    ├── __init__.py
    ├── mcp_test_client.py
    ├── iterm_mock.py
    └── helpers.py
```

**pytest.ini configuration:**
```ini
[pytest]
markers =
    unit: Fast unit tests without external dependencies
    integration: Tests requiring iTerm2/macOS
    edge: Edge case scenarios
    slow: Tests that take >5 seconds

testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

**Run commands:**
```bash
# Fast unit tests (CI on Linux)
pytest tests/unit -v -m unit

# Integration tests (CI on macOS)
pytest tests/integration -v -m integration

# All tests
pytest tests -v
```

**Migration plan:**
1. Create new directory structure
2. Move model/logic tests to `unit/`
3. Keep iTerm2-dependent tests in `integration/`
4. Update CI workflows to run separately
5. Gradually add mocks to convert integration → unit

**Effort:** 1-2 days  
**Impact:** High - enables fast CI feedback, better organization

---

## Priority 2: Important Improvements (Do Next)

### 2.1 Create iTerm2 Mock Infrastructure

**Why:** Unit tests shouldn't require actual iTerm2 installation.

**Implementation:**
```python
# tests/utils/iterm_mock.py
class ITerm2ConnectionMock:
    """Mock iTerm2 connection."""
    
    def __init__(self):
        self.sessions = {}
        self.windows = {}
        
    async def async_create():
        """Factory method mimicking iterm2.Connection.async_create()."""
        return ITerm2ConnectionMock()

class ITerm2SessionMock:
    """Mock iTerm2 session."""
    
    def __init__(self, session_id: str, name: str = None):
        self.id = session_id
        self.session_id = session_id
        self.name = name or f"Session-{session_id}"
        self._output_buffer = []
        self._is_processing = False
        
    async def async_send_text(self, text: str):
        """Mock send text."""
        self._output_buffer.append(('input', text))
        
    async def async_get_screen_contents(self) -> str:
        """Mock get screen contents."""
        return '\n'.join([line for _, line in self._output_buffer])
        
    async def async_set_name(self, name: str):
        """Mock set name."""
        self.name = name

class ITerm2AppMock:
    """Mock iTerm2 app."""
    
    async def async_create_window():
        """Create mock window."""
        return ITerm2WindowMock()

class ITerm2WindowMock:
    """Mock iTerm2 window."""
    
    def __init__(self):
        self.sessions = []
        self.current_tab = ITerm2TabMock()
        
    async def async_create_tab():
        """Create mock tab."""
        return ITerm2TabMock()

class ITerm2TabMock:
    """Mock iTerm2 tab."""
    
    def __init__(self):
        self.current_session = None
        
    async def async_split_pane(vertical=True):
        """Mock split pane."""
        session = ITerm2SessionMock(f"session-{len(self.sessions)}")
        return session
```

**Usage in tests:**
```python
import pytest
from unittest.mock import patch
from tests.utils.iterm_mock import ITerm2ConnectionMock
from core.terminal import ItermTerminal

@pytest.mark.unit
async def test_create_session_unit():
    # Mock iterm2 module
    mock_conn = ITerm2ConnectionMock()
    
    terminal = ItermTerminal(mock_conn)
    await terminal.initialize()
    
    session = await terminal.create_window()
    assert session is not None
    assert session.id in mock_conn.sessions
```

**Effort:** 2-3 days  
**Impact:** High - enables unit testing without iTerm2

---

### 2.2 Add Edge Case Test Suite

**Why:** Systematic edge case testing improves reliability.

**Categories to cover:**

1. **Input Validation** (`tests/edge_cases/test_input_validation.py`)
```python
class TestInputValidation:
    def test_empty_session_name(self):
        """Empty strings in session names."""
        
    def test_null_session_id(self):
        """None/null session IDs."""
        
    def test_invalid_max_lines(self):
        """Negative or zero max_lines."""
        
    def test_oversized_input(self):
        """Very large input strings (>1MB)."""
```

2. **Special Characters** (`tests/edge_cases/test_special_characters.py`)
```python
class TestSpecialCharacters:
    def test_unicode_in_names(self):
        """Unicode characters in session names."""
        
    def test_control_characters(self):
        """Control characters in input."""
        
    def test_ansi_escape_codes(self):
        """ANSI escape sequences."""
        
    def test_newlines_in_commands(self):
        """Multi-line commands."""
```

3. **Concurrency** (`tests/edge_cases/test_concurrency.py`)
```python
class TestConcurrency:
    async def test_parallel_session_creation(self):
        """Create 10 sessions simultaneously."""
        
    async def test_concurrent_writes(self):
        """Write to 5 sessions at the same time."""
        
    async def test_read_write_race(self):
        """Read and write to same session concurrently."""
        
    async def test_cascade_message_contention(self):
        """Send cascade messages to overlapping teams."""
```

4. **Resource Limits** (`tests/edge_cases/test_limits.py`)
```python
class TestResourceLimits:
    async def test_max_sessions(self):
        """Create 100+ sessions."""
        
    async def test_large_output(self):
        """Handle 10MB+ output."""
        
    async def test_long_running_command(self):
        """Command that runs for 60+ seconds."""
```

**Effort:** 2-3 days  
**Impact:** Medium-High - catches bugs before production

---

### 2.3 Improve Test Utilities

**Why:** Reduce boilerplate and improve test readability.

**Create:** `tests/utils/helpers.py`
```python
import asyncio
import tempfile
import shutil
from typing import Callable, Optional
from pathlib import Path

# Temporary directory management
def create_temp_dir(prefix: str = 'iterm-mcp-test-') -> Path:
    """Create a temporary directory for tests."""
    return Path(tempfile.mkdtemp(prefix=prefix))

def cleanup_temp_dir(path: Path) -> None:
    """Clean up temporary directory."""
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)

# Async helpers
async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_msg: str = "Condition not met"
) -> bool:
    """Wait for a condition to become true."""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        if condition():
            return True
        await asyncio.sleep(interval)
    raise TimeoutError(error_msg)

async def wait_for_output(
    session,
    expected: str,
    timeout: float = 5.0
) -> bool:
    """Wait for expected output in session."""
    async def check():
        output = await session.get_screen_contents()
        return expected in output
    return await wait_for_condition(check, timeout)

# Assertions
def assert_session_exists(terminal, session_id: str) -> None:
    """Assert that a session exists."""
    session = terminal.get_session_by_id(session_id)
    assert session is not None, f"Session {session_id} not found"

def assert_agent_registered(registry, agent_name: str) -> None:
    """Assert that an agent is registered."""
    agent = registry.get_agent(agent_name)
    assert agent is not None, f"Agent {agent_name} not registered"

# Test data builders
def build_session_config(
    name: str = "test-session",
    agent: Optional[str] = None,
    teams: Optional[list] = None
) -> dict:
    """Build a session configuration for testing."""
    config = {"name": name}
    if agent:
        config["agent"] = agent
    if teams:
        config["teams"] = teams
    return config
```

**Usage:**
```python
from tests.utils.helpers import (
    create_temp_dir, cleanup_temp_dir,
    wait_for_output, assert_session_exists
)

async def test_example():
    temp_dir = create_temp_dir()
    try:
        # Test code
        await wait_for_output(session, "expected text")
        assert_session_exists(terminal, session_id)
    finally:
        cleanup_temp_dir(temp_dir)
```

**Effort:** 1 day  
**Impact:** Medium - improves test maintainability

---

## Priority 3: Nice-to-Have Improvements (Do Later)

### 3.1 Add Performance/Stress Tests

**Why:** Validate behavior under load.

**Tests to add:**
```python
# tests/performance/test_throughput.py
@pytest.mark.slow
class TestThroughput:
    async def test_message_throughput(self):
        """Send 1000 messages, measure time."""
        
    async def test_session_creation_rate(self):
        """Create 100 sessions, measure time."""
        
    async def test_concurrent_reads(self):
        """Read from 50 sessions simultaneously."""

# tests/performance/test_stress.py
@pytest.mark.slow
class TestStress:
    async def test_many_sessions(self):
        """Maintain 100+ active sessions."""
        
    async def test_large_output_handling(self):
        """Process 100MB of output."""
        
    async def test_long_running_workflow(self):
        """Run for 60 minutes."""
```

**Effort:** 3-4 days  
**Impact:** Medium - ensures scalability

---

### 3.2 Improve CI Configuration

**Why:** Faster feedback, better coverage reporting.

**GitHub Actions:**
```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    name: Unit Tests (Linux)
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11']
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Run unit tests
        run: |
          pytest tests/unit -v --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        
  integration-tests:
    name: Integration Tests (macOS)
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install iTerm2
        run: brew install --cask iterm2
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run integration tests
        run: pytest tests/integration -v
        
  edge-case-tests:
    name: Edge Case Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run edge case tests
        run: pytest tests/edge_cases -v
```

**Effort:** 4-6 hours  
**Impact:** Medium - better CI visibility

---

### 3.3 Add Test Documentation

**Why:** Help contributors write good tests.

**Create:** `docs/TESTING_GUIDE.md`

Content outline:
1. How to run tests
2. Test organization
3. Writing unit tests
4. Writing integration tests
5. Using test utilities
6. Mocking best practices
7. Debugging test failures
8. Contributing new tests

**Effort:** 4-6 hours  
**Impact:** Low-Medium - improves contributor experience

---

## Implementation Timeline

### Week 1: Foundation
- [ ] Day 1-2: Implement MCPTestClient
- [ ] Day 3-4: Reorganize test directory structure
- [ ] Day 5: Set up pytest configuration and markers

### Week 2: Mocking
- [ ] Day 1-3: Create iTerm2 mock infrastructure
- [ ] Day 4-5: Convert 5-10 tests to use mocks

### Week 3: Edge Cases
- [ ] Day 1-2: Add input validation tests
- [ ] Day 3: Add special character tests
- [ ] Day 4-5: Add concurrency tests

### Week 4: Polish
- [ ] Day 1: Add test helpers
- [ ] Day 2-3: Update CI configuration
- [ ] Day 4-5: Documentation

---

## Success Metrics

After implementation, we should see:

1. **Faster CI:**
   - Unit tests: < 30 seconds
   - Integration tests: < 5 minutes
   - Total CI time: < 10 minutes

2. **Better Coverage:**
   - Unit test coverage: > 90%
   - Integration test coverage: > 80%
   - Edge case coverage: > 60%

3. **More Reliable:**
   - Test flakiness: < 1%
   - False positives: < 5%
   - CI success rate: > 95%

4. **Better Developer Experience:**
   - Local unit test run: < 10 seconds
   - Test documentation: Available and clear
   - Easy to add new tests

---

## Quick Start Guide

### For Immediate Impact (Today)

1. **Add pytest** to `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    # ... existing deps
]
```

2. **Create basic pytest.ini**:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
markers =
    unit: Unit tests
    integration: Integration tests
```

3. **Run existing tests with pytest**:
```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### This Week

1. Create `tests/utils/mcp_test_client.py`
2. Create `tests/unit/` and move `test_models.py`
3. Add first mock test

### This Month

1. Complete Priority 1 items
2. Start Priority 2 items
3. Update CI configuration

---

## Questions & Answers

**Q: Should we keep unittest or switch to pytest?**  
A: Keep unittest for existing tests, use pytest for new tests. pytest can run unittest tests, so there's no conflict.

**Q: Do all tests need mocks?**  
A: No. Integration tests should use real iTerm2. Unit tests should use mocks.

**Q: How do we handle tests that need both unit and integration versions?**  
A: Create both: `test_feature_unit.py` and `test_feature_integration.py`. The unit version uses mocks, the integration version uses real iTerm2.

**Q: What about the 88 existing tests?**  
A: Migrate gradually. Start with new tests following the new structure. Move existing tests over time.

**Q: How much will this slow down development?**  
A: Initially slower (1-2 weeks), then faster due to better test infrastructure and faster CI feedback.

---

## Resources

- [TEST_AUDIT.md](./TEST_AUDIT.md) - Full audit report
- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

---

**Next Steps:**
1. Review this document with the team
2. Create GitHub issues for each priority
3. Assign owners
4. Start implementation

**Questions?** Open an issue or discussion in the repository.
