# Test Strategy Recommendations for iterm-mcp

**Based on:** 
- [TEST_AUDIT.md](./TEST_AUDIT.md) (Claude Code MCP)
- [HAPPY_CLI_TEST_AUDIT.md](./HAPPY_CLI_TEST_AUDIT.md) (Happy CLI)

**Date:** December 2025  
**Priority:** High  
**Owner:** Development Team

## Executive Summary

This document provides actionable recommendations for improving iterm-mcp's test strategy, combining best practices from `claude-code-mcp` (structure, mocking, edge cases) and `happy-cli` (stress testing, resilience, real integration).

**Strategic Goals:**
1.  **Protocol Confidence:** Verify MCP protocol compliance using `MCPTestClient` (from Claude Code).
2.  **Reliability at Scale:** Ensure stability under load with stress and resilience tests (from Happy CLI).
3.  **Clean Architecture:** Separate unit tests (fast, mocked) from integration tests (thorough, real execution).
4.  **Developer Experience:** Provide robust test utilities and faster CI feedback loops.

---

## Comprehensive Implementation Roadmap

### Priority 1: Critical Improvements (Week 1)
*Focus: Foundation and Quick Wins*

#### 1.1 Implement MCPTestClient
**Source:** Claude Code MCP Audit  
**Why:** Enable protocol-level testing of MCP servers without manual JSON-RPC construction.

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
```

#### 1.2 Improve Test Utilities & Fix Async Issues
**Source:** Happy CLI Audit  
**Why:** Reduce boilerplate, fix "no current event loop" errors, and improve test readability.

**Key Components:**
- `wait_for(condition, timeout)` helper.
- `session_cleanup` context manager.
- `pytest-asyncio` configuration to fix event loop issues.

```python
# tests/helpers.py
async def wait_for(condition: Callable[[], Awaitable[bool]], timeout: float = 5.0, ...):
    """Wait for an async condition to become true."""
    # ... implementation ...

async def wait_for_output(session, expected_text: str, timeout: float = 5.0):
    """Wait for specific text to appear in session output."""
    # ... implementation ...
```

#### 1.3 Separate Unit and Integration Tests
**Source:** Claude Code MCP Audit  
**Why:** Unit tests should run fast in CI without macOS/iTerm2 dependencies.

**Structure:**
```
tests/
├── unit/              # No external dependencies (runs on Linux CI)
├── integration/       # Requires iTerm2 (runs on macOS CI)
└── utils/             # Shared utilities
```

**pytest.ini:**
```ini
[pytest]
markers =
    unit: Fast unit tests
    integration: Requires iTerm2/macOS
    stress: High load tests
```

---

### Priority 2: Core Testing Infrastructure (Week 2)
*Focus: robustness and isolation*

#### 2.1 Create iTerm2 Mock Infrastructure
**Source:** Claude Code MCP Audit  
**Why:** Unit tests shouldn't require actual iTerm2 installation.

```python
# tests/utils/iterm_mock.py
class ITerm2ConnectionMock:
    """Mock iTerm2 connection for unit tests."""
    ...
```

#### 2.2 Concurrent Operation Stress Tests
**Source:** Happy CLI Audit  
**Why:** Validate multi-agent orchestration under load (20+ sessions, parallel messages).

```python
@pytest.mark.stress
async def test_concurrent_session_creation():
    """Test creating 20+ sessions simultaneously."""
    # ... use asyncio.gather to create many sessions ...
```

---

### Priority 3: Resilience & Edge Cases (Week 3)

#### 3.1 Edge Case Test Suite
**Source:** Claude Code MCP Audit  
**Why:** Systematic coverage of input validation, special characters, and boundaries.

- **Input Validation:** Empty names, null IDs.
- **Special Characters:** Unicode, ANSI codes, control characters.
- **Limits:** Max lines, large payloads.

#### 3.2 Resilience Testing
**Source:** Happy CLI Audit  
**Why:** Verify behavior during failures (server crash, client disconnect, corrupt state).

```python
@pytest.mark.resilience
async def test_server_survives_client_disconnect():
    """Test that server continues running after client disconnects."""
    # ...
```

---

### Priority 4: Advanced Integration (Week 4+)

#### 4.1 Real gRPC Integration Tests
**Source:** Happy CLI Audit  
**Why:** Test against the real gRPC server, not just mocks.

#### 4.2 Test Fixtures
**Source:** Happy CLI Audit  
**Why:** Reusable data for complex scenarios (team hierarchies, cascade messages).

---

## Success Metrics

| Metric | Target |
|--------|--------|
| **Unit Test Duration** | < 30 seconds |
| **Total CI Duration** | < 10 minutes |
| **Unit Coverage** | > 90% |
| **Integration Coverage** | > 80% |
| **Stress Tests** | 10+ scenarios (concurrent sessions, messaging) |
| **Resilience Tests** | Server recovery, disconnect handling |

## Quick Start Guide

1.  **Update Dependencies:**
    Add `pytest-asyncio`, `pytest-timeout` to `pyproject.toml`.

2.  **Create Helper Module:**
    Implement `tests/helpers.py` with `wait_for` logic.

3.  **Fix Async Tests:**
    Migrate existing `unittest.TestCase` based async tests to `pytest` style with `@pytest.mark.asyncio`.

4.  **Implement MCPTestClient:**
    Create the client wrapper to start testing protocol compliance.

## Detailed Code Reference

Refer to the source audits for full code listings:
- `TEST_AUDIT.md` for `MCPTestClient` and `ITerm2Mock`.
- `HAPPY_CLI_TEST_AUDIT.md` for `stress tests`, `resilience tests`, and `wait_for` implementation details.
