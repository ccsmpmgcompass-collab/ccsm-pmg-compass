"""cloud_job_wrapper.py — runs a command as a subprocess, mirroring its
progress into the CLOUD_JOB_STATUS sheet tab so Streamlit (wherever it's
running) can show live status for jobs executed on GitHub Actions.

Usage:
    python -m app.ingestion.cloud_job_wrapper --job-id <uuid> \\
        --job-type tableau_reports -- \\
        python -m app.ingestion.tableau_reports_runner --year 2026 --quarter 2
"""
import argparse
import json
import subprocess
import sys
import time

from app.integrations import cloud_job_status

_THROTTLE_SECONDS = 3.0


def _extract_progress(line: str) -> str:
    """Best-effort human-readable progress text from one line of output.
    Tries the runner's JSON progress-line shape first, falls back to the
    raw line (the referral scraper and imos runner print plain text)."""
    line = line.strip()
    if not line:
        return ""
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return line
    if not isinstance(msg, dict):
        return line
    msg_type = msg.get("type")
    if msg_type == "progress":
        return f"{msg.get('completed', '?')}/{msg.get('total', '?')} — {msg.get('area', '')}"
    if msg_type == "areas":
        return f"{msg.get('total', '?')} jobs queued"
    if msg_type in ("status", "error"):
        return msg.get("msg", line)
    if msg_type == "done":
        return f"done — {msg.get('succeeded', 0)} succeeded, {msg.get('failed', 0)} failed"
    return line


def run(job_id: str, job_type: str, cmd: list[str]) -> int:
    cloud_job_status.update_job(job_id, "RUNNING", progress_text="Starting...")

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    last_write = 0.0
    last_line = ""
    for raw_line in proc.stdout:
        line = raw_line.rstrip("\n")
        if not line:
            continue
        print(line)  # keep it in the GitHub Actions log too
        last_line = _extract_progress(line) or last_line
        now = time.monotonic()
        if now - last_write >= _THROTTLE_SECONDS:
            cloud_job_status.update_job(job_id, "RUNNING", progress_text=last_line)
            last_write = now
    proc.wait()

    if proc.returncode == 0:
        cloud_job_status.update_job(job_id, "SUCCESS", progress_text=last_line,
                                    result_summary=last_line)
    else:
        cloud_job_status.update_job(
            job_id, "ERROR", progress_text=last_line,
            result_summary=f"Exit code {proc.returncode}: {last_line}",
        )
    return proc.returncode


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--job-type", required=True)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("ERROR: no command given after --", file=sys.stderr)
        sys.exit(2)

    rc = run(args.job_id, args.job_type, cmd)
    sys.exit(rc)


if __name__ == "__main__":
    main()
