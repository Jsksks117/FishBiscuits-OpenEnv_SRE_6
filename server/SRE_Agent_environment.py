# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
SRE Agent Environment Implementation.

A Docker-based sandbox environment where an AI agent must diagnose and fix
broken Linux server configurations. Each reset() spins up a fresh Ubuntu
container with an injected bug; step() runs the agent's bash commands.
"""

import logging
import re
import uuid

import docker

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import SreAgentAction, SreAgentObservation
    from ..tasks import TASK_DEFINITIONS, grade_task
    from .subprocess_sandbox import SubprocessSandbox
except ImportError:
    from models import SreAgentAction, SreAgentObservation
    from tasks import TASK_DEFINITIONS, grade_task
    from server.subprocess_sandbox import SubprocessSandbox

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

MAX_STEPS = 20
CONTAINER_IMAGE = "ubuntu:22.04"
CONTAINER_MEM_LIMIT = "512m"

# Patterns that warrant an immediate penalty (never executed).
DESTRUCTIVE_PATTERNS = [
    r"rm\s+-[rRf]*\s+/\s*$",   # rm -rf /
    r"rm\s+-[rRf]*\s+/\*",     # rm -rf /*
    r"dd\s+if=",                # dd if=...
    r"mkfs\.",                  # mkfs.ext4 …
    r":\(\)\s*\{",              # fork bomb  :() { … }
    r"chmod\s+-R\s+000\s+/\b",  # chmod -R 000 /
    r">\s*/dev/sd[a-z]",        # > /dev/sda
]


# ---------------------------------------------------------------------------
#  Environment
# ---------------------------------------------------------------------------

class SreAgentEnvironment(Environment):
    """
    SRE Agent Environment — Docker sandbox for SRE task simulation.

    The agent receives a task description (broken server scenario) and
    interacts with a real Ubuntu container via bash commands. A deterministic
    grader checks the container state after each step to compute rewards.

    Lifecycle:
      1. reset()  → spins up container, injects bug, returns first observation
      2. step()   → executes command, grades, returns observation + reward
      3. Episode ends when score == 1.0 or step_count >= MAX_STEPS
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = False

    def __init__(self):
        """Initialise internal state — no container is created yet."""
        self._state = State(episode_id=str(uuid.uuid4()), step_count=0)
        self._docker_client = None
        self._container = None
        self._current_task_id: str | None = None
        self._previous_score: float = 0.0
        self._use_subprocess: bool = False  # Fallback flag

        # Ordered list of tasks for deterministic cycling.
        self._task_list = list(TASK_DEFINITIONS.keys())
        self._task_index = 0

    # ------------------------------------------------------------------
    #  Docker helpers
    # ------------------------------------------------------------------

    def _get_docker_client(self):
        """Lazy-initialise the Docker client."""
        if self._docker_client is None:
            self._docker_client = docker.from_env()
        return self._docker_client

    def _cleanup_container(self):
        """Stop and remove the current sandbox container if it exists."""
        if self._container is not None:
            try:
                self._container.stop(timeout=3)
                self._container.remove(force=True)
                logger.info("Cleaned up container %s", self._container.name)
            except Exception as exc:
                logger.warning("Container cleanup error: %s", exc)
            finally:
                self._container = None

    def _spawn_container(self):
        """Create a fresh sandbox — Docker container or subprocess fallback."""
        self._cleanup_container()

        # Try Docker first (works locally and in DinD setups)
        if not self._use_subprocess:
            try:
                client = self._get_docker_client()
                name = f"sre_sandbox_{uuid.uuid4().hex[:8]}"

                container = client.containers.run(
                    CONTAINER_IMAGE,
                    command="sleep infinity",
                    name=name,
                    detach=True,
                    stdin_open=True,
                    tty=True,
                    mem_limit=CONTAINER_MEM_LIMIT,
                )
                logger.info("Spawned Docker sandbox: %s", name)
                return container
            except Exception as exc:
                logger.warning(
                    "Docker unavailable (%s), falling back to subprocess sandbox", exc
                )
                self._use_subprocess = True

        # Subprocess fallback (HF Spaces — runs commands in the server container)
        sandbox = SubprocessSandbox()
        logger.info("Spawned subprocess sandbox: %s", sandbox.name)
        return sandbox

    def _exec_in_container(self, command: str, timeout: int = 120) -> str:
        """Execute *command* in the sandbox and return combined output."""
        if self._container is None:
            return "Error: No sandbox container is running."
        try:
            result = self._container.exec_run(
                ["/bin/bash", "-c", command],
                tty=True,
            )
            output = result.output.decode("utf-8", errors="replace")
            # Cap output length so observations stay reasonable.
            if len(output) > 4096:
                output = output[:4096] + "\n... (output truncated)"
            return output
        except Exception as exc:
            return f"Execution error: {exc}"

    # ------------------------------------------------------------------
    #  Safety
    # ------------------------------------------------------------------

    @staticmethod
    def _is_destructive(command: str) -> bool:
        """Return True if *command* matches a known destructive pattern."""
        for pattern in DESTRUCTIVE_PATTERNS:
            if re.search(pattern, command):
                return True
        return False

    # ------------------------------------------------------------------
    #  OpenEnv API
    # ------------------------------------------------------------------

    def reset(self) -> SreAgentObservation:
        """
        Reset the environment.

        1. Tears down any existing sandbox container.
        2. Picks the next task (cycles through task_1 → task_2 → task_3).
        3. Spins up a fresh Ubuntu container.
        4. Runs the task's setup script to inject the bug.
        5. Returns the initial observation with the task description.
        """
        # Fresh episode state.
        self._state = State(episode_id=str(uuid.uuid4()), step_count=0)
        self._previous_score = 0.0

        # Cycle to the next task.
        self._current_task_id = self._task_list[
            self._task_index % len(self._task_list)
        ]
        self._task_index += 1
        task = TASK_DEFINITIONS[self._current_task_id]

        # Spin up container and inject bug.
        self._container = self._spawn_container()
        setup_out = self._exec_in_container(task["setup_script"])
        logger.info(
            "Setup [%s] done — first 200 chars: %s",
            self._current_task_id,
            setup_out[:200],
        )

        return SreAgentObservation(
            task_id=self._current_task_id,
            task_description=task["description"],
            terminal_output=(
                f"=== SRE SANDBOX READY ===\n"
                f"Task: {task['name']} ({task['difficulty']})\n"
                f"You are logged in as root@sandbox. "
                f"Use bash commands to diagnose and fix the issue.\n"
                f"You have {MAX_STEPS} steps.\n"
            ),
            current_step=0,
            max_steps=MAX_STEPS,
            done=False,
            reward=0.0,
        )

    def step(  # type: ignore[override]
        self, action: SreAgentAction
    ) -> SreAgentObservation:
        """
        Execute the agent's bash command in the sandbox.

        1. Validates & checks for destructive commands.
        2. Runs the command inside the Docker container.
        3. Runs the grader to compute a score delta.
        4. Returns observation with terminal output + reward.
        """
        self._state.step_count += 1
        step = self._state.step_count
        command = action.command.strip()
        task = TASK_DEFINITIONS[self._current_task_id]

        # --- destructive command guard ---
        if self._is_destructive(command):
            return SreAgentObservation(
                task_id=self._current_task_id,
                task_description=task["description"],
                terminal_output=(
                    "⚠️  BLOCKED — The command was identified as destructive "
                    "and was NOT executed. A penalty has been applied."
                ),
                current_step=step,
                max_steps=MAX_STEPS,
                done=step >= MAX_STEPS,
                reward=-0.1,
                metadata={"blocked_command": command},
            )

        # --- execute command ---
        output = self._exec_in_container(command)

        # --- grade ---
        current_score = grade_task(self._current_task_id, self._container)
        reward = round(current_score - self._previous_score, 4)
        self._previous_score = current_score

        done = current_score >= 0.99 or step >= MAX_STEPS

        return SreAgentObservation(
            task_id=self._current_task_id,
            task_description=task["description"],
            terminal_output=output if output else "(no output)",
            current_step=step,
            max_steps=MAX_STEPS,
            done=done,
            reward=reward,
            metadata={
                "current_score": current_score,
                "command": command,
            },
        )

    @property
    def state(self) -> State:
        """Return the current episode state."""
        return self._state

    # ------------------------------------------------------------------
    #  Cleanup
    # ------------------------------------------------------------------

    def __del__(self):
        """Best-effort cleanup when the object is garbage-collected."""
        self._cleanup_container()
