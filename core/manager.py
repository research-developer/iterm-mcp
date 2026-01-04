"""Manager Agent for hierarchical task delegation.

This module implements hierarchical task delegation where manager agents coordinate
planning and validation, delegating specific tasks to specialist agents.

Inspired by:
- CrewAI: Manager agent coordinates planning, validates results before proceeding
- AutoGen: GroupChatManager orchestrates multi-agent conversations
- Agency Swarm: CEO > Developer > VA hierarchy with explicit flows
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ============================================================================
# SESSION ROLE ENUM
# ============================================================================

class SessionRole(str, Enum):
    """Defines roles for specialized agents."""

    BUILDER = "builder"
    TESTER = "tester"
    DEVOPS = "devops"
    REVIEWER = "reviewer"
    RESEARCHER = "researcher"
    WRITER = "writer"
    ANALYST = "analyst"
    COORDINATOR = "coordinator"
    GENERAL = "general"


# ============================================================================
# TASK RESULT MODELS
# ============================================================================

class TaskStatus(str, Enum):
    """Status of a task execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    VALIDATION_FAILED = "validation_failed"


class TaskResult(BaseModel):
    """Result of a single task execution."""

    task_id: str = Field(..., description="Unique identifier for this task")
    task: str = Field(..., description="The task description that was executed")
    worker: str = Field(..., description="Agent name that executed the task")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Task execution status")
    success: bool = Field(default=False, description="Whether the task succeeded")
    output: Optional[str] = Field(default=None, description="Output from the task execution")
    error: Optional[str] = Field(default=None, description="Error message if task failed")
    started_at: Optional[datetime] = Field(default=None, description="When task execution started")
    completed_at: Optional[datetime] = Field(default=None, description="When task execution completed")
    duration_seconds: Optional[float] = Field(default=None, description="Execution duration in seconds")
    validation_passed: Optional[bool] = Field(default=None, description="Whether validation passed")
    validation_message: Optional[str] = Field(default=None, description="Validation result message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def mark_started(self) -> None:
        """Mark task as started."""
        self.started_at = datetime.now(timezone.utc)
        self.status = TaskStatus.IN_PROGRESS

    def mark_completed(self, success: bool, output: Optional[str] = None, error: Optional[str] = None) -> None:
        """Mark task as completed."""
        self.completed_at = datetime.now(timezone.utc)
        self.success = success
        self.output = output
        self.error = error
        self.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED

        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def mark_validation_result(self, passed: bool, message: Optional[str] = None) -> None:
        """Record validation result."""
        self.validation_passed = passed
        self.validation_message = message
        if not passed:
            self.status = TaskStatus.VALIDATION_FAILED


# ============================================================================
# TASK STEP AND PLAN MODELS
# ============================================================================

class TaskStep(BaseModel):
    """A single step in a task plan."""

    id: str = Field(..., description="Unique step identifier")
    task: str = Field(..., description="Task description to execute")
    role: Optional[SessionRole] = Field(default=None, description="Required worker role")
    optional: bool = Field(default=False, description="Whether failure should stop the plan")
    depends_on: List[str] = Field(default_factory=list, description="Step IDs this depends on")
    validation: Optional[str] = Field(
        default=None,
        description="Regex pattern to validate output, or 'success' for status check"
    )
    timeout_seconds: Optional[int] = Field(default=None, description="Max execution time")
    retry_count: int = Field(default=0, description="Number of retries on failure")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional step metadata")

    @field_validator('validation', mode='before')
    @classmethod
    def validate_regex(cls, v):
        """Validate that validation pattern is valid regex or special keyword."""
        if v is not None and v != 'success':
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        return v


class TaskPlan(BaseModel):
    """A multi-step execution plan."""

    name: str = Field(..., description="Plan name")
    description: Optional[str] = Field(default=None, description="Plan description")
    steps: List[TaskStep] = Field(..., description="Steps to execute")
    parallel_groups: List[List[str]] = Field(
        default_factory=list,
        description="Groups of step IDs that can run in parallel"
    )
    stop_on_failure: bool = Field(
        default=True,
        description="Stop plan on first non-optional failure"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional plan metadata")

    def get_step(self, step_id: str) -> Optional[TaskStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_execution_order(self) -> List[List[str]]:
        """Get steps organized by execution order (parallel groups or sequential).

        Returns a list of lists, where each inner list contains step IDs
        that can execute in parallel.
        """
        if self.parallel_groups:
            return self.parallel_groups

        # If no parallel groups defined, execute sequentially
        return [[step.id] for step in self.steps]

    def validate_dependencies(self) -> List[str]:
        """Validate that all dependencies exist and there are no cycles.

        Returns list of error messages (empty if valid).
        """
        errors = []
        step_ids = {step.id for step in self.steps}

        for step in self.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(f"Step '{step.id}' depends on non-existent step '{dep}'")

        # Check for cycles using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(step_id: str) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)

            step = self.get_step(step_id)
            if step:
                for dep in step.depends_on:
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        return True

            rec_stack.discard(step_id)
            return False

        for step in self.steps:
            if step.id not in visited:
                if has_cycle(step.id):
                    errors.append(f"Circular dependency detected involving step '{step.id}'")
                    break

        return errors


class PlanResult(BaseModel):
    """Result of executing a complete plan."""

    plan_name: str = Field(..., description="Name of the executed plan")
    success: bool = Field(default=False, description="Whether the plan completed successfully")
    results: List[TaskResult] = Field(default_factory=list, description="Results for each step")
    started_at: Optional[datetime] = Field(default=None, description="When plan execution started")
    completed_at: Optional[datetime] = Field(default=None, description="When plan execution completed")
    duration_seconds: Optional[float] = Field(default=None, description="Total execution duration")
    stopped_early: bool = Field(default=False, description="Whether plan stopped before completing")
    stop_reason: Optional[str] = Field(default=None, description="Reason for early stop")

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Get result for a specific task."""
        for result in self.results:
            if result.task_id == task_id:
                return result
        return None


# ============================================================================
# DELEGATION STRATEGY
# ============================================================================

class DelegationStrategy(str, Enum):
    """Strategy for selecting workers."""

    ROUND_ROBIN = "round_robin"
    ROLE_BASED = "role_based"
    LEAST_BUSY = "least_busy"
    RANDOM = "random"
    PRIORITY = "priority"


# ============================================================================
# VALIDATION CALLBACK TYPE
# ============================================================================

# Validation callback: takes TaskResult, returns (passed: bool, message: str)
ValidationCallback = Callable[["TaskResult"], Tuple[bool, Optional[str]]]

# Async validation callback
AsyncValidationCallback = Callable[["TaskResult"], Awaitable[Tuple[bool, Optional[str]]]]


def create_regex_validator(pattern: str) -> ValidationCallback:
    """Create a validation callback from a regex pattern."""
    compiled = re.compile(pattern)

    def validator(result: "TaskResult") -> Tuple[bool, Optional[str]]:
        if result.output is None:
            return False, "No output to validate"
        if compiled.search(result.output):
            return True, f"Output matches pattern: {pattern}"
        return False, f"Output does not match pattern: {pattern}"

    return validator


def create_success_validator() -> ValidationCallback:
    """Create a validation callback that checks task success status."""
    def validator(result: "TaskResult") -> Tuple[bool, Optional[str]]:
        if result.success:
            return True, "Task completed successfully"
        return False, f"Task failed: {result.error or 'unknown error'}"

    return validator


# ============================================================================
# MANAGER AGENT
# ============================================================================

class ManagerAgent:
    """Agent that coordinates other agents through hierarchical task delegation.

    A ManagerAgent can:
    - Maintain a list of worker agents
    - Delegate tasks to appropriate workers based on role or strategy
    - Validate task results before proceeding
    - Execute multi-step plans with dependency handling
    - Track execution state and results

    Example:
        manager = ManagerAgent(
            name="build-orchestrator",
            workers=["build-agent", "test-agent", "deploy-agent"]
        )

        result = await manager.delegate(
            task="npm run build",
            required_role=SessionRole.BUILDER
        )
    """

    def __init__(
        self,
        name: str,
        workers: Optional[List[str]] = None,
        delegation_strategy: DelegationStrategy = DelegationStrategy.ROLE_BASED,
        worker_roles: Optional[Dict[str, SessionRole]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a manager agent.

        Args:
            name: Unique name for this manager
            workers: List of worker agent names
            delegation_strategy: Strategy for selecting workers
            worker_roles: Mapping of worker names to their roles
            metadata: Additional metadata for the manager
        """
        self.name = name
        self.workers = workers or []
        self.strategy = delegation_strategy
        self.worker_roles = worker_roles or {}
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)

        # Internal state
        self._round_robin_index = 0
        self._task_counter = 0
        self._validators: Dict[str, ValidationCallback] = {}

        # Callbacks - set by the registry when integrated
        self._execute_callback: Optional[Callable] = None
        self._read_output_callback: Optional[Callable] = None

    def add_worker(self, worker_name: str, role: Optional[SessionRole] = None) -> None:
        """Add a worker to this manager."""
        if worker_name not in self.workers:
            self.workers.append(worker_name)
        if role:
            self.worker_roles[worker_name] = role

    def remove_worker(self, worker_name: str) -> bool:
        """Remove a worker from this manager."""
        if worker_name in self.workers:
            self.workers.remove(worker_name)
            self.worker_roles.pop(worker_name, None)
            return True
        return False

    def set_worker_role(self, worker_name: str, role: SessionRole) -> None:
        """Set the role for a worker."""
        self.worker_roles[worker_name] = role

    def get_workers_by_role(self, role: SessionRole) -> List[str]:
        """Get all workers with the specified role."""
        return [w for w, r in self.worker_roles.items() if r == role and w in self.workers]

    def register_validator(self, name: str, callback: ValidationCallback) -> None:
        """Register a named validation callback."""
        self._validators[name] = callback

    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        self._task_counter += 1
        return f"{self.name}-task-{self._task_counter}"

    async def select_worker(
        self,
        required_role: Optional[SessionRole] = None,
        exclude: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Select a worker based on the delegation strategy.

        Args:
            required_role: If specified, only consider workers with this role
            exclude: Workers to exclude from selection

        Returns:
            Worker name, or None if no suitable worker found
        """
        exclude = exclude or []
        candidates = [w for w in self.workers if w not in exclude]

        # Filter by role if required
        if required_role:
            role_workers = self.get_workers_by_role(required_role)
            candidates = [w for w in candidates if w in role_workers]

            # If no workers with specific role, fall back to general workers
            if not candidates:
                general_workers = self.get_workers_by_role(SessionRole.GENERAL)
                candidates = [w for w in self.workers if w in general_workers and w not in exclude]

        if not candidates:
            return None

        # Select based on strategy
        if self.strategy == DelegationStrategy.ROUND_ROBIN:
            self._round_robin_index = self._round_robin_index % len(candidates)
            selected = candidates[self._round_robin_index]
            self._round_robin_index += 1
            return selected

        elif self.strategy == DelegationStrategy.ROLE_BASED:
            # Prefer workers with the required role, then general
            if required_role:
                role_workers = [w for w in candidates if self.worker_roles.get(w) == required_role]
                if role_workers:
                    return role_workers[0]
            return candidates[0]

        elif self.strategy == DelegationStrategy.RANDOM:
            import random
            return random.choice(candidates)

        elif self.strategy == DelegationStrategy.PRIORITY:
            # Use order in workers list as priority
            return candidates[0]

        else:
            return candidates[0] if candidates else None

    async def execute_on_worker(
        self,
        worker: str,
        task: str,
        timeout_seconds: Optional[int] = None,
    ) -> TaskResult:
        """Execute a task on a specific worker.

        Args:
            worker: Worker agent name
            task: Task/command to execute
            timeout_seconds: Optional timeout

        Returns:
            TaskResult with execution details
        """
        result = TaskResult(
            task_id=self._generate_task_id(),
            task=task,
            worker=worker,
        )
        result.mark_started()

        try:
            if self._execute_callback:
                # Use the provided callback to execute on the worker.
                # The callback is responsible for honoring timeout_seconds if applicable.
                output, success, error = await self._execute_callback(worker, task, timeout_seconds)
                result.mark_completed(success=success, output=output, error=error)
            else:
                # No callback configured - this is a stub for testing
                logger.warning(f"No execute callback configured for manager {self.name}")
                result.mark_completed(
                    success=False,
                    error="No execution callback configured for this manager"
                )
        except asyncio.TimeoutError:
            result.mark_completed(
                success=False,
                error=f"Task timed out after {timeout_seconds} seconds"
            )
        except Exception as e:
            logger.error(f"Error executing task on worker {worker}: {e}")
            result.mark_completed(success=False, error=str(e))

        return result

    async def validate_result(
        self,
        result: TaskResult,
        validation: Optional[Union[str, ValidationCallback]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate a task result.

        Args:
            result: The task result to validate
            validation: Regex pattern string, 'success', validator name, or callback

        Returns:
            Tuple of (passed, message)
        """
        if validation is None:
            return True, None

        # Handle string validation specifications
        if isinstance(validation, str):
            if validation == 'success':
                validator = create_success_validator()
            elif validation in self._validators:
                validator = self._validators[validation]
            else:
                # Assume it's a regex pattern
                validator = create_regex_validator(validation)
        else:
            validator = validation

        # Support both sync and async validators
        validation_result = validator(result)
        if asyncio.iscoroutine(validation_result):
            passed, message = await validation_result
        else:
            passed, message = validation_result
        result.mark_validation_result(passed, message)
        return passed, message

    async def delegate(
        self,
        task: str,
        required_role: Optional[SessionRole] = None,
        validation: Optional[Union[str, ValidationCallback]] = None,
        timeout_seconds: Optional[int] = None,
        retry_count: int = 0,
    ) -> TaskResult:
        """Delegate a task to an appropriate worker.

        Args:
            task: Task description/command to execute
            required_role: Required worker role
            validation: Validation specification (regex, 'success', callback)
            timeout_seconds: Optional timeout
            retry_count: Number of retries on failure

        Returns:
            TaskResult with execution and validation details
        """
        excluded_workers: List[str] = []
        result: Optional[TaskResult] = None

        for attempt in range(max(1, retry_count + 1)):
            # Select worker
            worker = await self.select_worker(required_role, exclude=excluded_workers)
            if not worker:
                logger.error(f"No available worker for task: {task}")
                return TaskResult(
                    task_id=self._generate_task_id(),
                    task=task,
                    worker="none",
                    status=TaskStatus.FAILED,
                    success=False,
                    error="No available worker for required role"
                )

            # Execute task
            result = await self.execute_on_worker(worker, task, timeout_seconds)

            # Validate if specified
            if validation and result.success:
                passed, message = await self.validate_result(result, validation)
                if not passed:
                    logger.warning(f"Validation failed for task {result.task_id}: {message}")
                    result.success = False
                    result.status = TaskStatus.VALIDATION_FAILED

            # If successful or no more retries, return
            if result.success or attempt >= retry_count:
                return result

            # Mark this worker as tried
            excluded_workers.append(worker)
            logger.info(f"Retrying task {task} (attempt {attempt + 2}/{retry_count + 1})")

        # Should never reach here, but handle gracefully
        if result is not None:
            return result
        # Fallback: return a failed result if somehow no attempts were made
        return TaskResult(
            task_id=self._generate_task_id(),
            task=task,
            worker="none",
            status=TaskStatus.FAILED,
            success=False,
            error="No execution attempts were made"
        )

    async def orchestrate(
        self,
        plan: Union[TaskPlan, List[TaskStep]],
    ) -> PlanResult:
        """Execute a multi-step plan.

        Args:
            plan: TaskPlan or list of TaskSteps to execute

        Returns:
            PlanResult with all execution results
        """
        # Convert list to plan if needed
        if isinstance(plan, list):
            plan = TaskPlan(
                name=f"{self.name}-plan",
                steps=plan,
            )

        # Validate dependencies
        errors = plan.validate_dependencies()
        if errors:
            return PlanResult(
                plan_name=plan.name,
                success=False,
                stopped_early=True,
                stop_reason=f"Invalid plan: {'; '.join(errors)}"
            )

        plan_result = PlanResult(
            plan_name=plan.name,
            started_at=datetime.now(timezone.utc),
        )

        completed_steps: Dict[str, TaskResult] = {}

        # Get execution order
        execution_order = plan.get_execution_order()

        for step_group in execution_order:
            # Filter steps that have all dependencies satisfied
            ready_steps = []
            for step_id in step_group:
                step = plan.get_step(step_id)
                if step:
                    # Check if all dependencies are completed successfully
                    deps_satisfied = all(
                        dep in completed_steps and completed_steps[dep].success
                        for dep in step.depends_on
                    )
                    if deps_satisfied:
                        ready_steps.append(step)
                    elif step.depends_on:
                        # Skip steps with failed dependencies
                        result = TaskResult(
                            task_id=step.id,
                            task=step.task,
                            worker="none",
                            status=TaskStatus.SKIPPED,
                            success=False,
                            error="Dependencies not satisfied"
                        )
                        plan_result.results.append(result)
                        completed_steps[step.id] = result

            if not ready_steps:
                continue

            # Execute steps in this group (could be parallelized)
            if len(ready_steps) > 1:
                # Execute in parallel
                tasks = [
                    self.delegate(
                        task=step.task,
                        required_role=step.role,
                        validation=step.validation,
                        timeout_seconds=step.timeout_seconds,
                        retry_count=step.retry_count,
                    )
                    for step in ready_steps
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for step, result in zip(ready_steps, results):
                    if isinstance(result, Exception):
                        task_result = TaskResult(
                            task_id=step.id,
                            task=step.task,
                            worker="none",
                            status=TaskStatus.FAILED,
                            success=False,
                            error=str(result)
                        )
                    else:
                        task_result = result
                        task_result.task_id = step.id

                    plan_result.results.append(task_result)
                    completed_steps[step.id] = task_result

                    # Check for plan failure
                    if not task_result.success and not step.optional and plan.stop_on_failure:
                        plan_result.stopped_early = True
                        plan_result.stop_reason = f"Step '{step.id}' failed: {task_result.error}"
                        break
            else:
                # Execute single step
                step = ready_steps[0]
                result = await self.delegate(
                    task=step.task,
                    required_role=step.role,
                    validation=step.validation,
                    timeout_seconds=step.timeout_seconds,
                    retry_count=step.retry_count,
                )
                result.task_id = step.id

                plan_result.results.append(result)
                completed_steps[step.id] = result

                # Check for plan failure
                if not result.success and not step.optional and plan.stop_on_failure:
                    plan_result.stopped_early = True
                    plan_result.stop_reason = f"Step '{step.id}' failed: {result.error}"

            # Stop if we hit a failure
            if plan_result.stopped_early:
                break

        # Complete the plan result
        plan_result.completed_at = datetime.now(timezone.utc)
        if plan_result.started_at:
            plan_result.duration_seconds = (
                plan_result.completed_at - plan_result.started_at
            ).total_seconds()

        # Determine overall success
        plan_result.success = not plan_result.stopped_early
        if plan_result.success:
            for r in plan_result.results:
                step = plan.get_step(r.task_id)
                if step is None:
                    # Skip results that do not correspond to a plan step
                    continue
                if not (r.success or step.optional):
                    plan_result.success = False
                    break

        return plan_result

    def to_dict(self) -> Dict[str, Any]:
        """Convert manager to dictionary for serialization."""
        return {
            "name": self.name,
            "workers": self.workers,
            "delegation_strategy": self.strategy.value,
            "worker_roles": {k: v.value for k, v in self.worker_roles.items()},
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManagerAgent":
        """Create manager from dictionary."""
        return cls(
            name=data["name"],
            workers=data.get("workers", []),
            delegation_strategy=DelegationStrategy(data.get("delegation_strategy", "role_based")),
            worker_roles={
                k: SessionRole(v) for k, v in data.get("worker_roles", {}).items()
            },
            metadata=data.get("metadata", {}),
        )


# ============================================================================
# MANAGER REGISTRY
# ============================================================================

class ManagerRegistry:
    """Registry for managing multiple ManagerAgents."""

    def __init__(self):
        self._managers: Dict[str, ManagerAgent] = {}
        self._execute_callback: Optional[Callable] = None
        self._read_output_callback: Optional[Callable] = None

    def set_callbacks(
        self,
        execute_callback: Callable,
        read_output_callback: Optional[Callable] = None,
    ) -> None:
        """Set callbacks for task execution.

        Args:
            execute_callback: Async callback (worker, task, timeout) -> (output, success, error)
            read_output_callback: Optional callback to read worker output
        """
        self._execute_callback = execute_callback
        self._read_output_callback = read_output_callback

        # Update existing managers
        for manager in self._managers.values():
            manager._execute_callback = execute_callback
            manager._read_output_callback = read_output_callback

    def create_manager(
        self,
        name: str,
        workers: Optional[List[str]] = None,
        delegation_strategy: DelegationStrategy = DelegationStrategy.ROLE_BASED,
        worker_roles: Optional[Dict[str, SessionRole]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ManagerAgent:
        """Create and register a new manager.

        Args:
            name: Unique manager name
            workers: List of worker agent names
            delegation_strategy: Strategy for selecting workers
            worker_roles: Mapping of worker names to their roles
            metadata: Additional metadata

        Returns:
            The created ManagerAgent
        """
        manager = ManagerAgent(
            name=name,
            workers=workers,
            delegation_strategy=delegation_strategy,
            worker_roles=worker_roles,
            metadata=metadata,
        )
        manager._execute_callback = self._execute_callback
        manager._read_output_callback = self._read_output_callback

        self._managers[name] = manager
        return manager

    def get_manager(self, name: str) -> Optional[ManagerAgent]:
        """Get a manager by name."""
        return self._managers.get(name)

    def remove_manager(self, name: str) -> bool:
        """Remove a manager. Returns True if removed."""
        if name in self._managers:
            del self._managers[name]
            return True
        return False

    def list_managers(self) -> List[ManagerAgent]:
        """List all registered managers."""
        return list(self._managers.values())

    def get_manager_for_worker(self, worker: str) -> Optional[ManagerAgent]:
        """Find which manager a worker belongs to."""
        for manager in self._managers.values():
            if worker in manager.workers:
                return manager
        return None
