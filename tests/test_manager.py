"""Tests for hierarchical task delegation with manager agents."""

import asyncio
import re
import shutil
import tempfile
import unittest
from typing import List, Optional, Tuple

from core.manager import (
    SessionRole,
    TaskStatus,
    TaskResult,
    TaskStep,
    TaskPlan,
    PlanResult,
    DelegationStrategy,
    ManagerAgent,
    ManagerRegistry,
    create_regex_validator,
    create_success_validator,
    ValidationCallback,
)


class TestSessionRole(unittest.TestCase):
    """Test SessionRole enum."""

    def test_role_values(self):
        """Test that all expected roles exist."""
        self.assertEqual(SessionRole.BUILDER.value, "builder")
        self.assertEqual(SessionRole.TESTER.value, "tester")
        self.assertEqual(SessionRole.DEVOPS.value, "devops")
        self.assertEqual(SessionRole.REVIEWER.value, "reviewer")
        self.assertEqual(SessionRole.RESEARCHER.value, "researcher")
        self.assertEqual(SessionRole.WRITER.value, "writer")
        self.assertEqual(SessionRole.ANALYST.value, "analyst")
        self.assertEqual(SessionRole.COORDINATOR.value, "coordinator")
        self.assertEqual(SessionRole.GENERAL.value, "general")


class TestTaskResult(unittest.TestCase):
    """Test TaskResult model."""

    def test_task_result_creation(self):
        """Test creating a basic task result."""
        result = TaskResult(
            task_id="task-1",
            task="npm run build",
            worker="build-agent"
        )
        self.assertEqual(result.task_id, "task-1")
        self.assertEqual(result.task, "npm run build")
        self.assertEqual(result.worker, "build-agent")
        self.assertEqual(result.status, TaskStatus.PENDING)
        self.assertFalse(result.success)

    def test_mark_started(self):
        """Test marking task as started."""
        result = TaskResult(task_id="task-1", task="test", worker="agent-1")
        result.mark_started()

        self.assertEqual(result.status, TaskStatus.IN_PROGRESS)
        self.assertIsNotNone(result.started_at)

    def test_mark_completed_success(self):
        """Test marking task as completed successfully."""
        result = TaskResult(task_id="task-1", task="test", worker="agent-1")
        result.mark_started()
        result.mark_completed(success=True, output="Build successful")

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertTrue(result.success)
        self.assertEqual(result.output, "Build successful")
        self.assertIsNotNone(result.completed_at)
        self.assertIsNotNone(result.duration_seconds)

    def test_mark_completed_failure(self):
        """Test marking task as completed with failure."""
        result = TaskResult(task_id="task-1", task="test", worker="agent-1")
        result.mark_started()
        result.mark_completed(success=False, error="Build failed")

        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Build failed")

    def test_mark_validation_result(self):
        """Test recording validation result."""
        result = TaskResult(task_id="task-1", task="test", worker="agent-1")
        result.mark_started()
        result.mark_completed(success=True, output="output")
        result.mark_validation_result(passed=False, message="Validation failed")

        self.assertEqual(result.status, TaskStatus.VALIDATION_FAILED)
        self.assertFalse(result.validation_passed)
        self.assertEqual(result.validation_message, "Validation failed")


class TestTaskStep(unittest.TestCase):
    """Test TaskStep model."""

    def test_task_step_creation(self):
        """Test creating a basic task step."""
        step = TaskStep(id="step-1", task="npm install")
        self.assertEqual(step.id, "step-1")
        self.assertEqual(step.task, "npm install")
        self.assertIsNone(step.role)
        self.assertFalse(step.optional)
        self.assertEqual(step.depends_on, [])

    def test_task_step_with_role(self):
        """Test creating a step with role requirement."""
        step = TaskStep(
            id="build-step",
            task="npm run build",
            role=SessionRole.BUILDER,
            timeout_seconds=300
        )
        self.assertEqual(step.role, SessionRole.BUILDER)
        self.assertEqual(step.timeout_seconds, 300)

    def test_task_step_with_dependencies(self):
        """Test creating a step with dependencies."""
        step = TaskStep(
            id="test-step",
            task="npm test",
            depends_on=["build-step", "lint-step"]
        )
        self.assertIn("build-step", step.depends_on)
        self.assertIn("lint-step", step.depends_on)

    def test_task_step_validation_pattern(self):
        """Test step with regex validation pattern."""
        step = TaskStep(
            id="test-step",
            task="npm test",
            validation=r"All \d+ tests passed"
        )
        self.assertEqual(step.validation, r"All \d+ tests passed")

    def test_task_step_invalid_regex(self):
        """Test that invalid regex patterns are rejected."""
        with self.assertRaises(ValueError):
            TaskStep(id="test", task="test", validation="[invalid")


class TestTaskPlan(unittest.TestCase):
    """Test TaskPlan model."""

    def test_task_plan_creation(self):
        """Test creating a basic task plan."""
        steps = [
            TaskStep(id="step-1", task="task 1"),
            TaskStep(id="step-2", task="task 2"),
        ]
        plan = TaskPlan(name="test-plan", steps=steps)

        self.assertEqual(plan.name, "test-plan")
        self.assertEqual(len(plan.steps), 2)
        self.assertTrue(plan.stop_on_failure)

    def test_get_step(self):
        """Test retrieving step by ID."""
        steps = [
            TaskStep(id="step-1", task="task 1"),
            TaskStep(id="step-2", task="task 2"),
        ]
        plan = TaskPlan(name="test-plan", steps=steps)

        step = plan.get_step("step-1")
        self.assertIsNotNone(step)
        self.assertEqual(step.task, "task 1")

        self.assertIsNone(plan.get_step("nonexistent"))

    def test_get_execution_order_sequential(self):
        """Test execution order for sequential steps."""
        steps = [
            TaskStep(id="step-1", task="task 1"),
            TaskStep(id="step-2", task="task 2"),
            TaskStep(id="step-3", task="task 3"),
        ]
        plan = TaskPlan(name="test-plan", steps=steps)

        order = plan.get_execution_order()
        self.assertEqual(len(order), 3)
        self.assertEqual(order[0], ["step-1"])
        self.assertEqual(order[1], ["step-2"])
        self.assertEqual(order[2], ["step-3"])

    def test_get_execution_order_parallel(self):
        """Test execution order with parallel groups."""
        steps = [
            TaskStep(id="step-1", task="task 1"),
            TaskStep(id="step-2", task="task 2"),
            TaskStep(id="step-3", task="task 3"),
        ]
        plan = TaskPlan(
            name="test-plan",
            steps=steps,
            parallel_groups=[["step-1", "step-2"], ["step-3"]]
        )

        order = plan.get_execution_order()
        self.assertEqual(len(order), 2)
        self.assertEqual(order[0], ["step-1", "step-2"])
        self.assertEqual(order[1], ["step-3"])

    def test_validate_dependencies_valid(self):
        """Test dependency validation with valid plan."""
        steps = [
            TaskStep(id="step-1", task="task 1"),
            TaskStep(id="step-2", task="task 2", depends_on=["step-1"]),
            TaskStep(id="step-3", task="task 3", depends_on=["step-1", "step-2"]),
        ]
        plan = TaskPlan(name="test-plan", steps=steps)

        errors = plan.validate_dependencies()
        self.assertEqual(errors, [])

    def test_validate_dependencies_missing(self):
        """Test dependency validation with missing dependency."""
        steps = [
            TaskStep(id="step-1", task="task 1", depends_on=["nonexistent"]),
        ]
        plan = TaskPlan(name="test-plan", steps=steps)

        errors = plan.validate_dependencies()
        self.assertEqual(len(errors), 1)
        self.assertIn("nonexistent", errors[0])


class TestValidators(unittest.TestCase):
    """Test validation callback creation."""

    def test_regex_validator_match(self):
        """Test regex validator with matching output."""
        validator = create_regex_validator(r"success|passed")
        result = TaskResult(
            task_id="t1", task="test", worker="a1",
            output="All tests passed"
        )

        passed, message = validator(result)
        self.assertTrue(passed)

    def test_regex_validator_no_match(self):
        """Test regex validator with non-matching output."""
        validator = create_regex_validator(r"success")
        result = TaskResult(
            task_id="t1", task="test", worker="a1",
            output="Build failed"
        )

        passed, message = validator(result)
        self.assertFalse(passed)

    def test_regex_validator_no_output(self):
        """Test regex validator with no output."""
        validator = create_regex_validator(r"success")
        result = TaskResult(task_id="t1", task="test", worker="a1")

        passed, message = validator(result)
        self.assertFalse(passed)
        self.assertIn("No output", message)

    def test_success_validator_success(self):
        """Test success validator with successful result."""
        validator = create_success_validator()
        result = TaskResult(
            task_id="t1", task="test", worker="a1",
            success=True
        )

        passed, message = validator(result)
        self.assertTrue(passed)

    def test_success_validator_failure(self):
        """Test success validator with failed result."""
        validator = create_success_validator()
        result = TaskResult(
            task_id="t1", task="test", worker="a1",
            success=False, error="Something broke"
        )

        passed, message = validator(result)
        self.assertFalse(passed)
        self.assertIn("Something broke", message)


class TestManagerAgent(unittest.TestCase):
    """Test ManagerAgent class."""

    def test_manager_creation(self):
        """Test creating a basic manager."""
        manager = ManagerAgent(name="test-manager")
        self.assertEqual(manager.name, "test-manager")
        self.assertEqual(manager.workers, [])
        self.assertEqual(manager.strategy, DelegationStrategy.ROLE_BASED)

    def test_manager_with_workers(self):
        """Test creating manager with workers."""
        manager = ManagerAgent(
            name="build-manager",
            workers=["builder-1", "tester-1"],
            worker_roles={
                "builder-1": SessionRole.BUILDER,
                "tester-1": SessionRole.TESTER,
            }
        )
        self.assertIn("builder-1", manager.workers)
        self.assertIn("tester-1", manager.workers)
        self.assertEqual(manager.worker_roles["builder-1"], SessionRole.BUILDER)

    def test_add_worker(self):
        """Test adding a worker to manager."""
        manager = ManagerAgent(name="test-manager")
        manager.add_worker("new-worker", role=SessionRole.BUILDER)

        self.assertIn("new-worker", manager.workers)
        self.assertEqual(manager.worker_roles["new-worker"], SessionRole.BUILDER)

    def test_add_worker_no_duplicate(self):
        """Test that adding same worker twice doesn't duplicate."""
        manager = ManagerAgent(name="test-manager")
        manager.add_worker("worker-1")
        manager.add_worker("worker-1")

        self.assertEqual(manager.workers.count("worker-1"), 1)

    def test_remove_worker(self):
        """Test removing a worker from manager."""
        manager = ManagerAgent(
            name="test-manager",
            workers=["worker-1", "worker-2"],
            worker_roles={"worker-1": SessionRole.BUILDER}
        )

        result = manager.remove_worker("worker-1")
        self.assertTrue(result)
        self.assertNotIn("worker-1", manager.workers)
        self.assertNotIn("worker-1", manager.worker_roles)

        # Remove non-existent worker
        result = manager.remove_worker("nonexistent")
        self.assertFalse(result)

    def test_get_workers_by_role(self):
        """Test filtering workers by role."""
        manager = ManagerAgent(
            name="test-manager",
            workers=["b1", "b2", "t1"],
            worker_roles={
                "b1": SessionRole.BUILDER,
                "b2": SessionRole.BUILDER,
                "t1": SessionRole.TESTER,
            }
        )

        builders = manager.get_workers_by_role(SessionRole.BUILDER)
        self.assertEqual(len(builders), 2)
        self.assertIn("b1", builders)
        self.assertIn("b2", builders)

        testers = manager.get_workers_by_role(SessionRole.TESTER)
        self.assertEqual(len(testers), 1)
        self.assertIn("t1", testers)

    def test_set_worker_role(self):
        """Test setting worker role."""
        manager = ManagerAgent(name="test-manager", workers=["worker-1"])
        manager.set_worker_role("worker-1", SessionRole.DEVOPS)

        self.assertEqual(manager.worker_roles["worker-1"], SessionRole.DEVOPS)

    def test_register_validator(self):
        """Test registering custom validator."""
        manager = ManagerAgent(name="test-manager")

        def custom_validator(result: TaskResult) -> Tuple[bool, Optional[str]]:
            return result.success, "Custom check"

        manager.register_validator("custom", custom_validator)
        self.assertIn("custom", manager._validators)

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        manager = ManagerAgent(
            name="test-manager",
            workers=["worker-1", "worker-2"],
            delegation_strategy=DelegationStrategy.ROUND_ROBIN,
            worker_roles={"worker-1": SessionRole.BUILDER},
            metadata={"key": "value"}
        )

        data = manager.to_dict()
        restored = ManagerAgent.from_dict(data)

        self.assertEqual(restored.name, manager.name)
        self.assertEqual(restored.workers, manager.workers)
        self.assertEqual(restored.strategy, DelegationStrategy.ROUND_ROBIN)
        self.assertEqual(restored.worker_roles["worker-1"], SessionRole.BUILDER)


class TestManagerAgentAsync(unittest.TestCase):
    """Test async methods of ManagerAgent."""

    def setUp(self):
        """Create manager with test workers."""
        self.manager = ManagerAgent(
            name="test-manager",
            workers=["builder-1", "builder-2", "tester-1"],
            worker_roles={
                "builder-1": SessionRole.BUILDER,
                "builder-2": SessionRole.BUILDER,
                "tester-1": SessionRole.TESTER,
            }
        )

    def test_select_worker_role_based(self):
        """Test worker selection with role-based strategy."""
        async def run_test():
            worker = await self.manager.select_worker(required_role=SessionRole.BUILDER)
            self.assertIn(worker, ["builder-1", "builder-2"])

            worker = await self.manager.select_worker(required_role=SessionRole.TESTER)
            self.assertEqual(worker, "tester-1")

        asyncio.run(run_test())

    def test_select_worker_round_robin(self):
        """Test worker selection with round-robin strategy."""
        self.manager.strategy = DelegationStrategy.ROUND_ROBIN

        async def run_test():
            # Should cycle through workers
            selected = []
            for _ in range(4):
                worker = await self.manager.select_worker()
                selected.append(worker)

            # Should have seen at least 2 different workers
            self.assertGreater(len(set(selected)), 1)

        asyncio.run(run_test())

    def test_select_worker_with_exclusion(self):
        """Test worker selection with exclusion list."""
        async def run_test():
            worker = await self.manager.select_worker(
                required_role=SessionRole.BUILDER,
                exclude=["builder-1"]
            )
            self.assertEqual(worker, "builder-2")

        asyncio.run(run_test())

    def test_select_worker_no_candidates(self):
        """Test worker selection when no candidates available."""
        async def run_test():
            worker = await self.manager.select_worker(
                required_role=SessionRole.DEVOPS  # No devops workers
            )
            self.assertIsNone(worker)

        asyncio.run(run_test())

    def test_execute_on_worker_no_callback(self):
        """Test executing task without callback configured."""
        async def run_test():
            result = await self.manager.execute_on_worker("builder-1", "npm run build")

            self.assertFalse(result.success)
            self.assertIn("not integrated", result.error)

        asyncio.run(run_test())

    def test_execute_on_worker_with_callback(self):
        """Test executing task with callback."""
        async def mock_execute(worker, task, timeout):
            return f"Output from {worker}", True, None

        self.manager._execute_callback = mock_execute

        async def run_test():
            result = await self.manager.execute_on_worker("builder-1", "npm run build")

            self.assertTrue(result.success)
            self.assertEqual(result.output, "Output from builder-1")
            self.assertEqual(result.worker, "builder-1")

        asyncio.run(run_test())

    def test_validate_result_success_keyword(self):
        """Test validation with 'success' keyword."""
        async def run_test():
            result = TaskResult(task_id="t1", task="test", worker="a1", success=True)
            passed, msg = await self.manager.validate_result(result, "success")
            self.assertTrue(passed)

            result.success = False
            passed, msg = await self.manager.validate_result(result, "success")
            self.assertFalse(passed)

        asyncio.run(run_test())

    def test_validate_result_regex(self):
        """Test validation with regex pattern."""
        async def run_test():
            result = TaskResult(
                task_id="t1", task="test", worker="a1",
                success=True, output="Build completed successfully"
            )
            passed, msg = await self.manager.validate_result(result, r"successfully")
            self.assertTrue(passed)

        asyncio.run(run_test())

    def test_validate_result_named_validator(self):
        """Test validation with named validator."""
        def always_pass(result):
            return True, "Always passes"

        self.manager.register_validator("always_pass", always_pass)

        async def run_test():
            result = TaskResult(task_id="t1", task="test", worker="a1")
            passed, msg = await self.manager.validate_result(result, "always_pass")
            self.assertTrue(passed)

        asyncio.run(run_test())

    def test_delegate_no_workers(self):
        """Test delegation when no workers available."""
        manager = ManagerAgent(name="empty-manager")

        async def run_test():
            result = await manager.delegate("some task")

            self.assertFalse(result.success)
            self.assertIn("No available worker", result.error)

        asyncio.run(run_test())

    def test_delegate_with_retries(self):
        """Test delegation with retry on failure."""
        attempt_count = 0

        async def mock_execute(worker, task, timeout):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                return None, False, "First attempt fails"
            return "Success", True, None

        self.manager._execute_callback = mock_execute

        async def run_test():
            result = await self.manager.delegate(
                "test task",
                retry_count=2
            )

            self.assertTrue(result.success)
            self.assertEqual(attempt_count, 2)

        asyncio.run(run_test())


class TestManagerAgentOrchestration(unittest.TestCase):
    """Test plan orchestration in ManagerAgent."""

    def setUp(self):
        """Create manager with mock execution."""
        self.manager = ManagerAgent(
            name="orchestrator",
            workers=["worker-1", "worker-2"],
            worker_roles={
                "worker-1": SessionRole.GENERAL,
                "worker-2": SessionRole.GENERAL,
            }
        )

        self.execution_log = []

        async def mock_execute(worker, task, timeout):
            self.execution_log.append({"worker": worker, "task": task})
            return f"Executed: {task}", True, None

        self.manager._execute_callback = mock_execute

    def test_orchestrate_simple_plan(self):
        """Test orchestrating a simple sequential plan."""
        plan = TaskPlan(
            name="simple-plan",
            steps=[
                TaskStep(id="step-1", task="task 1"),
                TaskStep(id="step-2", task="task 2"),
            ]
        )

        async def run_test():
            result = await self.manager.orchestrate(plan)

            self.assertTrue(result.success)
            self.assertEqual(len(result.results), 2)
            self.assertEqual(self.execution_log[0]["task"], "task 1")
            self.assertEqual(self.execution_log[1]["task"], "task 2")

        asyncio.run(run_test())

    def test_orchestrate_plan_with_failure(self):
        """Test plan stops on failure when stop_on_failure is True."""
        async def failing_execute(worker, task, timeout):
            if "fail" in task:
                return None, False, "Intentional failure"
            return "Success", True, None

        self.manager._execute_callback = failing_execute

        plan = TaskPlan(
            name="failing-plan",
            steps=[
                TaskStep(id="step-1", task="task 1"),
                TaskStep(id="step-2", task="fail this"),
                TaskStep(id="step-3", task="task 3"),  # Should not execute
            ],
            stop_on_failure=True
        )

        async def run_test():
            result = await self.manager.orchestrate(plan)

            self.assertFalse(result.success)
            self.assertTrue(result.stopped_early)
            self.assertIn("step-2", result.stop_reason)

            # Only 2 steps should have results (step-3 never started)
            executed_ids = [r.task_id for r in result.results]
            self.assertIn("step-1", executed_ids)
            self.assertIn("step-2", executed_ids)

        asyncio.run(run_test())

    def test_orchestrate_optional_step_failure(self):
        """Test plan continues when optional step fails."""
        async def conditional_execute(worker, task, timeout):
            if "optional" in task:
                return None, False, "Optional failed"
            return "Success", True, None

        self.manager._execute_callback = conditional_execute

        plan = TaskPlan(
            name="optional-plan",
            steps=[
                TaskStep(id="step-1", task="task 1"),
                TaskStep(id="step-2", task="optional task", optional=True),
                TaskStep(id="step-3", task="task 3"),
            ],
            stop_on_failure=True
        )

        async def run_test():
            result = await self.manager.orchestrate(plan)

            # Plan should succeed because failed step was optional
            self.assertTrue(result.success)
            self.assertFalse(result.stopped_early)
            self.assertEqual(len(result.results), 3)

        asyncio.run(run_test())

    def test_orchestrate_with_dependencies(self):
        """Test plan respects step dependencies."""
        plan = TaskPlan(
            name="dep-plan",
            steps=[
                TaskStep(id="install", task="npm install"),
                TaskStep(id="build", task="npm build", depends_on=["install"]),
                TaskStep(id="test", task="npm test", depends_on=["build"]),
            ]
        )

        async def run_test():
            result = await self.manager.orchestrate(plan)

            self.assertTrue(result.success)
            # Verify execution order
            tasks = [log["task"] for log in self.execution_log]
            self.assertEqual(tasks.index("npm install"), 0)
            self.assertLess(tasks.index("npm install"), tasks.index("npm build"))
            self.assertLess(tasks.index("npm build"), tasks.index("npm test"))

        asyncio.run(run_test())

    def test_orchestrate_invalid_dependencies(self):
        """Test plan with invalid dependencies fails validation."""
        plan = TaskPlan(
            name="invalid-plan",
            steps=[
                TaskStep(id="step-1", task="task", depends_on=["nonexistent"]),
            ]
        )

        async def run_test():
            result = await self.manager.orchestrate(plan)

            self.assertFalse(result.success)
            self.assertTrue(result.stopped_early)
            self.assertIn("Invalid plan", result.stop_reason)

        asyncio.run(run_test())

    def test_orchestrate_from_step_list(self):
        """Test orchestrating from a list of steps."""
        steps = [
            TaskStep(id="s1", task="task 1"),
            TaskStep(id="s2", task="task 2"),
        ]

        async def run_test():
            result = await self.manager.orchestrate(steps)

            self.assertTrue(result.success)
            self.assertEqual(len(result.results), 2)

        asyncio.run(run_test())


class TestManagerRegistry(unittest.TestCase):
    """Test ManagerRegistry class."""

    def setUp(self):
        """Create a fresh registry for each test."""
        self.registry = ManagerRegistry()

    def test_create_manager(self):
        """Test creating a manager through registry."""
        manager = self.registry.create_manager(
            name="test-manager",
            workers=["worker-1"],
            delegation_strategy=DelegationStrategy.ROUND_ROBIN
        )

        self.assertEqual(manager.name, "test-manager")
        self.assertIn("worker-1", manager.workers)
        self.assertEqual(manager.strategy, DelegationStrategy.ROUND_ROBIN)

    def test_get_manager(self):
        """Test retrieving a manager by name."""
        self.registry.create_manager(name="my-manager")

        manager = self.registry.get_manager("my-manager")
        self.assertIsNotNone(manager)
        self.assertEqual(manager.name, "my-manager")

        self.assertIsNone(self.registry.get_manager("nonexistent"))

    def test_remove_manager(self):
        """Test removing a manager."""
        self.registry.create_manager(name="temp-manager")

        result = self.registry.remove_manager("temp-manager")
        self.assertTrue(result)
        self.assertIsNone(self.registry.get_manager("temp-manager"))

        # Remove non-existent
        result = self.registry.remove_manager("nonexistent")
        self.assertFalse(result)

    def test_list_managers(self):
        """Test listing all managers."""
        self.registry.create_manager(name="manager-1")
        self.registry.create_manager(name="manager-2")
        self.registry.create_manager(name="manager-3")

        managers = self.registry.list_managers()
        self.assertEqual(len(managers), 3)
        names = [m.name for m in managers]
        self.assertIn("manager-1", names)
        self.assertIn("manager-2", names)
        self.assertIn("manager-3", names)

    def test_get_manager_for_worker(self):
        """Test finding manager for a worker."""
        self.registry.create_manager(
            name="manager-a",
            workers=["worker-1", "worker-2"]
        )
        self.registry.create_manager(
            name="manager-b",
            workers=["worker-3"]
        )

        manager = self.registry.get_manager_for_worker("worker-2")
        self.assertIsNotNone(manager)
        self.assertEqual(manager.name, "manager-a")

        manager = self.registry.get_manager_for_worker("worker-3")
        self.assertEqual(manager.name, "manager-b")

        manager = self.registry.get_manager_for_worker("unknown-worker")
        self.assertIsNone(manager)

    def test_set_callbacks_propagates(self):
        """Test that setting callbacks propagates to all managers."""
        self.registry.create_manager(name="manager-1")
        self.registry.create_manager(name="manager-2")

        async def mock_execute(worker, task, timeout):
            return "output", True, None

        self.registry.set_callbacks(mock_execute)

        # Both managers should have the callback
        for manager in self.registry.list_managers():
            self.assertIsNotNone(manager._execute_callback)

    def test_new_manager_gets_callbacks(self):
        """Test that new managers get existing callbacks."""
        async def mock_execute(worker, task, timeout):
            return "output", True, None

        self.registry.set_callbacks(mock_execute)

        # Create manager after setting callbacks
        manager = self.registry.create_manager(name="new-manager")
        self.assertIsNotNone(manager._execute_callback)


class TestPlanResult(unittest.TestCase):
    """Test PlanResult model."""

    def test_plan_result_creation(self):
        """Test creating a plan result."""
        result = PlanResult(plan_name="test-plan")

        self.assertEqual(result.plan_name, "test-plan")
        self.assertFalse(result.success)
        self.assertEqual(result.results, [])

    def test_get_result_by_id(self):
        """Test retrieving task result by ID."""
        task_results = [
            TaskResult(task_id="task-1", task="t1", worker="w1"),
            TaskResult(task_id="task-2", task="t2", worker="w2"),
        ]
        result = PlanResult(plan_name="test-plan", results=task_results)

        task_result = result.get_result("task-1")
        self.assertIsNotNone(task_result)
        self.assertEqual(task_result.task, "t1")

        self.assertIsNone(result.get_result("nonexistent"))


if __name__ == "__main__":
    unittest.main()
