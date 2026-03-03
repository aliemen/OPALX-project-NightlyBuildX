#!/usr/bin/env python3

import os
import re
import subprocess
import threading
from datetime import datetime
from flask import (
    Flask,
    request,
    abort,
    jsonify,
    redirect,
    url_for,
)


app = Flask(__name__)
BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9._\-/]+$")

RUN_SCRIPT = "/home/aliemen/opalx/nightly-build-opalx/NightlyBuildX/scripts/run_nightly_local.sh"

# Base directory for full trigger logs on disk. Can be overridden via env.
TRIGGER_LOG_BASE_DIR = os.environ.get(
    "OPALX_TRIGGER_LOG_DIR", "/home/aliemen/opalx/nightly-results/trigger-logs"
)

# Simple in-memory state to track the currently running job.
_job_lock = threading.Lock()
_job_running = False
_job_last_branch = None
_job_last_ok = None

# Bounded in-memory log buffer for the current job (last N lines).
_job_log_lines = []
_JOB_LOG_MAX_LINES = 5000
# Sequence numbers for log lines to help the client handle truncation.
_job_log_start_seq = 0
_job_log_end_seq = 0

# Path of the full on-disk log file for the current/last job.
_job_log_file_path = None


def _append_log_line(line: str) -> None:
    """Append a line to the in-memory log buffer (bounded)."""
    global _job_log_lines, _job_log_start_seq, _job_log_end_seq
    _job_log_lines.append(line.rstrip("\n"))
    _job_log_end_seq += 1
    if len(_job_log_lines) > _JOB_LOG_MAX_LINES:
        # Keep only the last N lines and advance the starting sequence.
        dropped = len(_job_log_lines) - _JOB_LOG_MAX_LINES
        _job_log_lines = _job_log_lines[-_JOB_LOG_MAX_LINES :]
        _job_log_start_seq += dropped


def _run_nightly_job(branch: str, env: dict) -> None:
    """Background worker that runs the nightly script and records status."""
    global _job_running, _job_last_ok, _job_log_lines, _job_log_start_seq, _job_log_end_seq

    ok = False

    # Clear any previous log for this job.
    with _job_lock:
        _job_log_lines = []
        _job_log_start_seq = 0
        _job_log_end_seq = 0
        log_file_path = _job_log_file_path

    log_file = None
    try:
        if log_file_path:
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            log_file = open(log_file_path, "a", encoding="utf-8")

        proc = subprocess.Popen(
            [RUN_SCRIPT],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert proc.stdout is not None  # For type checkers.
        for line in proc.stdout:
            with _job_lock:
                _append_log_line(line)
            if log_file is not None:
                log_file.write(line)

        proc.wait()
        ok = proc.returncode == 0
    except Exception as exc:
        msg = f"[trigger] Exception while running job: {exc}"
        with _job_lock:
            _append_log_line(msg)
        if log_file is not None:
            log_file.write(msg + "\n")
        ok = False
    finally:
        if log_file is not None:
            log_file.flush()
            log_file.close()

    with _job_lock:
        _job_running = False
        _job_last_ok = ok


@app.route("/trigger", methods=["POST"])
def trigger():
    branch = (request.form.get("branch") or "").strip()

    if not branch or not BRANCH_PATTERN.match(branch):
        return "Invalid branch name", 400

    if not os.path.isfile(RUN_SCRIPT) or not os.access(RUN_SCRIPT, os.X_OK):
        abort(500, description="Run script not found or not executable.")

    env = os.environ.copy()
    env["OPALX_BRANCH"] = branch

    with _job_lock:
        global _job_running, _job_last_branch, _job_last_ok, _job_log_file_path
        if _job_running:
            # A job is already in progress; just send the user to the status page.
            return redirect(url_for("trigger_status"), code=303)
        _job_running = True
        _job_last_branch = branch
        _job_last_ok = None

        # Compute log file path for this run, grouped by branch.
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_branch = branch or "unknown"
        log_dir = os.path.join(TRIGGER_LOG_BASE_DIR, safe_branch)
        _job_log_file_path = os.path.join(
            log_dir, f"opalx-nightly-{safe_branch}-{timestamp}.log"
        )

    # Start the job in a background thread and immediately show the status page.
    t = threading.Thread(
        target=_run_nightly_job,
        args=(branch, env),
        daemon=True,
    )
    t.start()

    return redirect(url_for("trigger_status"), code=303)


@app.route("/trigger/status", methods=["GET"])
def trigger_status():
    with _job_lock:
        running = _job_running
        branch = _job_last_branch

    branch_label = branch or "-"

    # Simple status page that polls /trigger/state and /trigger/log.
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>OPALX Nightly Trigger</title>
  <style>
    body {{
      font-family: sans-serif;
      padding: 2.5rem 1.5rem 3rem;
      background: radial-gradient(circle at top, #1f2937 0, #020617 55%, #000 100%);
      color: #e5e7eb;
      min-height: 100vh;
      margin: 0;
    }}
    .page {{
      max-width: 960px;
      margin: 0 auto;
    }}
    h1 {{
      margin-bottom: 0.75rem;
      font-size: 1.6rem;
    }}
    #status {{
      font-size: 1.1rem;
      margin-top: 0.5rem;
    }}
    .card {{
      background: rgba(15,23,42,0.96);
      border-radius: 0.9rem;
      padding: 1.75rem 1.8rem;
      box-shadow: 0 22px 45px rgba(15,23,42,0.8);
      border: 1px solid rgba(148,163,184,0.25);
      margin-top: 3rem;
    }}
    .spinner {{
      width: 40px;
      height: 40px;
      border-radius: 999px;
      border: 4px solid rgba(148,163,184,0.3);
      border-top-color: #38bdf8;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 1rem;
    }}
    .subtext {{
      font-size: 0.9rem;
      color: #9ca3af;
      margin-top: 0.5rem;
    }}
    .console-card {{
      margin-top: 1.5rem;
    }}
    .console-title {{
      font-size: 1rem;
      margin-bottom: 0.4rem;
      text-align: left;
    }}
    .console-hint {{
      font-size: 0.8rem;
      color: #9ca3af;
      margin-bottom: 0.6rem;
      text-align: left;
    }}
    .console {{
      background: #020617;
      border-radius: 0.5rem;
      border: 1px solid rgba(148,163,184,0.35);
      padding: 0.6rem 0.75rem;
      max-height: 260px;
      overflow-y: auto;
      text-align: left;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 0.8rem;
      line-height: 1.35;
      white-space: pre-wrap;
    }}
    .console-line-prefix {{
      color: #6b7280;
      margin-right: 0.35rem;
    }}
    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="card">
      <div class="spinner" id="spinner"></div>
      <h1>Nightly run status</h1>
      <p id="status">{"Running nightly job for branch '" + branch_label + "'." if running else "Checking job status…"}</p>
      <p class="subtext">This can take a while. Please keep this tab open until it completes.</p>

      <div class="console-card">
        <div class="console-title">Console output</div>
        <div class="console-hint" id="console-hint">
          { "Streaming latest log lines for branch '" + branch_label + "'…" if running else "No active run; trigger a new nightly job from the main page." }
        </div>
        <div class="console" id="console"></div>
      </div>
      <div class="console-card" id="download-card" style="display:none; margin-top: 1rem;">
        <button id="download-btn" style="
          padding: 0.5rem 1.2rem;
          border-radius: 999px;
          border: 1px solid rgba(148,163,184,0.8);
          background: transparent;
          color: #e5e7eb;
          font-size: 0.85rem;
          font-weight: 500;
          cursor: pointer;
        " onclick="window.location.href={repr(url_for('download_log'))}">
          Download full log
        </button>
      </div>
      <div class="console-card" style="margin-top: 0.75rem;">
        <button id="back-btn" style="
          padding: 0.5rem 1.2rem;
          border-radius: 999px;
          border: 1px solid rgba(148,163,184,0.5);
          background: transparent;
          color: #e5e7eb;
          font-size: 0.85rem;
          font-weight: 500;
          cursor: pointer;
        " onclick="window.location.href='/'">
          Back to overview
        </button>
      </div>
    </div>
  </div>
  <script>
    var lastRenderedSeq = -1;
    var pollingActive = true;

    function appendLogLines(lines, startSeq, endSeq) {{
      var consoleEl = document.getElementById("console");
      if (!consoleEl) return;

      if (lines.length === 0) {{
        return;
      }}

      var firstSeq = startSeq;
      var lastSeq = endSeq;

      // If we have never rendered before, start from the current startSeq.
      if (lastRenderedSeq < firstSeq) {{
        // If we are skipping older lines because of truncation, show a notice once.
        if (lastRenderedSeq >= 0 && lastRenderedSeq + 1 < firstSeq) {{
          var notice = document.createElement("div");
          notice.textContent = "… older log lines truncated; showing latest " + lines.length + " lines.";
          consoleEl.appendChild(notice);
        }}
        for (var i = 0; i < lines.length; i++) {{
          var line = lines[i];
          var div = document.createElement("div");
          var spanPrefix = document.createElement("span");
          spanPrefix.className = "console-line-prefix";
          spanPrefix.textContent = "›";
          div.appendChild(spanPrefix);
          div.appendChild(document.createTextNode(" " + line));
          consoleEl.appendChild(div);
        }}
        lastRenderedSeq = lastSeq;
        consoleEl.scrollTop = consoleEl.scrollHeight;
        return;
      }}

      // Append only new lines beyond lastRenderedSeq.
      for (var seq = Math.max(lastRenderedSeq + 1, firstSeq); seq <= lastSeq; seq++) {{
        var idx = seq - firstSeq;
        if (idx < 0 || idx >= lines.length) continue;
        var line = lines[idx];
        var div = document.createElement("div");
        var spanPrefix = document.createElement("span");
        spanPrefix.className = "console-line-prefix";
        spanPrefix.textContent = "›";
        div.appendChild(spanPrefix);
        div.appendChild(document.createTextNode(" " + line));
        consoleEl.appendChild(div);
      }}
      if (lastSeq >= Math.max(lastRenderedSeq, firstSeq)) {{
        lastRenderedSeq = lastSeq;
        consoleEl.scrollTop = consoleEl.scrollHeight;
      }}
    }}

    function checkLog() {{
      if (!pollingActive) return;
      fetch({repr(url_for("trigger_log"))}, {{ cache: "no-store" }})
        .then(function (resp) {{ return resp.json(); }})
        .then(function (data) {{
          var hintEl = document.getElementById("console-hint");
          if (data.branch) {{
            hintEl.textContent = data.running
              ? "Streaming latest log lines for branch '" + data.branch + "'…"
              : "Log from last run for branch '" + data.branch + "'.";
          }}
          if (Array.isArray(data.lines) && typeof data.start_seq === "number" && typeof data.end_seq === "number") {{
            appendLogLines(data.lines, data.start_seq, data.end_seq);
          }}
        }})
        .catch(function () {{
          // Ignore errors; we'll retry on the next tick.
        }});
    }}

    function checkStatus() {{
      if (!pollingActive) return;
      fetch({repr(url_for("trigger_state"))}, {{ cache: "no-store" }})
        .then(function (resp) {{ return resp.json(); }})
        .then(function (data) {{
          var statusEl = document.getElementById("status");
          var downloadCard = document.getElementById("download-card");
          var spinnerEl = document.getElementById("spinner");
          if (!data.running && data.ok !== null) {{
            pollingActive = false;
            if (data.ok) {{
              statusEl.textContent = "Nightly run for branch '" + (data.branch || "-") + "' completed successfully.";
            }} else {{
              statusEl.textContent = "Nightly run for branch '" + (data.branch || "-") + "' completed with errors. Check logs for details.";
            }}
            if (downloadCard) {{
              downloadCard.style.display = "block";
            }}
            if (spinnerEl) {{
              spinnerEl.style.display = "none";
            }}
          }} else if (data.running) {{
            statusEl.textContent = "Running nightly job for branch '" + (data.branch || "-") + "'…";
          }}
        }})
        .catch(function () {{
          // Ignore errors; we'll retry on the next tick.
        }});
    }}

    // Poll every 2 seconds.
    setInterval(checkStatus, 2000);
    setInterval(checkLog, 2000);
    checkStatus();
    checkLog();
  </script>
</body>
</html>
"""
    return html


@app.route("/trigger/state", methods=["GET"])
def trigger_state():
    with _job_lock:
        running = _job_running
        branch = _job_last_branch
        ok = _job_last_ok

    return jsonify({"running": running, "branch": branch, "ok": ok})


@app.route("/trigger/log", methods=["GET"])
def trigger_log():
    """Return the current in-memory log buffer for the active or last job."""
    with _job_lock:
        running = _job_running
        branch = _job_last_branch
        lines = list(_job_log_lines)
        start_seq = _job_log_start_seq
        end_seq = _job_log_end_seq

    return jsonify(
        {
            "running": running,
            "branch": branch,
            "lines": lines,
            "start_seq": start_seq,
            "end_seq": end_seq,
        }
    )


@app.route("/trigger/log/download", methods=["GET"])
def download_log():
    """Download the current or last job's log as a plain-text file."""
    with _job_lock:
        branch = _job_last_branch or "unknown"
        log_file_path = _job_log_file_path
        lines = list(_job_log_lines)

    # Prefer the full on-disk log if available; otherwise fall back to the
    # in-memory buffer (last N lines).
    content: str
    if log_file_path and os.path.isfile(log_file_path):
        try:
            with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            content = "\n".join(lines) + ("\n" if lines else "")
    else:
        content = "\n".join(lines) + ("\n" if lines else "")

    filename = f"opalx-nightly-{branch}.log"

    from flask import Response

    response = Response(content, mimetype="text/plain; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)

