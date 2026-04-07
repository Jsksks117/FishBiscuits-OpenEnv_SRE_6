"""
Inference Script — SRE Agent (OpenAI Client)
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

- The inference script must be named `inference.py` and placed in the root directory of the project
- Participants must use OpenAI Client for all LLM calls using above variables

STDOUT FORMAT
- The script must emit exactly three line types to stdout, in this order:

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> rewards=<r1,r2,...,rn>
"""

import os
import re
import textwrap
from typing import List, Optional

from openai import OpenAI
from client import SreAgentEnv, SreAgentAction

# ---------------------------------------------------------------------------
# Environment variables (hackathon-mandated names)
# ---------------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME") or "gpt-4o-mini"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ENV_NAME = "SRE_Agent"
MAX_STEPS = 20
TEMPERATURE = 0.2
MAX_TOKENS = 200
MAX_OUTPUT_CHARS = 1000
FALLBACK_ACTION = "echo 'no-op'"
DEBUG = True

SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert Linux System Administrator solving SRE tasks in a Docker container.
    You will be given the task description and terminal output.
    Output ONLY the bash command you want to run.
    Do NOT use backticks, code blocks, or explanations. Just the raw command.
    If you are unsure, respond with: echo 'investigating'
""").strip()


# ---------------------------------------------------------------------------
# Logging helpers (mandatory stdout format)
# ---------------------------------------------------------------------------
def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, rewards: List[float], task: str) -> None:
    raw_score = sum(rewards)
    final_score = max(0.01, min(0.99, float(raw_score)))
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={final_score:.2f} rewards={rewards_str}", flush=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def truncate_output(text: str, max_len: int = MAX_OUTPUT_CHARS) -> str:
    """Keep terminal output bounded to avoid blowing up the LLM context."""
    if not text:
        return ""
    if len(text) > max_len:
        return "...[truncated]...\n" + text[-max_len:]
    return text


def build_history_lines(history: List[str]) -> str:
    """Return the last 4 history entries, like the sample script."""
    if not history:
        return "None"
    return "\n".join(history[-4:])


def build_user_prompt(step: int, task_description: str, terminal_output: str, history: List[str]) -> str:
    prompt = textwrap.dedent(f"""
        Step: {step}
        Task: {task_description}
        Previous steps:
        {build_history_lines(history)}
        Terminal Output:
        {truncate_output(terminal_output)}
        Reply with exactly one bash command to run.
    """).strip()
    return prompt


def parse_model_action(response_text: str) -> str:
    """Extract a clean command from the LLM response."""
    if not response_text:
        return FALLBACK_ACTION

    # Strip markdown backticks if present
    # Match ```bash\n...\n``` or ```\n...\n```
    block_match = re.search(r'```(?:bash|sh)?\s*\n(.*?)\n```', response_text, re.DOTALL)
    if block_match:
        return block_match.group(1).strip()

    # Match inline backticks `command`
    inline_match = re.search(r'`([^`]+)`', response_text)
    if inline_match:
        return inline_match.group(1).strip()

    # Otherwise use the first non-empty line
    for line in response_text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("//"):
            return line

    return FALLBACK_ACTION


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    async_env = SreAgentEnv(base_url="http://localhost:7860", message_timeout_s=180.0)
    env = async_env.sync()

    # We run 3 episodes (one per task — the environment cycles tasks on reset)
    tasks_to_run = 6
    all_scores = []

    for episode in range(tasks_to_run):
        history: List[str] = []
        rewards: List[float] = []
        steps_taken = 0
        success = False
        task_name = f"task_{episode + 1}"

        try:
            log_start(task=task_name, env=ENV_NAME, model=MODEL_NAME or "unknown")
            
            result = env.reset()
            observation = result.observation
            task_name = observation.task_id or task_name

            for step in range(1, MAX_STEPS + 1):
                if result.done:
                    break

                user_prompt = build_user_prompt(
                    step=step,
                    task_description=observation.task_description,
                    terminal_output=observation.terminal_output,
                    history=history,
                )

                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]

                try:
                    completion = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=messages,
                        temperature=TEMPERATURE,
                        max_tokens=MAX_TOKENS,
                        stream=False,
                    )
                    response_text = completion.choices[0].message.content or ""
                except Exception as exc:
                    response_text = FALLBACK_ACTION
                    if DEBUG:
                        print(f"[DEBUG] Model request failed: {exc}", flush=True)

                action_str = parse_model_action(response_text)

                result = env.step(SreAgentAction(command=action_str))
                observation = result.observation

                reward = result.reward or 0.0
                done = result.done

                rewards.append(reward)
                steps_taken = step

                log_step(step=step, action=action_str, reward=reward, done=done, error=None)

                history_line = f"Step {step}: {action_str} -> reward {reward:+.2f}"
                history.append(history_line)

                if done:
                    success = sum(rewards) > 0.0
                    break

            else:
                # Exhausted MAX_STEPS without done=true
                success = False

        finally:
            log_end(success=success, steps=steps_taken, rewards=rewards, task=task_name)
            total_score = sum(rewards)
            all_scores.append(total_score)

    # Summary
    env.close()


if __name__ == "__main__":
    main()
