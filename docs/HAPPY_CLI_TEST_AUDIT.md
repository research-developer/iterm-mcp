# Happy-CLI Test Strategy Audit

**Date:** December 2024  
**Author:** iterm-mcp Development Team  
**Parent Epic:** research-developer/iterm-mcp#10  
**Objective:** Review slopus/happy-cli test patterns and recommend adoptable strategies for iterm-mcp

---

## Executive Summary

This audit analyzes the test strategy of [slopus/happy-cli](https://github.com/slopus/happy-cli), a mobile/web client for Claude Code and Codex. The project demonstrates several advanced testing patterns that could enhance iterm-mcp's test coverage, particularly in areas of:

- Real API call integration testing
- Message queue mode management and permission edge cases
- Session lifecycle and daemon management
- Concurrent operation stress testing
- File system watcher and async iterator testing

**Key Findings:**
- 15 test files totaling 2,386 lines of test code
- Mix of unit tests (utils, parsers) and integration tests (daemon, session scanning)
- Advanced patterns for testing async operations and real-world scenarios
- Strong focus on resilience and edge case handling
- Extensive use of fixtures and test helpers

---

## 1. Test Infrastructure Overview

### 1.1 Test Framework & Configuration

**Framework:** Vitest (v3.2.4)
- Modern, fast test runner built on Vite
- Better ESM support than Jest
- Native TypeScript support
- Built-in coverage with v8 provider

**Configuration (`vitest.config.ts`):**
```typescript
{
  globals: false,
  environment: 'node',
  include: ['src/**/*.test.ts'],
  globalSetup: ['./src/test-setup.ts'],
  coverage: {
    provider: 'v8',
    reporter: ['text', 'json', 'html'],
    exclude: ['node_modules/**', 'dist/**', '**/*.d.ts', '**/*.config.*', '**/mockData/**']
  }
}
```

**Key Features:**
- Global setup builds project before tests run
- Environment variables loaded from `.env.integration-test`
- Path aliases (`@/` → `./src/`)
- Coverage reporting with exclusions for non-code files

### 1.2 Test Environment Separation

Happy-CLI uses **three distinct environments**:

1. **Development** (`.env.dev`)
   - `HAPPY_HOME_DIR=~/.happy-dev`
   - Local development server

2. **Integration Test** (`.env.integration-test`)
   - `HAPPY_HOME_DIR=~/.happy-dev-test` (ISOLATED)
   - `HAPPY_SERVER_URL=http://localhost:3005`
   - `HAPPY_DAEMON_HEARTBEAT_INTERVAL=30000` (30s for faster tests)
   - Dangerous logging enabled for debugging

3. **Production**
   - `HAPPY_HOME_DIR=~/.happy`
   - Production server URL

**Lesson for iterm-mcp:**
> Isolated test environments prevent test pollution and enable safe concurrent testing. Consider adopting environment-specific configuration for iTerm2 session management.

---

## 2. Test Categories & Patterns

### 2.1 Unit Tests (Pure Logic)

**Files:**
- `utils/MessageQueue2.test.ts` (459 lines)
- `utils/PushableAsyncIterable.test.ts`
- `utils/hmac_sha512.test.ts`
- `utils/deterministicJson.test.ts`
- `parsers/specialCommands.test.ts` (81 lines)
- `modules/common/pathSecurity.test.ts` (30 lines)

**Patterns Observed:**

#### 2.1.1 Message Queue Mode Testing
The `MessageQueue2.test.ts` demonstrates **extensive edge case coverage** for a complex async queue system:

```typescript
it('should return only messages with same mode and keep others', async () => {
    queue.push('local1', 'local');
    queue.push('local2', 'local');
    queue.push('remote1', 'remote');
    
    const result1 = await queue.waitForMessagesAndGetAsString();
    expect(result1?.mode).toBe('local');
    expect(queue.size()).toBe(2); // remote messages still queued
});
```

**Key Testing Strategies:**
1. **Mode Batching:** Tests verify messages with same mode are batched together
2. **Async Waiting:** Tests use `setTimeout` to simulate delayed message arrival
3. **Abort Signal Handling:** Tests cover AbortController integration
4. **Isolation Modes:** Tests `pushImmediate` vs `pushIsolateAndClear` semantics
5. **Complex Mode Hashing:** Tests object-based modes with multiple fields
6. **Null Reset Values:** Tests undefined values properly reset mode fields

**Relevance to iterm-mcp:**
> The message queue testing pattern could be adapted for testing iTerm2 session output buffering and command queueing. Consider testing scenarios where commands are batched by session or permission mode.

#### 2.1.2 Security & Path Validation
`pathSecurity.test.ts` demonstrates **security-first testing**:

```typescript
it('should prevent path traversal attacks', () => {
    const result = validatePath('../../.ssh/id_rsa', workingDir);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('outside the working directory');
});
```

**Lesson for iterm-mcp:**
> Add similar security tests for iTerm2 session commands, especially when accepting user input for file paths or command execution.

### 2.2 Integration Tests (Real System Interaction)

**Files:**
- `daemon/daemon.integration.test.ts` (473 lines) ⭐ **Most Complex**
- `claude/utils/sessionScanner.test.ts` (210 lines)

#### 2.2.1 Daemon Lifecycle Testing

The daemon integration test is **exceptionally comprehensive**, testing:

1. **Startup & Shutdown**
   - Daemon starts as background process
   - State file creation and cleanup
   - Process ID tracking
   - Graceful vs forced shutdown (SIGTERM vs SIGKILL)

2. **Session Management**
   - Session spawning via HTTP API
   - Session tracking (terminal vs daemon-spawned)
   - Session metadata webhooks
   - Concurrent session operations

3. **Stress Testing**
   ```typescript
   it('stress test: spawn / stop', { timeout: 60_000 }, async () => {
       const sessionCount = 20;
       const promises = Array(sessionCount).fill(null).map(() => 
           spawnDaemonSession('/tmp')
       );
       const results = await Promise.all(promises);
       expect(results).toHaveLength(sessionCount);
       // ... verify all sessions, then stop all
   });
   ```

4. **Version Mismatch Detection**
   - Tests automatic daemon restart when CLI version changes
   - Simulates `npm upgrade` scenario
   - Verifies old daemon is killed and new daemon takes over
   - Tests critical timing: heartbeat interval vs rebuild time

**Key Patterns:**

```typescript
// Wait utility for async conditions
async function waitFor(
    condition: () => Promise<boolean>,
    timeout = 5000,
    interval = 100
): Promise<void> {
    const start = Date.now();
    while (Date.now() - start < timeout) {
        if (await condition()) return;
        await new Promise(resolve => setTimeout(resolve, interval));
    }
    throw new Error('Timeout waiting for condition');
}

// Health check before running tests
describe.skipIf(!await isServerHealthy())('Daemon Integration Tests', ...)
```

**Relevance to iterm-mcp:**
> The daemon lifecycle testing patterns are **highly applicable** to iterm-mcp's gRPC server and agent registry. Consider:
> - Testing concurrent session creation/destruction
> - Testing server startup/shutdown with active sessions
> - Testing agent registry persistence across restarts
> - Adding stress tests for multi-agent orchestration

#### 2.2.2 File System Watching & Async Iteration

`sessionScanner.test.ts` tests a **complex real-time scanning system**:

```typescript
it('should process initial session and resumed session correctly', async () => {
    // Phase 1: Initial session
    const fixture1 = await readFile('0-say-lol-session.jsonl', 'utf-8');
    await writeFile(sessionFile1, fixture1);
    scanner.onNewSession(sessionId1);
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Phase 2: Resumed session with NEW session ID
    const fixture2 = await readFile('1-continue-run-ls-tool.jsonl', 'utf-8');
    await writeFile(sessionFile2, fixture2);
    scanner.onNewSession(sessionId2);
    
    // Verify deduplication of historical messages
    expect(collectedMessages).toHaveLength(expectedCount);
});
```

**Testing Strategies:**
1. **Fixture Files:** Uses `.jsonl` fixtures in `__fixtures__/` directory
2. **Incremental Writing:** Tests file watching by appending lines with delays
3. **Message Deduplication:** Verifies messages with same UUIDs aren't processed twice
4. **Session Resume:** Tests complex scenario of Claude sessions spanning multiple files
5. **Cleanup:** Proper cleanup of file watchers and temporary directories

**Relevance to iterm-mcp:**
> This pattern is excellent for testing iTerm2 output monitoring and log scanning. Consider:
> - Testing real-time output capture with incremental writes
> - Testing session reconnection with persistent IDs
> - Testing output deduplication across session restarts

### 2.3 Test Utilities & Helpers

#### 2.3.1 Global Test Setup
`test-setup.ts` runs build before tests:

```typescript
export function setup() {
    process.env.VITEST_POOL_TIMEOUT = '60000'
    const buildResult = spawnSync('yarn', ['build'], { stdio: 'pipe' })
    if (buildResult.stderr && buildResult.stderr.length > 0) {
        // Check for actual errors vs debugger output
        if (errorOutput.includes('Command failed with exit code')) {
            throw new Error(`Build failed: ${errorOutput}`)
        }
    }
}
```

**Why this matters:**
- Integration tests spawn the actual CLI binary from `dist/`
- Ensures tests always run against freshly built code
- Catches compilation errors before test execution

#### 2.3.2 Shared Test Helpers

**Utility Functions:**
```typescript
// Async condition waiter with timeout
async function waitFor(condition, timeout, interval)

// Health check that skips tests if prerequisites not met
async function isServerHealthy()

// Process spawning wrapper
function spawnHappyCLI(args, options)
```

**Relevance to iterm-mcp:**
> iterm-mcp should create similar test utilities:
> - `waitForSession()` - Wait for iTerm2 session to be ready
> - `waitForOutput()` - Wait for expected output in session
> - `skipIfNoITerm()` - Skip tests on non-macOS or when iTerm2 unavailable
> - `createTestSession()` - Standardized session creation with cleanup

---

## 3. Permission Mode & Edge Case Testing

### 3.1 Permission Mode Handling

Happy-CLI extensively tests **permission mode transitions** in message queues:

```typescript
it('should batch messages with enhanced mode hashing', async () => {
    queue.push('message1', { permissionMode: 'default', model: 'sonnet' });
    queue.push('message2', { permissionMode: 'default', model: 'sonnet' }); // Batched
    queue.push('message3', { permissionMode: 'default', model: 'haiku' }); // New batch
    queue.push('message4', { permissionMode: 'default', fallbackModel: 'opus' }); // New batch
    
    // Each mode change creates new batch
    expect(firstBatch.message).toBe('message1\nmessage2');
    expect(secondBatch.message).toBe('message3');
});
```

**Edge Cases Tested:**
1. **Mode Field Changes:** Tests every field change (model, fallbackModel, customSystemPrompt, allowedTools, disallowedTools)
2. **Undefined Resets:** Tests that `undefined` values reset fields properly
3. **Mode Hashing:** Tests deterministic JSON hashing for complex objects
4. **Array Equality:** Tests that array fields are compared correctly

### 3.2 Concurrent Operation Edge Cases

**Daemon Tests:**
- ✅ Concurrent session spawning (20+ simultaneous)
- ✅ Session metadata updates during concurrent operations
- ✅ Race conditions in session tracking
- ✅ Second daemon startup prevention
- ✅ Signal handling (SIGTERM vs SIGKILL)

**Session Scanner Tests:**
- ✅ Duplicate message handling (same message ID)
- ✅ Session resume with historical messages
- ✅ File watching during rapid writes
- ✅ Cleanup during active scanning

### 3.3 Resilience Testing

```typescript
it('should die with cleanup logs when SIGTERM is sent', async () => {
    const logFile = await getLatestDaemonLog();
    process.kill(daemonPid, 'SIGTERM');
    
    await new Promise(resolve => setTimeout(resolve, 4_000));
    
    // Verify cleanup happened
    const logContent = readFileSync(logFile.path, 'utf8');
    expect(logContent).toContain('SIGTERM');
    expect(logContent).toContain('cleanup');
});
```

**Resilience Patterns:**
- Process lifecycle (startup, heartbeat, shutdown)
- Graceful vs forced termination
- State file cleanup on crash
- Log verification after process death

---

## 4. Testing Real API Calls

### 4.1 HTTP API Integration

Happy-CLI tests **real HTTP endpoints** instead of mocking:

```typescript
async function isServerHealthy(): Promise<boolean> {
    try {
        const response = await fetch('http://localhost:3005/', { 
            signal: AbortSignal.timeout(1000) 
        });
        if (!response.ok) return false;
        
        // Also check credentials exist
        const testCredentials = existsSync(
            join(configuration.happyHomeDir, 'access.key')
        );
        return testCredentials;
    } catch {
        return false;
    }
}

describe.skipIf(!await isServerHealthy())('Daemon Integration Tests', ...)
```

**Benefits:**
- Tests real network behavior (timeouts, retries, etc.)
- Catches serialization/deserialization bugs
- Tests actual API contract, not mocked version
- Requires running local dev server for tests

**Tradeoffs:**
- ❌ Slower tests (network overhead)
- ❌ Requires infrastructure setup
- ✅ Higher confidence in integration
- ✅ Tests real failure modes

### 4.2 File System Integration

Tests write to **real temporary directories**:

```typescript
beforeEach(async () => {
    testDir = join(tmpdir(), `scanner-test-${Date.now()}`);
    await mkdir(testDir, { recursive: true });
    
    projectDir = join(homedir(), '.claude', 'projects', projectName);
    await mkdir(projectDir, { recursive: true });
});

afterEach(async () => {
    if (existsSync(testDir)) {
        await rm(testDir, { recursive: true, force: true });
    }
});
```

**Benefits:**
- Tests real file system behavior (permissions, timing, etc.)
- Tests actual fs watcher implementation
- No mocking complexity

---

## 5. Comparison with iterm-mcp Test Strategy

### 5.1 Current iterm-mcp Strengths

✅ **Good Unit Test Coverage:**
- 70 passing unit tests for models and agent registry
- Comprehensive agent/team functionality tests
- Good use of temporary directories for registry persistence

✅ **Structured Test Organization:**
- Tests separated by feature area
- Consistent use of unittest framework
- Async test patterns with `async_setup`/`async_teardown`

✅ **Integration Tests Exist:**
- Tests for basic iTerm2 functionality
- Tests for advanced features (monitoring, filtering)
- Tests for persistent sessions

### 5.2 Gaps Compared to Happy-CLI

❌ **Missing Resilience Testing:**
- No stress tests for concurrent operations
- No tests for server/agent registry crash scenarios
- No tests for signal handling (SIGTERM, SIGKILL)
- No tests for version/upgrade scenarios

❌ **Limited Edge Case Coverage:**
- Few tests for permission mode transitions
- Limited tests for message deduplication
- No tests for complex queueing scenarios
- Few tests for race conditions

❌ **No Real API Integration Tests:**
- Integration tests mock iTerm2 (fail on Linux CI)
- No tests against real gRPC server
- No end-to-end tests with actual MCP clients

❌ **Missing Test Utilities:**
- No `waitFor()` utility for async conditions
- No health check decorators for conditional test skipping
- No fixture management for complex test data

❌ **Limited Async Testing:**
- Some async tests fail with event loop errors
- No tests for async iterators
- Limited testing of concurrent async operations

---

## 6. Recommended Tests for iterm-mcp

### 6.1 High Priority (Adopt Immediately)

#### 6.1.1 Concurrent Operation Stress Tests
```python
# tests/test_concurrent_operations.py

import asyncio
import pytest
from iterm_mcpy.grpc_client import ITermClient

@pytest.mark.asyncio
async def test_concurrent_session_creation():
    """Test creating 20+ sessions simultaneously."""
    async with ITermClient() as client:
        # Create 20 sessions concurrently
        tasks = [
            client.create_sessions([
                {"name": f"session-{i}", "agent": f"agent-{i}"}
            ])
            for i in range(20)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all succeeded
        assert len(results) == 20
        assert all(r.success for r in results)
        
        # Verify all sessions are tracked
        sessions = await client.list_sessions()
        assert len(sessions) >= 20
        
        # Clean up
        for result in results:
            await client.close_session(result.session_id)
```

#### 6.1.2 Agent Registry Resilience Tests
```python
# tests/test_agent_registry_resilience.py

def test_registry_survives_corrupt_data():
    """Test registry handles corrupted JSONL gracefully."""
    registry = AgentRegistry(data_dir=temp_dir)
    registry.register_agent("agent-1", "session-1")
    
    # Corrupt the JSONL file
    with open(registry._agents_file, 'a') as f:
        f.write("CORRUPTED DATA\n")
    
    # Should still load valid entries
    registry2 = AgentRegistry(data_dir=temp_dir)
    agent = registry2.get_agent("agent-1")
    assert agent is not None
    assert agent.session_id == "session-1"
```

#### 6.1.3 Wait Utility for Async Conditions
```python
# tests/helpers.py

async def wait_for(
    condition: Callable[[], Awaitable[bool]],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_msg: str = "Timeout waiting for condition"
) -> None:
    """Wait for async condition to become true."""
    start = time.time()
    while time.time() - start < timeout:
        if await condition():
            return
        await asyncio.sleep(interval)
    raise TimeoutError(error_msg)

# Usage in tests
async def test_session_becomes_ready():
    session = await terminal.create_session("test")
    
    # Wait for session to be ready for input
    await wait_for(
        lambda: session.is_ready(),
        timeout=10.0,
        error_msg="Session never became ready"
    )
```

#### 6.1.4 gRPC Server Lifecycle Tests
```python
# tests/test_grpc_server_lifecycle.py

@pytest.mark.asyncio
async def test_server_shutdown_with_active_sessions():
    """Test graceful server shutdown with active sessions."""
    server = await start_grpc_server()
    
    async with ITermClient() as client:
        # Create active sessions
        await client.create_sessions([
            {"name": "session-1"},
            {"name": "session-2"}
        ])
        
        # Shutdown server
        await server.stop(grace=5.0)
        
        # Verify sessions were cleaned up
        # (This tests graceful shutdown logic)
```

### 6.2 Medium Priority (Adopt Soon)

#### 6.2.1 Output Deduplication Tests
```python
def test_output_deduplication_across_reconnect():
    """Test that reconnecting to session doesn't duplicate output."""
    session1 = terminal.create_session("test")
    session1.send_text("echo 'test'\n")
    output1 = session1.get_output()
    
    # Simulate reconnect
    persistent_id = session1.persistent_id
    session2 = terminal.get_session_by_persistent_id(persistent_id)
    output2 = session2.get_output()
    
    # Should not have duplicate output
    assert output1 == output2
```

#### 6.2.2 Message Queue Mode Tests
```python
def test_cascade_message_priority():
    """Test that cascade messages follow priority: agent > team > broadcast."""
    registry = AgentRegistry()
    registry.register_agent("alice", "session-1", teams=["frontend"])
    
    cascade = CascadingMessage(
        broadcast="Broadcast message",
        teams={"frontend": "Team message"},
        agents={"alice": "Agent-specific message"}
    )
    
    # Alice should receive agent-specific message, not team or broadcast
    targets = registry.resolve_cascade_targets(cascade)
    alice_message = next(t for t in targets if t.agent == "alice")
    assert alice_message.content == "Agent-specific message"
```

#### 6.2.3 Fixture-Based Session Tests
```python
# tests/fixtures/session_output.txt
"""
$ echo "hello"
hello
$ ls
file1.txt
file2.txt
"""

def test_output_parsing_with_fixtures():
    """Test output parsing using fixture files."""
    fixture_path = Path(__file__).parent / "fixtures" / "session_output.txt"
    expected = fixture_path.read_text()
    
    session = create_test_session()
    session.send_text("echo 'hello'\n")
    session.send_text("ls\n")
    
    output = session.get_output()
    assert "hello" in output
    assert "file1.txt" in output
```

### 6.3 Lower Priority (Nice to Have)

#### 6.3.1 Security & Path Validation
```python
def test_command_injection_prevention():
    """Test that command input is sanitized."""
    session = terminal.create_session("test")
    
    # Attempt command injection
    malicious_input = "echo safe; rm -rf /"
    
    # Should only execute safe part (implementation dependent)
    session.send_text(malicious_input, safe_mode=True)
    output = session.get_output()
    
    assert "safe" in output
    assert "rm" not in output  # Injection prevented
```

#### 6.3.2 Performance Benchmarks
```python
import pytest

@pytest.mark.benchmark
def test_session_creation_performance(benchmark):
    """Benchmark session creation time."""
    def create_session():
        terminal.create_session("bench-test")
    
    result = benchmark(create_session)
    assert result.stats['mean'] < 0.5  # Less than 500ms
```

---

## 7. Action Items for iterm-mcp

### Immediate Actions (Week 1-2)

1. **Create Test Utilities Module** (`tests/helpers.py`)
   - ✅ Implement `wait_for()` utility
   - ✅ Add `skip_if_no_iterm()` decorator
   - ✅ Add `create_test_session()` helper

2. **Add Stress Tests** (`tests/test_concurrent_operations.py`)
   - ✅ Test concurrent session creation (20+ sessions)
   - ✅ Test concurrent message sending
   - ✅ Test agent registry under load

3. **Improve Async Test Handling**
   - ✅ Fix event loop issues in existing tests
   - ✅ Add pytest-asyncio configuration
   - ✅ Standardize async test patterns

### Short Term (Month 1)

4. **Add Resilience Tests** (`tests/test_resilience.py`)
   - ⬜ Test gRPC server crash recovery
   - ⬜ Test agent registry corruption handling
   - ⬜ Test signal handling (SIGTERM, SIGKILL)

5. **Add Integration Tests for Real gRPC**
   - ⬜ Create local gRPC server fixture
   - ⬜ Test against real server instead of mocks
   - ⬜ Add end-to-end tests with MCP client

6. **Create Test Fixtures**
   - ⬜ Add `tests/fixtures/` directory
   - ⬜ Create sample session output files
   - ⬜ Create sample agent configurations

### Medium Term (Month 2-3)

7. **Add Permission Mode Tests**
   - ⬜ Test cascade message priority resolution
   - ⬜ Test message deduplication
   - ⬜ Test team hierarchy message routing

8. **Add Edge Case Coverage**
   - ⬜ Test session reconnection scenarios
   - ⬜ Test output overflow handling
   - ⬜ Test rapid command execution

9. **Performance Testing**
   - ⬜ Add pytest-benchmark
   - ⬜ Benchmark session operations
   - ⬜ Benchmark message routing

### Long Term (Month 4+)

10. **Security Testing**
    - ⬜ Add command injection tests
    - ⬜ Add path traversal tests
    - ⬜ Add privilege escalation tests

11. **Test Documentation**
    - ⬜ Document test patterns and conventions
    - ⬜ Create test writing guide
    - ⬜ Add examples for common test scenarios

---

## 8. Key Takeaways

### What Happy-CLI Does Well

1. **Real Integration Testing:** Uses actual HTTP APIs and file systems instead of extensive mocking
2. **Stress Testing:** Tests with 20+ concurrent operations to find race conditions
3. **Resilience Focus:** Tests process lifecycle, signal handling, and crash recovery
4. **Test Utilities:** Comprehensive helper functions for async testing
5. **Environment Isolation:** Separate test environment prevents pollution
6. **Fixture Management:** Well-organized test data in `__fixtures__/` directories

### What iterm-mcp Can Improve

1. **Add Concurrent Operation Tests:** Current tests are mostly sequential
2. **Add Resilience Tests:** No tests for server crashes or signal handling
3. **Create Test Utilities:** Add `wait_for()`, skip decorators, and session helpers
4. **Fix Async Tests:** Resolve event loop issues in integration tests
5. **Add Real gRPC Tests:** Test against actual server instead of mocks
6. **Add Fixtures:** Organize test data in fixture files

### Overall Assessment

Happy-CLI demonstrates **mature testing practices** suitable for a production CLI tool. The test suite:
- Balances unit and integration testing
- Tests real-world scenarios and edge cases
- Uses advanced async testing patterns
- Includes stress and resilience testing
- Has good separation of concerns

iterm-mcp has a **solid foundation** but can benefit from:
- Adding stress and resilience tests
- Improving async test infrastructure
- Testing against real systems (gRPC, iTerm2)
- Better test utilities and helpers

**Recommendation:** Adopt the patterns outlined in Section 6 incrementally, starting with high-priority items. Focus on concurrent operations and resilience testing first, as these are critical for multi-agent orchestration reliability.

---

## Appendix A: Test File Inventory

### Happy-CLI Test Files (15 files, 2,386 lines)

| File | Lines | Category | Focus |
|------|-------|----------|-------|
| `daemon/daemon.integration.test.ts` | 473 | Integration | Daemon lifecycle, stress testing |
| `utils/MessageQueue2.test.ts` | 459 | Unit | Message batching, mode handling |
| `claude/utils/sessionScanner.test.ts` | 210 | Integration | File watching, deduplication |
| `utils/PushableAsyncIterable.test.ts` | ~150 | Unit | Async iteration |
| `parsers/specialCommands.test.ts` | 81 | Unit | Command parsing |
| `modules/common/pathSecurity.test.ts` | 30 | Unit | Security validation |
| Others (9 files) | ~1,000 | Mixed | Utils, codex, UI, modules |

### iterm-mcp Test Files (11 files, 88 passing)

| File | Tests | Category | Status |
|------|-------|----------|--------|
| `test_agent_registry.py` | 33 | Unit | ✅ Passing |
| `test_models.py` | 37 | Unit | ✅ Passing |
| `test_grpc_client.py` | 18 | Integration | ✅ Passing |
| `test_basic_functionality.py` | 7 | Integration | ⚠️ Requires macOS |
| `test_advanced_features.py` | 3 | Integration | ⚠️ Requires macOS |
| Others (6 files) | 27 | Mixed | ⚠️ Mixed status |

---

## Appendix B: Code Examples for Adoption

### B.1 Wait Utility Implementation
```python
# tests/helpers.py

import asyncio
import time
from typing import Callable, Awaitable, TypeVar

T = TypeVar('T')

async def wait_for(
    condition: Callable[[], Awaitable[bool]],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_msg: str = "Timeout waiting for condition"
) -> None:
    """
    Wait for an async condition to become true.
    
    Args:
        condition: Async function that returns bool
        timeout: Maximum time to wait in seconds
        interval: Polling interval in seconds
        error_msg: Error message if timeout occurs
        
    Raises:
        TimeoutError: If condition doesn't become true within timeout
        
    Example:
        >>> await wait_for(
        ...     lambda: session.is_ready(),
        ...     timeout=10.0,
        ...     error_msg="Session never became ready"
        ... )
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            if await condition():
                return
        except Exception:
            pass  # Condition check failed, keep waiting
        await asyncio.sleep(interval)
    raise TimeoutError(error_msg)


async def wait_for_value(
    getter: Callable[[], Awaitable[T]],
    expected: T,
    timeout: float = 5.0,
    interval: float = 0.1,
    error_msg: str = "Timeout waiting for value"
) -> T:
    """
    Wait for an async getter to return expected value.
    
    Example:
        >>> count = await wait_for_value(
        ...     lambda: client.get_session_count(),
        ...     expected=5,
        ...     timeout=10.0
        ... )
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            value = await getter()
            if value == expected:
                return value
        except Exception:
            pass
        await asyncio.sleep(interval)
    raise TimeoutError(f"{error_msg}: expected {expected}")
```

### B.2 Test Fixture Helper
```python
# tests/fixtures.py

from pathlib import Path
from typing import Dict, Any
import json

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(name: str, format: str = "txt") -> str:
    """Load a test fixture file."""
    fixture_path = FIXTURES_DIR / f"{name}.{format}"
    return fixture_path.read_text()

def load_json_fixture(name: str) -> Dict[str, Any]:
    """Load a JSON fixture file."""
    content = load_fixture(name, "json")
    return json.loads(content)

def load_jsonl_fixture(name: str) -> list:
    """Load a JSONL fixture file."""
    content = load_fixture(name, "jsonl")
    return [json.loads(line) for line in content.strip().split('\n')]

# Usage:
# session_output = load_fixture("session_output")
# agent_config = load_json_fixture("agent_config")
# messages = load_jsonl_fixture("cascade_messages")
```

### B.3 Conditional Test Skip Decorator
```python
# tests/decorators.py

import sys
import platform
import pytest
import shutil

def skip_if_no_iterm():
    """Skip test if iTerm2 is not available."""
    is_macos = platform.system() == 'Darwin'
    has_iterm = shutil.which('iterm2') is not None
    
    return pytest.mark.skipif(
        not (is_macos and has_iterm),
        reason="iTerm2 not available (requires macOS with iTerm2 installed)"
    )

def skip_if_no_grpc_server():
    """Skip test if gRPC server is not running."""
    import grpc
    
    def check_server():
        try:
            channel = grpc.insecure_channel('localhost:50051')
            grpc.channel_ready_future(channel).result(timeout=1)
            return True
        except:
            return False
    
    return pytest.mark.skipif(
        not check_server(),
        reason="gRPC server not running on localhost:50051"
    )

# Usage:
# @skip_if_no_iterm()
# async def test_iterm_session():
#     ...
```

---

**Document End**

*For questions or clarifications, see parent issue research-developer/iterm-mcp#10*
