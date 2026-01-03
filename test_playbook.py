#!/usr/bin/env python3
"""Test playbook creation and structure."""
from core.models import (
    CreateSessionsRequest, SessionConfig,
    OrchestrateRequest, Playbook, PlaybookCommand,
    SessionMessage, SessionTarget
)

# Test 1: Create a simple playbook
playbook = Playbook(
    commands=[
        PlaybookCommand(
            name='initial-setup',
            messages=[
                SessionMessage(
                    content='echo "Hello from playbook"',
                    targets=[SessionTarget(team='docs-testing')],
                    execute=True
                )
            ],
            parallel=True
        ),
        PlaybookCommand(
            name='verification',
            messages=[
                SessionMessage(
                    content='echo "Setup complete"',
                    targets=[SessionTarget(agent='test-profiles')],
                    execute=True
                )
            ],
            parallel=False
        )
    ]
)

print('Playbook created:')
print(f'  Commands: {len(playbook.commands)}')
for i, cmd in enumerate(playbook.commands):
    print(f'  [{i+1}] {cmd.name}: {len(cmd.messages)} message(s), parallel={cmd.parallel}')

# Test 2: Validate with OrchestrateRequest
request = OrchestrateRequest(playbook=playbook)
print(f'\nOrchestrateRequest validated: {request is not None}')

# Test 3: Create session config
session_config = CreateSessionsRequest(
    layout='HORIZONTAL_SPLIT',
    sessions=[
        SessionConfig(name='worker-1', agent='worker-1', team='workers'),
        SessionConfig(name='worker-2', agent='worker-2', team='workers')
    ]
)

print(f'\nSession config:')
print(f'  Layout: {session_config.layout}')
print(f'  Sessions: {[s.name for s in session_config.sessions]}')

# Pass criteria
passed = (
    len(playbook.commands) == 2 and
    playbook.commands[0].name == 'initial-setup' and
    request is not None and
    len(session_config.sessions) == 2
)
print(f'\nPASS: {passed}')
