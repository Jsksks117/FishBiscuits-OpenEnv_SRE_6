---
title: FishBiscuits-OpenEnv_SRE_6
emoji: 🐳
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---
# Openenv - SRE Agent Linux (Sandbox-Ubuntu) RL Environment

[![OpenEnv Component](https://img.shields.io/badge/OpenEnv-v0.2.3-blue)](https://github.com/open-env/open-env)
[![License](https://img.shields.io/badge/License-BSD--3--Clause-green)](LICENSE)

## Overview

This repository implements a sandboxed Site Reliability Engineering (SRE) benchmarking environment for evaluating agents on realistic Linux(ubuntu 22.04) troubleshooting tasks. It is built around an OpenEnv-compatible containerized environment that simulates common infrastructure failures in Linux Systems and measures agent performance using deterministic reward/penalty grading.

The project is designed for:
- evaluating LLM-driven SRE agents,
- testing robust troubleshooting workflows,
- validating command-based remediation strategies in an isolated Ubuntu environment.

## Motivation and Use Case

Modern SRE teams need automated support for diagnosing and resolving service outages, configuration failures, and infrastructure faults. This repository offers a reproducible evaluation environment to benchmark agent reasoning, command planning, and system recovery skills.

Use cases include:
- benchmarking LLM-based troubleshooting agents,
- training reinforcement learning agents on infrastructure recovery,
- comparing diagnostic strategies across eight progressively harder tasks,
- validating agent safety by using an isolated sandbox instead of production systems.

## Environment Description

The sandbox exposes a terminal-style action/observation interface inside a Docker-based Ubuntu environment. Each episode starts from a fresh container state with one of eight predefined task scenarios.

The environment is implemented as:
- a Docker-based sandbox for reliable local isolation,
- a fallback subprocess mode for environments where Docker is unavailable,
- a task registry with setup scripts and grading logic in `FishBiscuits-OpenEnv_SRE_6/tasks.py`.

### Action Space

Agents interact with the environment using a single action type:
- `command` (string): raw bash command executed inside the sandbox.

This means the agent's output is interpreted directly as a shell command and executed in the container.

### Observation Space

Each step returns an observation containing:
- `terminal_output`: the captured stdout/stderr from the last executed command,
- `task_description`: the current task goal and instructions,
- `task_id`: identifier for the active task,
- `current_step`: current step count in the scenario,
- `reward`: incremental reward from the last action,
- `done`: whether the task is complete or the step budget is exhausted.

## Task Descriptions

The environment contains eight distinct tasks. Each task is defined with a human-readable goal, difficulty label, a setup script that injects the failure condition, and a grading routine.

### Task 1: Fix File Permissions
- **ID:** `task_1_permissions`
- **Difficulty:** Easy
- **Goal:** A critical HTML file under `/var/www/html/index.html` has been accidentally set to permission `000`. Fix only the file permissions so the web server can read it.
- **Success criteria:** file exists with readable permissions for owner and others.

### Task 2: Restart Crashed Web Server
- **ID:** `task_2_service`
- **Difficulty:** Medium
- **Goal:** Nginx has crashed and left a stale PID file at `/run/nginx.pid`. Clean up the stale state, restart Nginx using `service nginx start`, and ensure it is listening on port 80.
- **Success criteria:** `/run/nginx.pid` is removed or contains a valid process ID, the Nginx process is running, and port 80 is listening.
- **Important:** This environment uses Docker containers, so `service nginx start` is the correct management method.

### Task 3: Fix Broken Nginx Configuration
- **ID:** `task_3_nginx_config`
- **Difficulty:** Hard
- **Goal:** The Nginx configuration is broken by a missing closing brace in its configuration file. Fix the config, validate with `nginx -t`, start Nginx, and confirm the site returns a valid response.
- **Success criteria:** `nginx -t` passes, Nginx is running, and a request to `http://localhost:80/` returns HTTP 200 with the expected page content.

### Task 4: Emergency Disk Clearance
- **ID:** `task_4_disk_pressure`
- **Difficulty:** Hard
- **Goal:** A 10MB rogue log file at `/var/log/app/debug.log.1` has exhausted the available space. Remove the offending file and restart the logging service (`rsyslog`).
- **Success criteria:** `/var/log/app/debug.log.1` is removed and `rsyslog` is running again.

### Task 5: DB Corruption Pipeline
- **ID:** `task_5_db_pipeline`
- **Difficulty:** Very Hard
- **Goal:** Perform full recovery of a broken database backend: kill rogue port listeners, fix PostgreSQL config permissions/syntax, start service, decode a base64 auth token, and update the application config.
- **Success criteria:** PostgreSQL is running, the auth token is correctly applied to the DB user, and the app config matches the new password.

### Task 6: Fix Local Service Discovery
- **ID:** `task_6_dns_poisoning`
- **Difficulty:** Hard
- **Goal:** The hostname `db.local` is poisoned in `/etc/hosts` with an invalid IP. Remove or fix the bad entry so `db.local` resolves to `127.0.0.1` or `::1`.
- **Success criteria:** `db.local` resolves to `127.0.0.1` or `::1` via `getent hosts db.local` or equivalent resolution check.

### Task 7: Webserver Pipeline Complete Restore
- **ID:** `task_7_web_restore`
- **Difficulty:** Very Hard
- **Goal:** Full stack web restoration after a botched update. Includes extracting binary SSL backups (tar), repairing broken symlinks, fixing complex Nginx syntax errors, and restoring web content from backups with correct ownership.
- **Success criteria:** SSL certs exist, symlinks point to valid configs, Nginx is running on port 80, and web content is owned by www-data.

### Task 8: Disk Clean & Service Chain
- **ID:** `task_8_disk_clean`
- **Difficulty:** Very Hard
- **Goal:** Complex service chain recovery: remove massive sparse files consuming block space, recreate accidentally deleted syslog files with system permissions, and restore a backed-up cronjob with strict 644 permission requirements.
- **Success criteria:** Sparse file is gone, syslog is recreated with owner syslog:adm, rsyslog is running, and the cron service is active with the restored job.

## Reward Breakdown and Penalties

Each task is graded with checkpoints and penalties. Scores are computed in the task grader and normalized to a value between 0.01 and 0.99.

### Task 1 Rewards and Penalties
- **Rewards:**
  - 1.0 for proper permissions such as `644`, `755`, or `664`
  - 0.5 for any other non-zero permission update
- **Penalties:**
  - `-0.2` for leftover backup or temporary files in `/var/www/html`
  - `-0.1` for using more than 10 commands in the episode

### Task 2 Rewards and Penalties
- **Rewards:**
  - `+0.3` for handling the stale PID file correctly
  - `+0.3` for having the Nginx process running
  - `+0.4` for having port 80 listening
- **Penalties:**
  - `-0.1` for using `kill -9`
  - `-0.2` if the bogus PID value `99999` remains in `/run/nginx.pid`

### Task 3 Rewards and Penalties
- **Rewards:**
  - `+0.4` for passing `nginx -t`
  - `+0.3` for Nginx running
  - `+0.3` for a successful HTTP 200 response on `http://localhost:80/`
- **Penalties:**
  - `-0.15` for leaving `.bak`, `.tmp`, or old config files in `/etc/nginx/`
  - `-0.1` for installing unrelated editor or software packages

### Task 4 Rewards and Penalties
- **Rewards:**
  - `+0.5` for removing the 10MB rogue log file
  - `+0.5` for having `rsyslog` running
- **Penalties:**
  - `-0.4` for deleting the entire `/var/log/app` directory instead of removing only the offending file

### Task 5 Rewards and Penalties
- **Rewards:**
  - `+0.10` for killing the rogue process
  - `+0.30` for fixing pg_hba.conf permissions and syntax
  - `+0.15` for starting PostgreSQL
  - `+0.25` for decoding token and updating database user
  - `+0.10` for updating app configuration
  - `+0.09` for starting the app daemon

### Task 6 Rewards and Penalties
- **Rewards:**
  - `1.0` if `db.local` resolves to `127.0.0.1` or `::1`
  - `0.4` if the poisoned entry is removed but not correctly remapped
- **Penalties:**
  - `-0.2` for using more than 5 commands to perform the single-hosts-file edit

### Task 7 Rewards and Penalties
- **Rewards:**
  - `+0.10` for restoring SSL certificates
  - `+0.10` for removing broken default symlink
  - `+0.15` for symlinking myapp configuration
  - `+0.15` for restoring web root index files
  - `+0.15` for fixing web root ownership
  - `+0.15` for fixing Nginx syntax
  - `+0.19` for starting Nginx

### Task 8 Rewards and Penalties
- **Rewards:**
  - `+0.15` for removing the massive sparse file
  - `+0.10` for recreating the syslog file
  - `+0.15` for fixing syslog owner/group
  - `+0.15` for starting rsyslog
  - `+0.15` for restoring the cronjob backup
  - `+0.10` for setting cronjob permissions to 644
  - `+0.19` for starting the cron service

## Expected Difficulty Summary

| Task | Difficulty | Focus Area |
| --- | --- | --- |
| Task 1 | Easy | File permissions and minimal remediation |
| Task 2 | Medium | Service lifecycle and stale PID cleanup |
| Task 3 | Hard | Configuration syntax correctness and validation |
| Task 4 | Hard | Disk pressure remediation and logging service recovery |
| Task 5 | Very Hard | Database pipeline and credential recovery |
| Task 6 | Hard | Local DNS/hosts troubleshooting |
| Task 7 | Very Hard | Full web stack restoration and backup recovery |
| Task 8 | Very Hard | Storage management and multi-service chaining |

## Clone and Use This Repository

### Clone the repo

```bash
git clone https://github.com/Jsksks117/FishBiscuits-OpenEnv_SRE_6.git
cd FishBiscuits-OpenEnv_SRE_6

# Install dependencies
pip install -e .
```

## Local Setup

### Install Python dependencies

This repository is designed to run inside the `FishBiscuits-OpenEnv_SRE_6` project structure.

```bash
cd FishBiscuits-OpenEnv_SRE_6
pip install -r server/requirements.txt
```

### Run the sandbox server locally

```bash
cd FishBiscuits-OpenEnv_SRE_6
python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
```


## Run inference and evaluation

### Environment Variables
Ensure the following are set:
```bash
export API_BASE_URL="https://api.openai.com/v1" # or your chosen provider
export MODEL_NAME="gpt-4o"
export OPENAI_API_KEY="your_api_key"
export HF_TOKEN="your_huggingface_token" # Required for HF hosted models
```

### Execute Baseline Agent
```bash
cd FishBiscuits-OpenEnv_SRE_6
python inference.py
```

## Docker Setup

Docker is recommended for the most reliable sandbox experience.

### Build the Docker image

```bash
cd FishBiscuits-OpenEnv_SRE_6
docker build -t sre-agent .
```

### Run the container

```bash
docker run -p 7860:7860 sre-agent
```
 

## Baseline and Evaluation

Baseline results evaluated using the `llama-3.3-70b-versatile` model based on recent terminal runs.

| Task | Model | Steps | Score | Rewards Sequence | Notes |
| --- | --- | --- | --- | --- | --- |
| task_1 | `llama-3.3-70b-versatile` | 2 | 0.99 | `0.99` | Found and fixed the permission issue in one command |
| task_2 | `llama-3.3-70b-versatile` | 4 | 0.99 | `0.01, 0.98` | Diagnosed stale PID then restarted Nginx |
| task_3 | `llama-3.3-70b-versatile` | 3 | 0.99 | `0.40, 0.00, 0.59` | Validated config and started Nginx successfully |
| task_4 | `llama-3.3-70b-versatile` | 10 | 0.01 | `0.01, 0.00, ...` | Struggles with exhaustive log searches and rsyslog restart logic |
| task_5 | `llama-3.3-70b-versatile` | 10 | 0.49 | `0.34, 0.00, 0.00, 0.00, 0.15, ...` | Solved process/permission issues but missed auth chain |
| task_6 | `llama-3.3-70b-versatile` | 3 | 0.99 | `0.01, 0.00, 0.98` | Resolved poisoned hosts entry successfully |
| task_7 | `llama-3.3-70b-versatile` | 10 | 0.25 | `0.01, 0.09, 0.15, -0.15, 0.15, -0.15, 0.15, ...` | Struggled with complex Nginx syntax loop |
| task_8 | `llama-3.3-70b-versatile` | 10 | 0.55 | `0.15, 0.15, 0.00, 0.10, 0.00, 0.15, ...` | Successfully cleared disk and recreated log files |

## Project Layout

- `FishBiscuits-OpenEnv_SRE_6/` — main environment package
- `FishBiscuits-OpenEnv_SRE_6/tasks.py` — all task definitions and grader logic
- `FishBiscuits-OpenEnv_SRE_6/server/` — API server and OpenEnv integration
- `FishBiscuits-OpenEnv_SRE_6/inference.py` — sample inference loop
- `FishBiscuits-OpenEnv_SRE_6/Dockerfile` — container image definition

## License

This repository follows the BSD-style license referenced in the project's source headers.
