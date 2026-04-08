# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
SRE Agent Task Definitions.

Each task defines:
  - name: Human-readable task title
  - difficulty: easy / medium / hard
  - description: What the agent is told (the "goal")
  - setup_script: Bash script injected into the container to create the bug
  - grade(container): Deterministic grading function returning 0.0–1.0
"""

import logging

logger = logging.getLogger(__name__)

def _get_history(container) -> str:
    """Retrieves the bash history to check for messy or brute-force commands."""
    return _exec(container, "cat ~/.bash_history || echo ''")

# ---------------------------------------------------------------------------
#  Task Registry
# ---------------------------------------------------------------------------

TASK_DEFINITIONS = {
"task_1_permissions": {
    "name": "Fix File Permissions",
    "difficulty": "easy",
    # "description": (
    #     "A critical web page file at /var/www/html/index.html has had its "
    #     "permissions completely removed (set to 000). No user can read it. "
    #     "Fix the file permissions so the web server can serve the file. "
    #     "The recommended permission is 644 (owner read/write, others read)."
    # ),
    "description": (
        "A critical web page file somewhere inside var has had its "
        "permissions completely removed (set to 000). No user can read it. "
        "Fix the html file permissions(only) so the web server can serve the file. "
        "so that owner can read/write, and others can read."
    ),
    "setup_script": (
        "set -e\n"
        "mkdir -p /var/www/html\n"
        "echo '<h1>Welcome to SRE Agent Server</h1>"
        "<p>Service is operational.</p>' > /var/www/html/index.html\n"
        "chmod 000 /var/www/html/index.html\n"
    ),
},
"task_2_service": {
    "name": "Restart Crashed Web Server",
    "difficulty": "medium",
    "description": (
        "The nginx web server has crashed unexpectedly and left a stale "
        "PID file somewhere. The server needs to be restarted and "
        "listening on port 80. Diagnose the issue, clean up any stale state, "
        "and restart the service.\n"
        "IMPORTANT: This is a Docker container — use 'service nginx start' "
        "instead of 'systemctl'."
        "give step by step commands to fix the issue.\n"
    ),
    "setup_script": (
        "set -e\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "apt-get update -qq > /dev/null 2>&1\n"
        "apt-get install -y -qq nginx procps iproute2 > /dev/null 2>&1\n"
        "echo '<h1>SRE Agent Server</h1><p>Service restored.</p>' "
        "> /var/www/html/index.html\n"
        "service nginx start\n"
        "sleep 1\n"
        "pkill -9 nginx || true\n"
        "sleep 0.5\n"
        "echo '99999' > /run/nginx.pid\n"
    ),
},
"task_3_nginx_config": {
    "name": "Fix Broken Nginx Configuration",
    "difficulty": "hard",
    # "description": (
    #     "The nginx web server has a syntax error in its main configuration "
    #     "file (/etc/nginx/nginx.conf) that prevents it from starting. "
    #     "Diagnose the configuration error, fix it, start nginx, and verify "
    #     "it serves content on port 80.\n"
    #     "The expected web content is already placed in /var/www/html/index.html.\n"
    #     "IMPORTANT: This is a Docker container — use 'service nginx start' "
    #     "instead of 'systemctl'. You can validate the config with 'nginx -t'."
    # ),
    "description": (
        "The nginx web server has a syntax error in its main configuration "
        "file somewhere inside that prevents it from starting. "
        "Diagnose the configuration error, fix it, start nginx, and verify "
        "it serves content on port 80.\n"
        "The expected web content is already placed in /var/www/html/index.html.\n"
        "IMPORTANT: This is a Docker container — use 'service nginx start' "
        "instead of 'systemctl'. You can validate the config with 'nginx -t'."
    ),
    "setup_script": (
        "set -e\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "apt-get update -qq > /dev/null 2>&1\n"
        "apt-get install -y -qq nginx curl procps iproute2 > /dev/null 2>&1\n"
        "echo '<h1>SRE Agent Fixed This!</h1>"
        "<p>Configuration repaired successfully.</p>' "
        "> /var/www/html/index.html\n"
        "# Break nginx config — remove the last closing brace\n"
        "sed -i '$ d' /etc/nginx/nginx.conf\n"
        "service nginx stop 2>/dev/null || true\n"
        "pkill nginx 2>/dev/null || true\n"
    ),
},
"task_4_disk_pressure": {
    "name": "Emergency Disk Clearance",
    "difficulty": "hard",
    "description": (
        "The system is reporting 'No space left on device' errors. "
        "A rogue log file has consumed the entire available disk space in /var/log. "
        "Find the oversized file, remove it, and restart the logging service (rsyslog)."
    ),
    "setup_script": (
        "set -e\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "apt-get update -qq > /dev/null 2>&1\n"
        "apt-get install -y -qq rsyslog > /dev/null 2>&1\n"
        "mkdir -p /var/log/app/\n"
        "truncate -s 10M /var/log/app/debug.log.1\n"
        "chown -R syslog:adm /var/log/app\n"
        "service rsyslog start\n"
    ),
},

"task_5_db_pipeline": {
    "name": "DB Corruption Pipeline",
    "difficulty": "hard",
    "description": (
        "The database is completely down and the application cannot connect. You must perform a full recovery pipeline. "
        "1) Find and stop the rogue process blocking port 5432. "
        "2) The PostgreSQL pg_hba.conf file has its permissions erased and contains a syntax error. Fix both so it's readable. "
        "3) Start the PostgreSQL service. "
        "4) Read the new expected base64 password from /opt/auth/token.txt, decode it, and update the 'appuser' account in PostgreSQL. "
        "5) Finally, update the application config at /etc/myapp/config.json with this new decoded password instead of the old one, "
        "and start the application 'myapp' daemon (a placeholder service we've provided)."
    ),
    "setup_script": (
        "set -e\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "apt-get update -qq > /dev/null 2>&1\n"
        "apt-get install -y -qq postgresql procps python3 > /dev/null 2>&1\n"
        "service postgresql start\n"
        "su - postgres -c \"psql -c \\\"CREATE USER appuser WITH PASSWORD 'wrong_password';\\\"\" || true\n"
        "service postgresql stop\n"
        "# 1. Rogue process on 5432\n"
        "python3 -c 'import socket; s=socket.socket(); s.bind((\"0.0.0.0\", 5432)); s.listen(1); import time; time.sleep(3600)' >/dev/null 2>&1 &\n"
        "# 2. Break pg_hba.conf\n"
        "PG_HBA=$(find /etc/postgresql -name pg_hba.conf -type f)\n"
        "echo '!!!CORRUPT!!!' >> $PG_HBA\n"
        "chmod 000 $PG_HBA\n"
        "# 3. Auth token\n"
        "mkdir -p /opt/auth\n"
        "echo 'cDRzc3cwcmRfVTNQ' > /opt/auth/token.txt\n"
        "# 4. App config\n"
        "mkdir -p /etc/myapp\n"
        "echo '{\"db_user\": \"appuser\", \"db_pass\": \"old_password\"}' > /etc/myapp/config.json\n"
        "# 5. Mock app service\n"
        "echo '#!/bin/bash\nwhile true; do sleep 10; done' > /usr/local/bin/myappd\n"
        "chmod +x /usr/local/bin/myappd\n"
    ),
},
"task_6_dns_poisoning": {
    "name": "Fix Local Service Discovery",
    "difficulty": "hard",
    "description": (
        "The application is failing to connect to the internal database at 'db.local'. "
        "The database is verified as running on localhost:5432, but the app "
        "cannot resolve the address correctly. Fix the resolution issue."
    ),
    "setup_script": (
        "set -e\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "apt-get update -qq > /dev/null 2>&1\n"
        "apt-get install -y -qq iputils-ping dnsutils > /dev/null 2>&1\n"
        "echo '10.255.255.255 db.local' >> /etc/hosts\n"
    ),
},
"task_7_web_restore": {
    "name": "Webserver Pipeline Complete Restore",
    "difficulty": "hard",
    "description": (
        "The Nginx web server is completely broken due to a botched system update. "
        "1) The missing SSL certificates have been backed up in /root/backup-certs.tar.gz. Extract them to /etc/ssl/certs/. "
        "2) The default symlink in /etc/nginx/sites-enabled/ is broken. Remove it. "
        "3) Symlink the /etc/nginx/sites-available/myapp config to sites-enabled. "
        "4) The myapp config has a syntax error. Fix it. "
        "5) The web root /var/www/html/ is empty! Restore the files from /var/backups/html/ into it. "
        "6) Ensure /var/www/html/ is owned by www-data. "
        "7) Start the nginx service successfully."
    ),
    "setup_script": (
        "set -e\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "apt-get update -qq > /dev/null 2>&1\n"
        "apt-get install -y -qq nginx procps tar > /dev/null 2>&1\n"
        "# 1. SSL certs\n"
        "mkdir -p /tmp/certs\n"
        "touch /tmp/certs/myapp.crt /tmp/certs/myapp.key\n"
        "tar -czf /root/backup-certs.tar.gz -C /tmp certs\n"
        "rm -rf /tmp/certs\n"
        "# 2. Sites-enabled\n"
        "rm -f /etc/nginx/sites-enabled/default\n"
        "ln -s /does/not/exist /etc/nginx/sites-enabled/default\n"
        "# 3. Symlink & 4. Syntax Error\n"
        "echo -e 'server {\\nlisten 80;\\nlisten 443 ssl;\\nssl_certificate /etc/ssl/certs/myapp.crt;\\nssl_certificate_key /etc/ssl/certs/myapp.key;\\nroot /var/www/html;\\nindex index.html;\\nINVALID_DIRECTIVE;\\n}' > /etc/nginx/sites-available/myapp\n"
        "# 5. Web root restore\n"
        "mkdir -p /var/backups/html\n"
        "echo '<h1>Restored!</h1>' > /var/backups/html/index.html\n"
        "rm -rf /var/www/html\n"
        "mkdir -p /var/www/html\n"
        "chown root:root /var/www/html\n"
    ),
},
"task_8_disk_clean": {
    "name": "Disk Clean & Service Chain",
    "difficulty": "hard",
    "description": (
        "The server is having severe disk and logging problems. "
        "1) A huge sparse file at /tmp/fill.dd is consuming excessive blocks. Remove it. "
        "2) The /var/log/syslog file was deleted accidentally. Recreate it. "
        "3) Ensure /var/log/syslog is owned by syslog:adm so the service can write to it. "
        "4) Start the rsyslog service successfully. "
        "5) A vital cronjob was backed up to /root/cron.bak. Restore it to /etc/cron.d/logsync. "
        "6) Fix its permissions (it must be exactly 644, not executable, or cron will refuse it). "
        "7) Start the cron service to ensure it runs."
    ),
    "setup_script": (
        "set -e\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "apt-get update -qq > /dev/null 2>&1\n"
        "apt-get install -y -qq rsyslog cron procps > /dev/null 2>&1\n"
        "# 1. Sparse file\n"
        "dd if=/dev/zero of=/tmp/fill.dd bs=1M count=0 seek=5000 2>/dev/null\n"
        "# 2. Syslog broken\n"
        "service rsyslog stop || true\n"
        "rm -f /var/log/syslog\n"
        "# 3. Cron backed up\n"
        "service cron stop || true\n"
        "echo '* * * * * root /usr/bin/sync' > /root/cron.bak\n"
        "chmod 0777 /root/cron.bak\n"
    ),
},
}


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _exec(container, cmd: str) -> str:
    """Run a command inside a Docker container and return stripped stdout."""
    try:
        result = container.exec_run(["/bin/bash", "-c", cmd])
        return result.output.decode("utf-8", errors="replace").strip()
    except Exception as e:
        logger.warning(f"Grader exec failed: {e}")
        return ""


# ---------------------------------------------------------------------------
#  Public grading entry-point
# ---------------------------------------------------------------------------

def grade_task(task_id: str, container) -> float:
    """
    Grade a task by inspecting the current state of the container.

    Returns a score between 0.0 and 1.0.
    """
    graders = {
        "task_1_permissions": _grade_permissions,
        "task_2_service": _grade_service,
        "task_3_nginx_config": _grade_nginx_config,
        "task_4_disk_pressure": _grade_disk_pressure,
        "task_5_db_pipeline": _grade_db_pipeline,
        "task_6_dns_poisoning": _grade_dns_poisoning,
        "task_7_web_restore": _grade_web_restore,
        "task_8_disk_clean": _grade_disk_clean,
    }
    grader = graders.get(task_id)
    if grader is None:
        logger.error(f"No grader for task: {task_id}")
        return 0.0
    try:
        return grader(container)
    except Exception as e:
        logger.error(f"Grader crash for {task_id}: {e}")
        return 0.0


# ---------------------------------------------------------------------------
#  Individual graders
# ---------------------------------------------------------------------------
def _grade_permissions(container) -> float:
    """
    Task 1 (Easy): Fix File Permissions.
    
    Checkpoints:
      - File exists and permissions are 644/755/664  -> 1.0
      - Permissions changed from 000 but not ideal  -> 0.5
    
    Penalties:
      - Leftover 'trash' files in /var/www/html      -> -0.2
      - Excessive commands (>10) for easy task      -> -0.1
    """
    score = 0.0
    # 1. Check current state
    raw = _exec(container, "stat -c '%a' /var/www/html/index.html 2>/dev/null || echo 'MISSING'")
    if raw == "MISSING": return 0.0

    perms = int(raw) if raw.isdigit() else 0
    if perms in (644, 755, 664):
        score = 1.0
    elif perms > 0:
        score = 0.5

    # --- PENALTIES ---
    # Penalty for leaving backup files (e.g., index.html.bak)
    extras = _exec(container, "ls /var/www/html/ | grep -v '^index.html$'")
    if extras:
        score -= 0.2
    
    # Penalty for being slow (more than 10 commands for an 'easy' task)
    history = _get_history(container).splitlines()
    if len(history) > 10:
        score -= 0.1

    return max(0.01, min(0.99, score))


def _grade_service(container) -> float:
    """
    Task 2 (Medium): Restart Crashed Web Server.
    
    Checkpoints:
      - Stale PID file handled (removed/valid)       -> +0.3
      - nginx master process running                 -> +0.3
      - Port 80 is listening                         -> +0.4
      
    Penalties:
      - Used 'kill -9' (Brute force)                 -> -0.1
      - Did not delete the specific '99999' PID file -> -0.2
    """
    score = 0.0

    # --- checkpoint 1: stale PID ------------------------------------------------
    pid_status = _exec(container, (
        "if [ -f /run/nginx.pid ]; then "
        "  pid=$(cat /run/nginx.pid 2>/dev/null); "
        "  if [ -n \"$pid\" ] && kill -0 \"$pid\" 2>/dev/null; then "
        "    echo VALID; "
        "  else "
        "    echo STALE; "
        "  fi; "
        "else "
        "  echo REMOVED; "
        "fi"
    ))
    if pid_status in ("VALID", "REMOVED"):
        score += 0.3

    # --- checkpoint 2: nginx process running ------------------------------------
    proc = _exec(
        container,
        "pgrep -x nginx > /dev/null 2>&1 && echo RUNNING || echo STOPPED",
    )
    if "RUNNING" in proc:
        score += 0.3

    # --- checkpoint 3: port 80 listening ----------------------------------------
    port = _exec(
        container,
        "ss -tlnp 2>/dev/null | grep -q ':80 ' && echo LISTENING || echo NO",
    )
    if "LISTENING" in port:
        score += 0.4

    pid_val = _exec(container, "cat /run/nginx.pid 2>/dev/null || echo ''")
    if pid_val == "99999":
        score -= 0.2

    # Penalty: Brute force usage of kill -9
    if "kill -9" in _get_history(container):
        score -= 0.1

    # return max(-1.0, round(score, 2))

    # return min(round(score, 2), 1.0)
    return max(0.01, min(0.99, round(score, 2)))


def _grade_nginx_config(container) -> float:
    """
    Task 3 (Hard): Fix Broken Nginx Configuration.
    
    Checkpoints:
      - nginx -t passes                               -> +0.4
      - nginx master process running                  -> +0.3
      - curl localhost:80 returns 200 + "SRE Agent"   -> +0.3
      
    Penalties:
      - Backup files left in /etc/nginx/ (.bak, .tmp) -> -0.15
      - Bloat: Installed editors (vim/nano)           -> -0.1
    """
    score = 0.0

    # --- checkpoint 1: valid config ---------------------------------------------
    cfg = _exec(container, "nginx -t 2>&1; echo EXIT_CODE=$?")
    if "EXIT_CODE=0" in cfg:
        score += 0.4

    # --- checkpoint 2: nginx running --------------------------------------------
    proc = _exec(
        container,
        "pgrep -x nginx > /dev/null 2>&1 && echo RUNNING || echo STOPPED",
    )
    if "RUNNING" in proc:
        score += 0.3

    # --- checkpoint 3: HTTP 200 + correct content -------------------------------
    http_code = _exec(
        container,
        "curl -s -o /dev/null -w '%{http_code}' http://localhost:80/ 2>/dev/null "
        "|| echo 000",
    )
    if http_code.strip() == "200":
        body = _exec(container, "curl -s http://localhost:80/ 2>/dev/null")
        if "SRE Agent" in body:
            score += 0.3

    config_backups = _exec(container, "ls /etc/nginx/ | grep -E '.bak|.tmp|.old'")
    if config_backups:
        score -= 0.15

    # Penalty: Installing unnecessary software (bloat)
    history = _get_history(container)
    if "apt install" in history and "nginx" not in history:
        score -= 0.1

    return max(0.01, min(0.99, round(score, 2)))





def _grade_disk_pressure(container) -> float:
    """
    Task 5 (Hard): Emergency Disk Clearance.

    Checkpoints:
      - The 10MB rogue file is gone                  -> +0.5
      - rsyslog service is running                   -> +0.5

    Penalties:
      - Deleted entire /var/log/app directory         -> -0.4
    """
    score = 0.0

    # Checkpoint 1: Is the 10MB file gone? (+0.5)
    file_check = _exec(container, "[ -f /var/log/app/debug.log.1 ] && echo EXISTS || echo GONE")
    if file_check == "GONE":
        score += 0.5

    # Checkpoint 2: Is rsyslog service running? (+0.5)
    service_status = _exec(container, "service rsyslog status | grep 'running' || echo 'DOWN'")
    if "running" in service_status:
        score += 0.5

    # Penalty: Deleting the entire /var/log/app directory instead of the file (-0.4)
    dir_check = _exec(container, "[ -d /var/log/app ] && echo OK || echo DELETED")
    if dir_check == "DELETED":
        score -= 0.4

    return max(0.01, min(0.99, round(score, 2)))


# ---------------------------------------------------------------------------
#  Advanced Individual graders (Task 6-8)
# ---------------------------------------------------------------------------

def _grade_dns_poisoning(container) -> float:
    """
    Task 6 (Hard): Fix Local Service Discovery.

    Checkpoints:
      - db.local resolves to 127.0.0.1 / ::1         -> 1.0
      - Bad IP removed but not pointed to localhost   -> 0.4

    Penalties:
      - More than 5 commands for a single file edit   -> -0.2
    """
    score = 0.0

    # Checkpoint 1: Does db.local resolve to 127.0.0.1 or localhost? (+1.0)
    resolution = _exec(container, "getent hosts db.local")
    if "127.0.0.1" in resolution or "::1" in resolution:
        score = 1.0
    # Partial Reward: Bad IP removed but not pointed to localhost (+0.4)
    elif "10.255.255.255" not in _exec(container, "cat /etc/hosts"):
        score = 0.4

    # Penalty: Using more than 5 commands for a single file edit (-0.2)
    history = _get_history(container).splitlines()
    if len(history) > 5:
        score -= 0.2

    return max(0.01, min(0.99, round(score, 2)))

def _grade_db_pipeline(container) -> float:
    score = 0.0

    # 1. Rogue process killed (+0.10)
    rogue_check = _exec(container, "ss -tulpn 2>/dev/null | grep -q ':5432 ' | grep python3 || echo GONE")
    if "GONE" in rogue_check:
        score += 0.10

    # 2. Permissions fixed (+0.15)
    pg_hba = _exec(container, "find /etc/postgresql -name pg_hba.conf -type f | head -n 1")
    if pg_hba:
        perms = _exec(container, f"stat -c '%a' {pg_hba} 2>/dev/null || echo 000")
        if int(perms) > 0 and '0' not in perms[0]: # Not 000
            score += 0.15

        # 3. Syntax fixed (+0.15)
        syntax_check = _exec(container, f"grep '!!!CORRUPT!!!' {pg_hba} || echo GONE")
        if "GONE" in syntax_check:
            score += 0.15

    # 4. Service started (+0.15)
    pg_run = _exec(container, "pgrep -f 'postgres' || echo STOPPED")
    if "STOPPED" not in pg_run:
        score += 0.15

    # Make sure we can check db connection
    _exec(container, "service postgresql start >/dev/null 2>&1")

    # 5. Token found and 6. User updated (+0.10 + 0.15 = +0.25)
    history = _get_history(container)
    if "token.txt" in history or "base64" in history:
        score += 0.10
    connect_test = _exec(container, "PGPASSWORD='p4ssw0rd_U3P' psql -U appuser -d postgres -h 127.0.0.1 -c '\\q' 2>/dev/null && echo SUCCESS || echo FAIL")
    if "SUCCESS" in connect_test:
        score += 0.15

    # 7. Config updated (+0.10)
    config_check = _exec(container, "grep 'p4ssw0rd_U3P' /etc/myapp/config.json || echo FAIL")
    if "FAIL" not in config_check:
        score += 0.10

    # 8. App service started (+0.09)
    app_run = _exec(container, "pgrep -f 'myappd' || echo STOPPED")
    if "STOPPED" not in app_run:
        score += 0.09

    return max(0.01, min(0.99, round(score, 2)))


def _grade_web_restore(container) -> float:
    score = 0.0

    # 1. Certs restored (+0.10)
    if "EXISTS" in _exec(container, "[ -f /etc/ssl/certs/myapp.crt ] && echo EXISTS"):
        score += 0.10

    # 2. Broken default symlink removed (+0.10)
    if "GONE" in _exec(container, "[ ! -L /etc/nginx/sites-enabled/default ] && echo GONE"):
        score += 0.10

    # 3. myapp symlinked (+0.15)
    if "YES" in _exec(container, "[ -L /etc/nginx/sites-enabled/myapp ] && echo YES"):
        score += 0.15

    # 4. Web files restored (+0.15)
    if "YES" in _exec(container, "[ -f /var/www/html/index.html ] && echo YES"):
        score += 0.15

    # 5. Ownership fixed (+0.15)
    owner = _exec(container, "stat -c '%U' /var/www/html/index.html 2>/dev/null || echo root")
    if owner == "www-data":
        score += 0.15

    # 6. Syntax error fixed (+0.15)
    syntax = _exec(container, "grep 'INVALID_DIRECTIVE' /etc/nginx/sites-available/myapp || echo GONE")
    if "GONE" in syntax:
        score += 0.15

    # 7. Nginx started (+0.19)
    proc = _exec(container, "pgrep -x nginx > /dev/null 2>&1 && echo RUNNING || echo STOPPED")
    if "RUNNING" in proc:
        score += 0.19

    return max(0.01, min(0.99, round(score, 2)))


def _grade_disk_clean(container) -> float:
    score = 0.0

    # 1. Sparse file removed (+0.15)
    if "GONE" in _exec(container, "[ ! -f /tmp/fill.dd ] && echo GONE"):
        score += 0.15
    
    # 2. Syslog file created (+0.10)
    if "YES" in _exec(container, "[ -f /var/log/syslog ] && echo YES"):
        score += 0.10

    # 3. Syslog ownership fixed (+0.15)
    user = _exec(container, "stat -c '%U:%G' /var/log/syslog 2>/dev/null || echo root:root")
    if "syslog:adm" in user:
        score += 0.15

    # 4. Rsyslog started (+0.15)
    if "RUNNING" in _exec(container, "pgrep -f rsyslogd >/dev/null && echo RUNNING"):
        score += 0.15

    # 5. Cronjob restored (+0.15)
    if "YES" in _exec(container, "[ -f /etc/cron.d/logsync ] && echo YES"):
        score += 0.15

    # 6. Cronjob permissions fixed (+0.10)
    perms = _exec(container, "stat -c '%a' /etc/cron.d/logsync 2>/dev/null || echo 000")
    if "644" in perms:
        score += 0.10

    # 7. Cron service started (+0.19)
    if "RUNNING" in _exec(container, "pgrep -x cron >/dev/null && echo RUNNING"):
        score += 0.19

    return max(0.01, min(0.99, round(score, 2)))
