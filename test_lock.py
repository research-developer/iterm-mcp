#!/usr/bin/env python3
"""Test session lock management via MCP tools."""
from core.agents import AgentRegistry

registry = AgentRegistry()

# Get an agent
agent = registry.get_agent('test-agents')
if agent:
    session_id = agent.session_id
    print(f'Agent: {agent.name}, Session: {session_id}')

    # Check if lock manager is attached
    if hasattr(registry, '_lock_manager') and registry._lock_manager:
        lock_manager = registry._lock_manager

        # Try to lock
        locked = lock_manager.lock_session(session_id, 'test-agents')
        print(f'Lock acquired: {locked}')

        # Check lock status
        lock_info = lock_manager.get_lock(session_id)
        print(f'Lock info: {lock_info}')

        # Try to lock with different agent (should fail)
        locked2 = lock_manager.lock_session(session_id, 'other-agent')
        print(f'Second lock attempt: {locked2}')

        # Unlock
        unlocked = lock_manager.unlock_session(session_id, 'test-agents')
        print(f'Unlocked: {unlocked}')

        print(f'PASS: {locked and not locked2 and unlocked}')
    else:
        print('Lock manager not attached - testing via MCP tool instead')
        print('Use lock_session MCP tool to test locking')
        print('PASS: N/A (lock manager not attached in standalone mode)')
else:
    print('Agent not found')
