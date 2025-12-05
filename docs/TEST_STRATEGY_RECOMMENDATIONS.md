# Test Strategy Recommendations for iterm-mcp

**Based on:** Happy-CLI Test Audit (see [HAPPY_CLI_TEST_AUDIT.md](HAPPY_CLI_TEST_AUDIT.md))  
**Date:** December 2024  
**Epic:** research-developer/iterm-mcp#10

---

## Executive Summary

This document provides actionable recommendations for improving iterm-mcp's test strategy based on patterns observed in slopus/happy-cli. The recommendations are prioritized by impact and effort, with concrete code examples for implementation.

**Quick Wins (1-2 weeks):**
1. Add test utility module with `wait_for()` helper
2. Fix async event loop issues in existing tests
3. Add concurrent operation stress tests

**High Impact (1 month):**
4. Add resilience testing (server crashes, signal handling)
5. Create test fixtures for complex scenarios
6. Add real gRPC integration tests

---

## 1. Test Utilities Module

### Status: ❌ Not Implemented
### Priority: 🔴 High (Quick Win)
### Effort: ~4 hours

### Problem
Tests currently duplicate async waiting logic and lack standardized helpers for common operations.

### Solution
Create `tests/helpers.py` with reusable test utilities.

### Implementation

```python
# tests/helpers.py

import asyncio
import time
import platform
import shutil
from typing import Callable, Awaitable, TypeVar, Optional
from pathlib import Path

import pytest
import grpc

T = TypeVar('T')

# ============================================================================
# Async Wait Utilities
# ============================================================================

async def wait_for(
    condition: Callable[[], Awaitable[bool]],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_msg: str = "Timeout waiting for condition"
) -> None:
    """
    Wait for an async condition to become true.
    
    Usage:
        await wait_for(
            lambda: session.is_ready(),
            timeout=10.0,
            error_msg="Session never became ready"
        )
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            if await condition():
                return
        except Exception:
            pass
        await asyncio.sleep(interval)
    raise TimeoutError(error_msg)


async def wait_for_value(
    getter: Callable[[], Awaitable[T]],
    expected: T,
    timeout: float = 5.0,
    interval: float = 0.1,
    comparator: Optional[Callable[[T, T], bool]] = None
) -> T:
    """
    Wait for an async getter to return expected value.
    
    Usage:
        session_count = await wait_for_value(
            lambda: client.get_session_count(),
            expected=5,
            timeout=10.0
        )
    """
    comparator = comparator or (lambda a, b: a == b)
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            value = await getter()
            if comparator(value, expected):
                return value
        except Exception:
            pass
        await asyncio.sleep(interval)
    
    raise TimeoutError(
        f"Timeout waiting for value: expected {expected}, "
        f"last value was {value if 'value' in locals() else 'unavailable'}"
    )


async def wait_for_output(
    session,
    expected_text: str,
    timeout: float = 5.0,
    interval: float = 0.2
) -> str:
    """
    Wait for specific text to appear in session output.
    
    Usage:
        output = await wait_for_output(
            session,
            "Command completed",
            timeout=10.0
        )
    """
    async def check_output():
        output = await session.get_screen_contents()
        return expected_text in output
    
    await wait_for(
        check_output,
        timeout=timeout,
        interval=interval,
        error_msg=f"Expected text '{expected_text}' not found in output"
    )
    
    return await session.get_screen_contents()

# ============================================================================
# Test Skip Decorators
# ============================================================================

def skip_if_no_iterm():
    """Skip test if iTerm2 is not available."""
    is_macos = platform.system() == 'Darwin'
    has_iterm = shutil.which('iterm2') is not None
    
    return pytest.mark.skipif(
        not (is_macos and has_iterm),
        reason="iTerm2 not available (requires macOS with iTerm2 installed)"
    )


def skip_if_no_grpc_server(host: str = 'localhost', port: int = 50051):
    """Skip test if gRPC server is not running."""
    def check_server():
        try:
            channel = grpc.insecure_channel(f'{host}:{port}')
            grpc.channel_ready_future(channel).result(timeout=1)
            channel.close()
            return True
        except:
            return False
    
    return pytest.mark.skipif(
        not check_server(),
        reason=f"gRPC server not running on {host}:{port}"
    )

# ============================================================================
# Session Helpers
# ============================================================================

async def create_test_session(
    terminal,
    name: str = "test-session",
    wait_ready: bool = True,
    ready_timeout: float = 5.0
):
    """
    Create a test session with standard setup and waiting.
    
    Usage:
        session = await create_test_session(terminal, name="my-test")
    """
    session = await terminal.create_window()
    if session:
        await session.set_name(name)
        
        if wait_ready:
            await wait_for(
                lambda: session.is_ready() if hasattr(session, 'is_ready') else True,
                timeout=ready_timeout,
                error_msg=f"Session '{name}' never became ready"
            )
    
    return session


class SessionCleanup:
    """Context manager for automatic session cleanup."""
    
    def __init__(self, terminal, session):
        self.terminal = terminal
        self.session = session
    
    async def __aenter__(self):
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            try:
                await self.terminal.close_session(self.session.id)
            except:
                pass  # Ignore cleanup errors

# ============================================================================
# Fixture Helpers
# ============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(name: str, format: str = "txt") -> str:
    """Load a test fixture file."""
    fixture_path = FIXTURES_DIR / f"{name}.{format}"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")
    return fixture_path.read_text()


def load_json_fixture(name: str):
    """Load a JSON fixture file."""
    import json
    content = load_fixture(name, "json")
    return json.loads(content)


def load_jsonl_fixture(name: str) -> list:
    """Load a JSONL fixture file."""
    import json
    content = load_fixture(name, "jsonl")
    return [json.loads(line) for line in content.strip().split('\n') if line.strip()]
```

### Usage Examples

```python
# tests/test_example_with_helpers.py

import pytest
from tests.helpers import (
    wait_for, wait_for_output, create_test_session,
    SessionCleanup, skip_if_no_iterm
)

@skip_if_no_iterm()
@pytest.mark.asyncio
async def test_session_with_helpers(terminal):
    """Example test using helper utilities."""
    
    # Create session with automatic readiness wait
    session = await create_test_session(terminal, name="test")
    
    # Use context manager for cleanup
    async with SessionCleanup(terminal, session):
        # Send command
        await session.send_text("echo 'test'\n")
        
        # Wait for expected output
        output = await wait_for_output(session, "test", timeout=5.0)
        assert "test" in output
```

---

## 2. Concurrent Operation Stress Tests

### Status: ❌ Not Implemented
### Priority: 🔴 High
### Effort: ~8 hours

### Problem
No tests verify that iterm-mcp handles concurrent operations correctly. This is critical for multi-agent orchestration.

### Solution
Add dedicated stress test suite that creates many concurrent operations.

### Implementation

```python
# tests/test_concurrent_operations.py

import asyncio
import pytest
from iterm_mcpy.grpc_client import ITermClient
from tests.helpers import wait_for_value

@pytest.mark.stress
@pytest.mark.asyncio
async def test_concurrent_session_creation():
    """Test creating 20+ sessions simultaneously."""
    session_count = 20
    
    async with ITermClient() as client:
        # Create sessions concurrently
        tasks = [
            client.create_sessions([{
                "name": f"stress-session-{i}",
                "agent": f"agent-{i}"
            }])
            for i in range(session_count)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for failures
        failures = [r for r in results if isinstance(r, Exception)]
        if failures:
            pytest.fail(f"{len(failures)} concurrent creations failed: {failures[0]}")
        
        # Verify all succeeded
        assert len(results) == session_count
        assert all(hasattr(r, 'success') and r.success for r in results)
        
        # Verify all sessions are tracked
        sessions = await client.list_sessions()
        stress_sessions = [s for s in sessions if s.name.startswith("stress-session-")]
        assert len(stress_sessions) >= session_count
        
        # Clean up all sessions
        cleanup_tasks = [
            client.close_session(r.session_id)
            for r in results if hasattr(r, 'session_id')
        ]
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)


@pytest.mark.stress
@pytest.mark.asyncio
async def test_concurrent_message_sending():
    """Test sending messages to multiple sessions in parallel."""
    async with ITermClient() as client:
        # Create 10 sessions
        create_result = await client.create_sessions([
            {"name": f"msg-session-{i}"}
            for i in range(10)
        ])
        
        session_ids = [s.session_id for s in create_result.sessions]
        
        try:
            # Send messages to all sessions concurrently
            tasks = [
                client.write_to_sessions([{
                    "content": f"echo 'message to session {i}'\n",
                    "targets": [{"session_id": sid}]
                }])
                for i, sid in enumerate(session_ids)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            failures = [r for r in results if isinstance(r, Exception)]
            assert len(failures) == 0, f"Message sending failed: {failures}"
            
        finally:
            # Clean up
            for sid in session_ids:
                await client.close_session(sid)


@pytest.mark.stress
@pytest.mark.asyncio
async def test_agent_registry_under_load():
    """Test agent registry with rapid registration/deregistration."""
    from core.agents import AgentRegistry
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    try:
        registry = AgentRegistry(data_dir=temp_dir)
        
        # Rapid registration
        tasks = [
            asyncio.to_thread(
                registry.register_agent,
                f"agent-{i}",
                f"session-{i}",
                teams=["team-a"] if i % 2 == 0 else ["team-b"]
            )
            for i in range(100)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(failures) == 0, f"Registration failures: {failures}"
        
        # Verify all registered
        all_agents = registry.list_agents()
        assert len(all_agents) == 100
        
        # Concurrent removal
        tasks = [
            asyncio.to_thread(registry.remove_agent, f"agent-{i}")
            for i in range(100)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all removed
        assert len(registry.list_agents()) == 0
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
```

### Running Stress Tests

```bash
# Run only stress tests
pytest -m stress

# Run stress tests with verbose output
pytest -m stress -v

# Run with increased timeouts
pytest -m stress --timeout=120
```

---

## 3. Resilience Testing

### Status: ❌ Not Implemented
### Priority: 🟠 Medium-High
### Effort: ~12 hours

### Problem
No tests verify behavior during failures, crashes, or abnormal conditions.

### Solution
Add resilience test suite covering crash scenarios, signal handling, and recovery.

### Implementation

```python
# tests/test_resilience.py

import signal
import time
import pytest
import os
from pathlib import Path
from iterm_mcpy.grpc_server import start_server
from tests.helpers import wait_for

@pytest.mark.resilience
@pytest.mark.asyncio
async def test_server_survives_client_disconnect():
    """Test that server continues running after client disconnects."""
    from iterm_mcpy.grpc_client import ITermClient
    
    # Start server
    server = await start_server(port=50052)
    
    try:
        # Connect and disconnect multiple clients
        for i in range(5):
            async with ITermClient(port=50052) as client:
                await client.list_sessions()
            # Client disconnected, server should still be alive
        
        # Verify server still responds
        async with ITermClient(port=50052) as client:
            sessions = await client.list_sessions()
            assert sessions is not None
    
    finally:
        await server.stop(grace=5.0)


@pytest.mark.resilience
def test_agent_registry_handles_corrupt_data():
    """Test that registry gracefully handles corrupted persistence files."""
    from core.agents import AgentRegistry
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    try:
        # Create registry and add agent
        registry = AgentRegistry(data_dir=temp_dir)
        registry.register_agent("agent-1", "session-1")
        
        # Corrupt the agents file
        agents_file = Path(temp_dir) / "agents.jsonl"
        with open(agents_file, 'a') as f:
            f.write("CORRUPTED_DATA_NOT_VALID_JSON\n")
            f.write("{incomplete json\n")
        
        # Create new registry - should skip corrupt lines
        registry2 = AgentRegistry(data_dir=temp_dir)
        
        # Should still have valid agent
        agent = registry2.get_agent("agent-1")
        assert agent is not None
        assert agent.session_id == "session-1"
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.resilience
def test_registry_handles_missing_directory():
    """Test that registry creates directory if missing."""
    from core.agents import AgentRegistry
    import tempfile
    from pathlib import Path
    
    temp_dir = Path(tempfile.mkdtemp()) / "nested" / "missing" / "dir"
    
    try:
        # Should create directory automatically
        registry = AgentRegistry(data_dir=str(temp_dir))
        registry.register_agent("test-agent", "test-session")
        
        # Verify it works
        agent = registry.get_agent("test-agent")
        assert agent is not None
        assert temp_dir.exists()
        
    finally:
        # Clean up entire tree
        root = temp_dir
        while root.parent != root:
            root = root.parent
            if "tmp" in str(root):
                break
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
```

---

## 4. Fix Async Event Loop Issues

### Status: ⚠️ Partial (Some tests failing)
### Priority: 🔴 High (Quick Win)
### Effort: ~4 hours

### Problem
Some tests fail with "no current event loop" errors in Python 3.10+.

### Solution
Standardize async test setup using pytest-asyncio.

### Implementation

```python
# pytest.ini (create or update)
[pytest]
asyncio_mode = auto
markers =
    stress: marks tests as stress tests (deselect with '-m "not stress"')
    resilience: marks tests as resilience tests
    integration: marks tests as integration tests
    unit: marks tests as unit tests

# pyproject.toml (update test dependencies)
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0",
    "pytest-timeout>=2.1.0",
]
```

```python
# Update failing tests to use pytest-asyncio

# BEFORE (causes event loop errors):
class TestExample(unittest.TestCase):
    def test_async_function(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_impl())

# AFTER (works correctly):
import pytest

@pytest.mark.asyncio
async def test_async_function():
    await async_impl()
```

### Migration Guide

1. Replace `unittest.TestCase` with pytest functions
2. Add `@pytest.mark.asyncio` to async tests
3. Remove manual event loop management
4. Use `async def` for test functions
5. Use fixtures instead of setUp/tearDown

Example migration:

```python
# OLD:
class TestSession(unittest.TestCase):
    async def async_setup(self):
        self.terminal = await create_terminal()
    
    def test_something(self):
        async def impl():
            await self.async_setup()
            # ... test code
        asyncio.get_event_loop().run_until_complete(impl())

# NEW:
@pytest.fixture
async def terminal():
    term = await create_terminal()
    yield term
    await term.cleanup()

@pytest.mark.asyncio
async def test_something(terminal):
    # ... test code
```

---

## 5. Real gRPC Integration Tests

### Status: ❌ Not Implemented
### Priority: 🟠 Medium
### Effort: ~8 hours

### Problem
Current tests mock gRPC interactions instead of testing against real server.

### Solution
Create fixtures that start real gRPC server for integration tests.

### Implementation

```python
# tests/conftest.py (pytest configuration)

import pytest
import asyncio
from iterm_mcpy.grpc_server import start_server
from iterm_mcpy.grpc_client import ITermClient

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def grpc_server():
    """Start gRPC server for integration tests."""
    server = await start_server(port=50053)  # Different port for tests
    yield server
    await server.stop(grace=5.0)


@pytest.fixture
async def grpc_client(grpc_server):
    """Provide gRPC client connected to test server."""
    async with ITermClient(port=50053) as client:
        yield client
```

```python
# tests/test_grpc_integration.py

import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_session_creation(grpc_client):
    """Test session creation against real gRPC server."""
    result = await grpc_client.create_sessions([
        {"name": "integration-test-session"}
    ])
    
    assert result.success
    assert len(result.sessions) == 1
    
    # Verify via list
    sessions = await grpc_client.list_sessions()
    test_session = next(
        (s for s in sessions if s.name == "integration-test-session"),
        None
    )
    assert test_session is not None
    
    # Clean up
    await grpc_client.close_session(test_session.id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_cascade_messaging(grpc_client):
    """Test cascade messaging against real server."""
    # Register agents
    await grpc_client.register_agent("agent-1", "session-1", teams=["team-a"])
    await grpc_client.register_agent("agent-2", "session-2", teams=["team-a"])
    await grpc_client.register_agent("agent-3", "session-3", teams=["team-b"])
    
    # Send cascade message
    result = await grpc_client.send_cascade_message(
        broadcast="All: Status update",
        teams={"team-a": "Team A: Deploy now"},
        agents={"agent-1": "Agent 1: You're lead"}
    )
    
    # Verify targeting
    assert len(result.targets) == 3
    agent1_target = next(t for t in result.targets if t.agent == "agent-1")
    assert agent1_target.content == "Agent 1: You're lead"
```

---

## 6. Test Fixtures

### Status: ❌ Not Implemented
### Priority: 🟡 Medium
### Effort: ~4 hours

### Problem
Tests use inline data instead of reusable fixtures, making tests harder to read and maintain.

### Solution
Create `tests/fixtures/` directory with common test data.

### Structure

```
tests/
├── fixtures/
│   ├── __init__.py
│   ├── session_outputs/
│   │   ├── simple_echo.txt
│   │   ├── long_output.txt
│   │   └── error_output.txt
│   ├── agent_configs/
│   │   ├── single_agent.json
│   │   ├── team_hierarchy.json
│   │   └── multi_team.json
│   └── cascade_messages/
│       ├── simple_broadcast.jsonl
│       └── complex_cascade.jsonl
└── helpers.py (includes load_fixture functions)
```

### Example Fixtures

```txt
# tests/fixtures/session_outputs/simple_echo.txt
$ echo "Hello, World!"
Hello, World!
$ pwd
/Users/test/project
$
```

```json
# tests/fixtures/agent_configs/team_hierarchy.json
{
  "teams": [
    {"name": "engineering", "description": "All engineers"},
    {"name": "frontend", "parent": "engineering"},
    {"name": "backend", "parent": "engineering"}
  ],
  "agents": [
    {"name": "alice", "session": "session-1", "teams": ["frontend"]},
    {"name": "bob", "session": "session-2", "teams": ["backend"]},
    {"name": "charlie", "session": "session-3", "teams": ["frontend", "backend"]}
  ]
}
```

### Usage

```python
# tests/test_with_fixtures.py

from tests.helpers import load_fixture, load_json_fixture

def test_output_parsing():
    """Test output parsing using fixture."""
    expected_output = load_fixture("session_outputs/simple_echo")
    
    # ... create session and run commands
    
    assert output == expected_output

def test_team_hierarchy():
    """Test team hierarchy using fixture."""
    config = load_json_fixture("agent_configs/team_hierarchy")
    
    # Create teams and agents from fixture
    for team in config["teams"]:
        registry.create_team(**team)
    
    for agent in config["agents"]:
        registry.register_agent(**agent)
    
    # Test team membership
    assert registry.get_team_members("frontend") == ["alice", "charlie"]
```

---

## Implementation Priority

### Phase 1: Foundation (Week 1-2)
- [x] ✅ Create `tests/helpers.py` with utilities
- [ ] ⬜ Fix async event loop issues
- [ ] ⬜ Update pytest configuration

### Phase 2: Core Testing (Week 3-4)
- [ ] ⬜ Add concurrent operation stress tests
- [ ] ⬜ Add resilience tests
- [ ] ⬜ Create test fixtures structure

### Phase 3: Integration (Week 5-6)
- [ ] ⬜ Add real gRPC integration tests
- [ ] ⬜ Add fixture-based tests
- [ ] ⬜ Document test patterns

### Phase 4: Enhancement (Month 2+)
- [ ] ⬜ Add performance benchmarks
- [ ] ⬜ Add security tests
- [ ] ⬜ Add cross-platform test matrix

---

## Measuring Success

### Test Coverage Metrics

**Current State:**
- Total tests: 104
- Passing: 70 unit tests
- Coverage: 23.86%

**Target State (3 months):**
- Total tests: 150+
- Passing: 120+
- Coverage: 40%+
- Stress tests: 10+
- Integration tests working in CI

### Quality Indicators

✅ **Success Criteria:**
- All async tests pass without event loop errors
- At least 5 stress tests with 20+ concurrent operations
- At least 5 resilience tests for failure scenarios
- gRPC integration tests run against real server
- Test utilities used consistently across test suite

---

## Resources

### Documentation to Create
- [ ] `docs/TESTING_GUIDE.md` - How to write tests
- [ ] `docs/TEST_PATTERNS.md` - Common test patterns
- [ ] `tests/README.md` - Running and organizing tests

### Dependencies to Add
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0",
    "pytest-timeout>=2.1.0",
    "pytest-benchmark>=4.0.0",  # For performance tests
]
```

### CI Updates Needed
```yaml
# .github/workflows/ci.yml
- name: Run unit tests
  run: pytest tests/ -m "not stress and not integration" --cov

- name: Run integration tests  
  run: pytest tests/ -m integration --cov-append

- name: Run stress tests (optional)
  run: pytest tests/ -m stress --timeout=120
  continue-on-error: true  # Don't fail build on stress test failures
```

---

## Conclusion

These recommendations provide a clear path to improving iterm-mcp's test strategy based on proven patterns from happy-cli. The focus is on:

1. **Quick wins** that can be implemented in 1-2 weeks
2. **High-impact** improvements for reliability and confidence
3. **Practical** solutions that fit iterm-mcp's architecture
4. **Incremental** adoption without requiring a complete rewrite

By following this roadmap, iterm-mcp will achieve:
- Better test coverage for concurrent operations
- More reliable async testing
- Higher confidence in production deployment
- Easier debugging of integration issues
- Better documentation for future contributors

---

**Next Steps:**
1. Review and approve this document
2. Create GitHub issues for each phase
3. Begin Phase 1 implementation
4. Track progress in Epic #10

For detailed analysis, see [HAPPY_CLI_TEST_AUDIT.md](HAPPY_CLI_TEST_AUDIT.md).
