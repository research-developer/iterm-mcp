#!/usr/bin/env python3
"""
Example: Orchestrating Multiple Claude Code Instances

This example demonstrates how to use iterm-mcp to coordinate multiple
Claude Code instances running in parallel iTerm sessions.

Use case: Managing a multi-component project with separate agents for
frontend, backend, and testing.
"""

import asyncio
import iterm2
from core.terminal import ItermTerminal
from core.layouts import LayoutManager, LayoutType
from core.agents import AgentRegistry, CascadingMessage


async def main():
    """Main orchestration example."""
    
    # 1. Connect to iTerm2
    print("Connecting to iTerm2...")
    connection = await iterm2.Connection.async_create()
    
    # 2. Initialize terminal and agent registry
    terminal = ItermTerminal(connection)
    await terminal.initialize()
    layout_manager = LayoutManager(terminal)
    agent_registry = AgentRegistry()
    
    print("Setting up multi-agent environment...\n")
    
    # 3. Create teams
    agent_registry.create_team("development", "Development team")
    agent_registry.create_team("frontend", "Frontend developers", parent_team="development")
    agent_registry.create_team("backend", "Backend developers", parent_team="development")
    
    # 4. Create sessions with layout
    session_map = await layout_manager.create_layout(
        layout_type=LayoutType.QUAD,
        pane_names=["Frontend", "Backend", "Testing", "Monitor"]
    )
    
    # 5. Register agents
    frontend_session = await terminal.get_session_by_name("Frontend")
    backend_session = await terminal.get_session_by_name("Backend")
    testing_session = await terminal.get_session_by_name("Testing")
    monitor_session = await terminal.get_session_by_name("Monitor")
    
    agent_registry.register_agent(
        name="frontend-agent",
        session_id=frontend_session.id,
        teams=["frontend", "development"],
        metadata={"role": "ui-development", "tech": "react"}
    )
    
    agent_registry.register_agent(
        name="backend-agent",
        session_id=backend_session.id,
        teams=["backend", "development"],
        metadata={"role": "api-development", "tech": "python"}
    )
    
    agent_registry.register_agent(
        name="test-agent",
        session_id=testing_session.id,
        teams=["development"],
        metadata={"role": "quality-assurance"}
    )
    
    print("Agents registered:")
    for agent in agent_registry.list_agents():
        print(f"  - {agent.name}: teams={agent.teams}, metadata={agent.metadata}")
    print()
    
    # 6. Optional: Start Claude Code MCP in each session
    # Uncomment if you want to run @steipete/claude-code-mcp in each session
    """
    print("Starting Claude Code MCP in each session...")
    
    await frontend_session.send_text(
        "npx -y @steipete/claude-code-mcp@latest",
        execute=True
    )
    await backend_session.send_text(
        "npx -y @steipete/claude-code-mcp@latest",
        execute=True
    )
    await testing_session.send_text(
        "npx -y @steipete/claude-code-mcp@latest",
        execute=True
    )
    """
    
    # 7. Example: Send cascading messages
    print("Example 1: Cascading messages with priority")
    print("-" * 50)
    
    # Resolve cascade targets
    cascade = CascadingMessage(
        broadcast="All agents: sync your code",
        teams={
            "frontend": "Frontend team: run npm install",
            "backend": "Backend team: run pip install -r requirements.txt"
        },
        agents={
            "test-agent": "Test agent: prepare test environment"
        }
    )
    
    targets = agent_registry.resolve_cascade_targets(cascade)
    print("Message dispatch plan:")
    for message, agent_names in targets.items():
        print(f"\n  Message: '{message}'")
        print(f"  Recipients: {', '.join(agent_names)}")
    print()
    
    # 8. Example: Parallel command execution
    print("\nExample 2: Execute commands in parallel")
    print("-" * 50)
    
    # Get session IDs for all development team agents
    dev_agents = agent_registry.list_agents(team="development")
    dev_session_ids = agent_registry.get_session_ids_for_agents(
        [a.name for a in dev_agents]
    )
    
    print(f"Executing 'echo' command in {len(dev_session_ids)} sessions...")
    
    # Send commands to all development sessions
    tasks = []
    for agent in dev_agents:
        session = await terminal.get_session_by_id(agent.session_id)
        task = session.send_text(
            f"echo 'Hello from {agent.name}!'",
            execute=True
        )
        tasks.append(task)
    
    # Wait for all commands to complete
    await asyncio.gather(*tasks)
    print("Commands sent!\n")
    
    # 9. Example: Message deduplication
    print("\nExample 3: Message deduplication")
    print("-" * 50)
    
    # Record a message as sent
    agent_registry.record_message_sent(
        "Deploy to staging",
        ["frontend-agent", "backend-agent"]
    )
    
    # Check if message was already sent
    already_sent_1 = agent_registry.was_message_sent("Deploy to staging", "frontend-agent")
    already_sent_2 = agent_registry.was_message_sent("Deploy to staging", "test-agent")
    
    print(f"Was 'Deploy to staging' sent to frontend-agent? {already_sent_1}")
    print(f"Was 'Deploy to staging' sent to test-agent? {already_sent_2}")
    
    # Filter unsent recipients
    unsent = agent_registry.filter_unsent_recipients(
        "Deploy to staging",
        ["frontend-agent", "backend-agent", "test-agent"]
    )
    print(f"Unsent recipients: {unsent}\n")
    
    # 10. Show session info
    print("\nExample 4: Monitor session")
    print("-" * 50)
    print(f"Monitor session ID: {monitor_session.id}")
    print(f"Monitor persistent ID: {monitor_session.persistent_id}")
    print("  (Can reconnect to this session later using persistent_id)")
    
    # Send info to monitor
    await monitor_session.send_text("echo '=== Multi-Agent Orchestration Demo ==='", execute=True)
    await monitor_session.send_text(f"echo 'Active agents: {len(agent_registry.list_agents())}'", execute=True)
    await monitor_session.send_text(f"echo 'Active teams: {len(agent_registry.list_teams())}'", execute=True)
    
    await asyncio.sleep(1)
    
    # Read output from monitor
    output = await monitor_session.get_screen_contents()
    print("\nMonitor output:")
    print(output)
    
    print("\n" + "=" * 50)
    print("Demo complete!")
    print("=" * 50)
    print("\nAgent registry is persisted to ~/.iterm-mcp/")
    print("You can reconnect to these sessions using their persistent IDs")
    print("\nPress Ctrl+C to exit (sessions will remain open)")
    
    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    asyncio.run(main())
