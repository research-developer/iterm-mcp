#!/usr/bin/env python3
"""
Example demonstrating split_session usage.

This script shows various ways to use the split_session tool to create
dynamic layouts and orchestration patterns.
"""

import json
from core.models import SplitSessionRequest, SessionTarget

# ============================================================================
# EXAMPLE 1: Basic Split
# ============================================================================

def example_basic_split():
    """Basic split to create a new pane below an existing session."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic Split")
    print("=" * 60)
    
    request = SplitSessionRequest(
        target=SessionTarget(session_id="w0t0p0:s123456"),
        direction="below",
        name="DebugPane"
    )
    
    print("\nRequest:")
    print(json.dumps(json.loads(request.model_dump_json()), indent=2))
    
    print("\nWhat this does:")
    print("  - Splits the target session horizontally")
    print("  - Creates a new pane below it")
    print("  - Names the new pane 'DebugPane'")


# ============================================================================
# EXAMPLE 2: Orchestrator Pattern
# ============================================================================

def example_orchestrator_pattern():
    """Orchestrator spawning worker agents."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Orchestrator Pattern")
    print("=" * 60)
    
    # Create 3 worker agents to the right of orchestrator
    workers = []
    for i in range(1, 4):
        request = SplitSessionRequest(
            target=SessionTarget(agent="orchestrator"),
            direction="right",
            name=f"Worker{i}",
            agent=f"worker-{i}",
            team="workers",
            command=f"python worker.py --id={i}"
        )
        workers.append(request)
    
    print("\nCreating 3 worker agents:")
    for i, worker in enumerate(workers, 1):
        print(f"\n  Worker {i}:")
        data = json.loads(worker.model_dump_json())
        print(f"    - Name: {data['name']}")
        print(f"    - Agent: {data['agent']}")
        print(f"    - Team: {data['team']}")
        print(f"    - Command: {data['command']}")
    
    print("\nLayout result:")
    print("  +-------------+--------+--------+--------+")
    print("  | Orchestrator| Worker1| Worker2| Worker3|")
    print("  +-------------+--------+--------+--------+")


# ============================================================================
# EXAMPLE 3: IDE Layout
# ============================================================================

def example_ide_layout():
    """Build an IDE-like layout progressively."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: IDE Layout")
    print("=" * 60)
    
    # Starting with "Editor" session
    # Split 1: Create tests pane to the right
    split1 = SplitSessionRequest(
        target=SessionTarget(name="Editor"),
        direction="right",
        name="Tests",
        command="npm test -- --watch"
    )
    
    # Split 2: Create terminal below editor
    split2 = SplitSessionRequest(
        target=SessionTarget(name="Editor"),
        direction="below",
        name="Terminal"
    )
    
    # Split 3: Create logs below tests
    split3 = SplitSessionRequest(
        target=SessionTarget(name="Tests"),
        direction="below",
        name="Logs",
        command="tail -f app.log"
    )
    
    print("\nSplit sequence:")
    print("  1. Split Editor → right → Tests")
    print("  2. Split Editor → below → Terminal")
    print("  3. Split Tests → below → Logs")
    
    print("\nFinal layout:")
    print("  +----------+----------+")
    print("  |  Editor  |  Tests   |")
    print("  +----------+----------+")
    print("  | Terminal |  Logs    |")
    print("  +----------+----------+")


# ============================================================================
# EXAMPLE 4: Debugging Session
# ============================================================================

def example_debugging_session():
    """Open debug panes next to main session."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Debugging Session")
    print("=" * 60)
    
    # Main development session
    # Split 1: Create debugger below
    debugger = SplitSessionRequest(
        target=SessionTarget(name="DevSession"),
        direction="below",
        name="Debugger",
        command="python -m pdb app.py"
    )
    
    # Split 2: Create logs to the right
    logs = SplitSessionRequest(
        target=SessionTarget(name="DevSession"),
        direction="right",
        name="Logs",
        command="tail -f debug.log"
    )
    
    print("\nDebug layout:")
    print("  +------------+----------+")
    print("  | DevSession |  Logs    |")
    print("  +------------+----------+")
    print("  |  Debugger  |          |")
    print("  +------------+----------+")


# ============================================================================
# EXAMPLE 5: Agent with Role
# ============================================================================

def example_agent_with_role():
    """Create specialized agent sessions with roles."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Agent with Role")
    print("=" * 60)
    
    # Create different specialized agents
    builder = SplitSessionRequest(
        target=SessionTarget(agent="orchestrator"),
        direction="right",
        name="Builder",
        agent="builder-1",
        role="builder",
        command="npm run build"
    )
    
    tester = SplitSessionRequest(
        target=SessionTarget(agent="orchestrator"),
        direction="below",
        name="Tester",
        agent="tester-1",
        role="tester",
        command="npm test"
    )
    
    devops = SplitSessionRequest(
        target=SessionTarget(agent="orchestrator"),
        direction="right",
        name="DevOps",
        agent="devops-1",
        role="devops",
        command="kubectl get pods"
    )
    
    print("\nSpecialized agents:")
    print("  - Builder: Handles compilation and packaging")
    print("  - Tester: Runs tests and reports results")
    print("  - DevOps: Manages infrastructure and deployments")


# ============================================================================
# EXAMPLE 6: AI Agent Launch
# ============================================================================

def example_ai_agent_launch():
    """Launch AI agent CLIs in split panes."""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: AI Agent Launch")
    print("=" * 60)
    
    # Launch Claude agent
    claude = SplitSessionRequest(
        target=SessionTarget(name="MainSession"),
        direction="right",
        name="ClaudeHelper",
        agent="claude-helper",
        agent_type="claude",
        team="ai-agents"
    )
    
    print("\nLaunching Claude agent:")
    print("  - Target: MainSession")
    print("  - Direction: right")
    print("  - Agent type: claude (auto-launches Claude CLI)")
    print("  - Team: ai-agents")
    
    print("\nSupported agent types:")
    print("  - claude: Claude AI CLI")
    print("  - gemini: Google Gemini CLI")
    print("  - codex: OpenAI Codex CLI")
    print("  - copilot: GitHub Copilot CLI")


# ============================================================================
# EXAMPLE 7: Monitoring Sessions
# ============================================================================

def example_monitoring_sessions():
    """Create monitored sessions for long-running operations."""
    print("\n" + "=" * 60)
    print("EXAMPLE 7: Monitoring Sessions")
    print("=" * 60)
    
    # Create monitored build session
    build = SplitSessionRequest(
        target=SessionTarget(agent="orchestrator"),
        direction="below",
        name="BuildProcess",
        agent="builder",
        command="npm run build",
        monitor=True  # Enable real-time monitoring
    )
    
    print("\nMonitored build session:")
    print("  - Enables real-time output monitoring")
    print("  - Useful for long-running operations")
    print("  - Can detect completion or errors")
    print("  - Automatically tracks command output")


# ============================================================================
# EXAMPLE 8: Team Organization
# ============================================================================

def example_team_organization():
    """Organize agents into teams with color coding."""
    print("\n" + "=" * 60)
    print("EXAMPLE 8: Team Organization")
    print("=" * 60)
    
    # Create frontend team
    frontend_agents = [
        SplitSessionRequest(
            target=SessionTarget(agent="orchestrator"),
            direction="right",
            name=f"Frontend{i}",
            agent=f"frontend-{i}",
            team="frontend",
            command=f"npm run dev -- --port=300{i}"
        )
        for i in range(1, 4)
    ]
    
    # Create backend team
    backend_agents = [
        SplitSessionRequest(
            target=SessionTarget(agent="orchestrator"),
            direction="below",
            name=f"Backend{i}",
            agent=f"backend-{i}",
            team="backend",
            command=f"python api.py --port=800{i}"
        )
        for i in range(1, 4)
    ]
    
    print("\nTeam organization:")
    print("  Frontend team (3 agents):")
    print("    - All agents get the same tab color")
    print("    - Easy to identify team members visually")
    print("  Backend team (3 agents):")
    print("    - Different color from frontend")
    print("    - Clear separation of concerns")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("SPLIT_SESSION TOOL - USAGE EXAMPLES")
    print("=" * 60)
    print("\nThis script demonstrates various ways to use split_session")
    print("for dynamic layout creation and agent orchestration.")
    
    example_basic_split()
    example_orchestrator_pattern()
    example_ide_layout()
    example_debugging_session()
    example_agent_with_role()
    example_ai_agent_launch()
    example_monitoring_sessions()
    example_team_organization()
    
    print("\n" + "=" * 60)
    print("END OF EXAMPLES")
    print("=" * 60)
    print("\nTo use these in practice:")
    print("  1. Start the MCP server")
    print("  2. Use Claude Desktop with the iterm-mcp integration")
    print("  3. Call split_session with the parameters shown above")
    print("\nFor more details, see: docs/split_session.md")
    print()


if __name__ == "__main__":
    main()
