#!/usr/bin/env python3
"""
Example: Hierarchical Task Delegation with Manager Agents

This example demonstrates how to use ManagerAgent to orchestrate complex
multi-step workflows across multiple Claude Code instances running in
iTerm sessions.

Inspired by:
- CrewAI: Manager agent coordinates planning, validates results
- AutoGen: GroupChatManager orchestrates multi-agent conversations
- Agency Swarm: CEO > Developer > VA hierarchy with explicit flows

Use case: Building and deploying a full-stack application with separate
agents for building, testing, and deployment.
"""

import asyncio
import iterm2
from typing import Any, Optional, Tuple

from core.terminal import ItermTerminal
from core.layouts import LayoutManager, LayoutType
from core.agents import AgentRegistry
from core.manager import (
    ManagerAgent,
    ManagerRegistry,
    SessionRole,
    TaskStep,
    TaskPlan,
    DelegationStrategy,
    TaskStatus,
)


async def mock_execute_task(
    terminal: ItermTerminal,
    agent_registry: AgentRegistry,
) -> callable:
    """Create an execution callback for the manager.

    This callback sends commands to agents via their iTerm sessions
    and waits for output.
    """
    async def execute(
        worker: str,
        task: str,
        timeout: Optional[int] = None
    ) -> Tuple[str, bool, Optional[str]]:
        """Execute a task on a worker agent's session."""
        agent = agent_registry.get_agent(worker)
        if not agent:
            return None, False, f"Worker '{worker}' not found"

        session = await terminal.get_session_by_id(agent.session_id)
        if not session:
            return None, False, f"Session not found for worker '{worker}'"

        # Send the command
        await session.send_text(task, execute=True)

        # Wait for completion (simplified - real implementation would monitor)
        await asyncio.sleep(2)

        # Read output
        output = await session.get_screen_contents()

        # Simple success check - look for common error patterns
        error_patterns = ["error", "failed", "exception", "fatal"]
        has_error = any(pattern in output.lower() for pattern in error_patterns)

        if has_error:
            return output, False, "Command produced error output"
        return output, True, None

    return execute


async def example_simple_delegation():
    """Example 1: Simple task delegation to a single worker."""
    print("\n" + "=" * 60)
    print("Example 1: Simple Task Delegation")
    print("=" * 60)

    # Create manager with workers
    manager = ManagerAgent(
        name="build-manager",
        workers=["frontend-builder", "backend-builder", "tester"],
        worker_roles={
            "frontend-builder": SessionRole.BUILDER,
            "backend-builder": SessionRole.BUILDER,
            "tester": SessionRole.TESTER,
        },
        delegation_strategy=DelegationStrategy.ROLE_BASED
    )

    print(f"\nCreated manager '{manager.name}' with workers:")
    for worker in manager.workers:
        role = manager.worker_roles.get(worker, SessionRole.GENERAL)
        print(f"  - {worker} ({role.value})")

    # Without actual iTerm integration, show what would happen
    print("\nDelegation logic (no actual execution):")

    # Role-based selection
    builder = await manager.select_worker(required_role=SessionRole.BUILDER)
    print(f"  Selected builder for build task: {builder}")

    tester = await manager.select_worker(required_role=SessionRole.TESTER)
    print(f"  Selected tester for test task: {tester}")


async def example_plan_orchestration():
    """Example 2: Multi-step plan orchestration."""
    print("\n" + "=" * 60)
    print("Example 2: Multi-Step Plan Orchestration")
    print("=" * 60)

    # Create a build-deploy plan
    plan = TaskPlan(
        name="build-and-deploy",
        description="Build, test, and deploy a full-stack application",
        steps=[
            TaskStep(
                id="install-deps",
                task="npm install && pip install -r requirements.txt",
                role=SessionRole.BUILDER,
                timeout_seconds=300,
            ),
            TaskStep(
                id="build-frontend",
                task="cd frontend && npm run build",
                role=SessionRole.BUILDER,
                depends_on=["install-deps"],
                validation=r"Build completed|Successfully compiled",
            ),
            TaskStep(
                id="build-backend",
                task="cd backend && python setup.py build",
                role=SessionRole.BUILDER,
                depends_on=["install-deps"],
                validation=r"Build completed|Successfully built",
            ),
            TaskStep(
                id="run-tests",
                task="pytest tests/ -v",
                role=SessionRole.TESTER,
                depends_on=["build-frontend", "build-backend"],
                validation=r"passed|OK",
                retry_count=1,
            ),
            TaskStep(
                id="deploy",
                task="./scripts/deploy.sh production",
                role=SessionRole.DEVOPS,
                depends_on=["run-tests"],
                validation="success",
            ),
        ],
        stop_on_failure=True,
    )

    print(f"\nPlan: {plan.name}")
    print(f"Description: {plan.description}")
    print(f"Stop on failure: {plan.stop_on_failure}")

    print("\nSteps:")
    for step in plan.steps:
        deps = f" (depends on: {', '.join(step.depends_on)})" if step.depends_on else ""
        optional = " [optional]" if step.optional else ""
        role = f" [{step.role.value}]" if step.role else ""
        validation = f" (validates: {step.validation})" if step.validation else ""
        print(f"  {step.id}: {step.task}{role}{deps}{optional}{validation}")

    # Validate the plan
    errors = plan.validate_dependencies()
    if errors:
        print(f"\nPlan validation errors: {errors}")
    else:
        print("\nPlan validation: ✓ All dependencies valid")

    # Show execution order
    order = plan.get_execution_order()
    print("\nExecution order:")
    for i, group in enumerate(order, 1):
        if len(group) > 1:
            print(f"  Step {i}: [parallel] {', '.join(group)}")
        else:
            print(f"  Step {i}: {group[0]}")


async def example_parallel_execution():
    """Example 3: Parallel task execution."""
    print("\n" + "=" * 60)
    print("Example 3: Parallel Task Groups")
    print("=" * 60)

    # Plan with parallel steps
    plan = TaskPlan(
        name="parallel-build",
        steps=[
            TaskStep(id="install", task="npm install"),
            TaskStep(id="lint", task="npm run lint", depends_on=["install"]),
            TaskStep(id="typecheck", task="npm run typecheck", depends_on=["install"]),
            TaskStep(id="test", task="npm test", depends_on=["lint", "typecheck"]),
        ],
        # Group lint and typecheck to run in parallel
        parallel_groups=[
            ["install"],
            ["lint", "typecheck"],
            ["test"],
        ]
    )

    print(f"\nPlan: {plan.name}")
    print("\nParallel execution groups:")
    for i, group in enumerate(plan.parallel_groups, 1):
        if len(group) > 1:
            print(f"  Group {i}: {' + '.join(group)} (parallel)")
        else:
            print(f"  Group {i}: {group[0]}")


async def example_validation_callbacks():
    """Example 4: Custom validation callbacks."""
    print("\n" + "=" * 60)
    print("Example 4: Validation Callbacks")
    print("=" * 60)

    manager = ManagerAgent(name="validation-demo")

    # Register custom validators
    def test_coverage_validator(result):
        """Check if test coverage meets threshold."""
        if result.output and "coverage:" in result.output.lower():
            import re
            match = re.search(r'coverage:\s*(\d+(?:\.\d+)?)%', result.output, re.I)
            if match:
                coverage = float(match.group(1))
                if coverage >= 80:
                    return True, f"Coverage {coverage}% meets 80% threshold"
                return False, f"Coverage {coverage}% below 80% threshold"
        return False, "Coverage information not found in output"

    def no_warnings_validator(result):
        """Check that output contains no warnings."""
        if result.output and "warning" in result.output.lower():
            return False, "Output contains warnings"
        return True, "No warnings found"

    manager.register_validator("coverage-80", test_coverage_validator)
    manager.register_validator("no-warnings", no_warnings_validator)

    print("\nRegistered validators:")
    for name in manager._validators:
        print(f"  - {name}")

    print("\nValidation types supported:")
    print("  - 'success': Check if task.success is True")
    print("  - regex pattern: Check if output matches regex")
    print("  - named validator: Use registered callback")
    print("  - custom callback: Pass function directly")


async def example_delegation_strategies():
    """Example 5: Different delegation strategies."""
    print("\n" + "=" * 60)
    print("Example 5: Delegation Strategies")
    print("=" * 60)

    workers = ["worker-1", "worker-2", "worker-3"]

    strategies = [
        (DelegationStrategy.ROLE_BASED, "Select workers matching required role"),
        (DelegationStrategy.ROUND_ROBIN, "Cycle through workers evenly"),
        (DelegationStrategy.RANDOM, "Random worker selection"),
        (DelegationStrategy.PRIORITY, "Use worker list order as priority"),
        (DelegationStrategy.LEAST_BUSY, "Select worker with fewest tasks (future)"),
    ]

    print("\nAvailable strategies:")
    for strategy, desc in strategies:
        print(f"  - {strategy.value}: {desc}")

    # Demo round-robin
    print("\nRound-robin demonstration:")
    manager = ManagerAgent(
        name="rr-manager",
        workers=workers,
        delegation_strategy=DelegationStrategy.ROUND_ROBIN
    )

    for i in range(5):
        selected = await manager.select_worker()
        print(f"  Task {i+1} -> {selected}")


async def example_manager_registry():
    """Example 6: Managing multiple managers."""
    print("\n" + "=" * 60)
    print("Example 6: Manager Registry")
    print("=" * 60)

    registry = ManagerRegistry()

    # Create specialized managers
    build_manager = registry.create_manager(
        name="build-orchestrator",
        workers=["builder-1", "builder-2"],
        worker_roles={
            "builder-1": SessionRole.BUILDER,
            "builder-2": SessionRole.BUILDER,
        }
    )

    test_manager = registry.create_manager(
        name="test-orchestrator",
        workers=["tester-1", "tester-2"],
        worker_roles={
            "tester-1": SessionRole.TESTER,
            "tester-2": SessionRole.REVIEWER,
        }
    )

    deploy_manager = registry.create_manager(
        name="deploy-orchestrator",
        workers=["deployer"],
        worker_roles={
            "deployer": SessionRole.DEVOPS,
        }
    )

    print(f"\nRegistered {len(registry.list_managers())} managers:")
    for manager in registry.list_managers():
        print(f"  - {manager.name}: {len(manager.workers)} workers")

    # Find manager for a worker
    worker = "builder-1"
    manager = registry.get_manager_for_worker(worker)
    print(f"\nManager for '{worker}': {manager.name if manager else 'None'}")


async def example_full_workflow():
    """Example 7: Complete workflow with iTerm integration."""
    print("\n" + "=" * 60)
    print("Example 7: Full Workflow (requires iTerm2)")
    print("=" * 60)

    print("""
To run the full workflow with iTerm2 integration:

1. Start iTerm2 and enable the Python API
2. Run this script in iTerm2's Scripts menu

The workflow will:
1. Create a QUAD layout with 4 panes
2. Register agents for each pane (builder, tester, reviewer, monitor)
3. Create a ManagerAgent to orchestrate them
4. Execute a build-test-deploy plan
5. Display results in the monitor pane

Example code:

    # Connect to iTerm2
    connection = await iterm2.Connection.async_create()
    terminal = ItermTerminal(connection)
    await terminal.initialize()

    # Create layout and register agents
    layout_manager = LayoutManager(terminal)
    await layout_manager.create_layout(
        layout_type=LayoutType.QUAD,
        pane_names=["Builder", "Tester", "Reviewer", "Monitor"]
    )

    # Set up agent registry
    agent_registry = AgentRegistry()
    # ... register agents ...

    # Create manager registry with execution callback
    manager_registry = ManagerRegistry()
    execute_callback = await mock_execute_task(terminal, agent_registry)
    manager_registry.set_callbacks(execute_callback)

    # Create orchestrator
    orchestrator = manager_registry.create_manager(
        name="ci-orchestrator",
        workers=["builder-agent", "test-agent", "review-agent"],
        worker_roles={
            "builder-agent": SessionRole.BUILDER,
            "test-agent": SessionRole.TESTER,
            "review-agent": SessionRole.REVIEWER,
        }
    )

    # Execute plan
    plan = TaskPlan(
        name="ci-pipeline",
        steps=[
            TaskStep(id="build", task="npm run build", role=SessionRole.BUILDER),
            TaskStep(id="test", task="npm test", role=SessionRole.TESTER, depends_on=["build"]),
            TaskStep(id="review", task="./scripts/code-review.sh", role=SessionRole.REVIEWER, depends_on=["test"]),
        ]
    )

    result = await orchestrator.orchestrate(plan)
    print(f"Plan completed: {'success' if result.success else 'failed'}")
    """)


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Hierarchical Task Delegation Examples")
    print("=" * 60)

    await example_simple_delegation()
    await example_plan_orchestration()
    await example_parallel_execution()
    await example_validation_callbacks()
    await example_delegation_strategies()
    await example_manager_registry()
    await example_full_workflow()

    print("\n" + "=" * 60)
    print("All examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
