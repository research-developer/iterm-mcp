#!/usr/bin/env python3
"""Test cascading message resolution."""
from core.agents import AgentRegistry, CascadingMessage

registry = AgentRegistry()

# Create a test team with agents
test_team = registry.get_team('docs-testing')
if not test_team:
    test_team = registry.create_team('docs-testing', 'Documentation testing team')
    print(f'Created team: {test_team.name}')

# Ensure agents are in the team
for agent_name in ['test-profiles', 'test-agents']:
    agent = registry.get_agent(agent_name)
    if agent and 'docs-testing' not in agent.teams:
        registry.assign_to_team(agent_name, 'docs-testing')
        print(f'Assigned {agent_name} to docs-testing')

# Test resolve_cascade_targets with team message
team_cascade = CascadingMessage(teams={'docs-testing': 'Hello team!'})
result = registry.resolve_cascade_targets(team_cascade)
print(f'\nResolving team docs-testing:')
print(f'  Result: {result}')

# Test with specific agent
agent_cascade = CascadingMessage(agents={'test-profiles': 'Hello agent!'})
result2 = registry.resolve_cascade_targets(agent_cascade)
print(f'\nResolving agent test-profiles:')
print(f'  Result: {result2}')

# Test broadcast
broadcast_cascade = CascadingMessage(broadcast='Hello everyone!')
result3 = registry.resolve_cascade_targets(broadcast_cascade)
print(f'\nBroadcast to all:')
print(f'  Agents reached: {len(result3)}')

passed = len(result) >= 1 and len(result2) == 1
print(f'\nPASS: {passed}')
