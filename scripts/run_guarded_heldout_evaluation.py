#!/usr/bin/env python
"""Owner-gated launcher for the predeclared, one-time held-out evaluation.

This launcher deliberately refuses the current proposed/unapproved protocol.
It does not load benchmark labels itself. It verifies identities and delegates
only to an owner-approved executor recorded in the evaluation protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "configs/workbench/final_evaluation_protocol_v1.json"


class GuardError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


def _manifest(output: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        if path.name in {"checksums.sha256", "execution_record.json"}:
            continue
        entries.append({"path": path.relative_to(output).as_posix(), "sha256": _sha256(path)})
    return entries


def execute(
    *,
    protocol_path: Path,
    output: Path,
    expected_protocol_sha256: str,
    expected_source_commit: str,
    rewire_scores: Path,
) -> dict[str, Any]:
    # Require the explicit token before reading protocol/executor configuration.
    if os.environ.get("HELDOUT_APPROVAL") != "APPROVED":
        raise GuardError("HELDOUT_APPROVAL must be explicitly set to APPROVED by the owner")

    protocol_path = protocol_path.resolve()
    if _sha256(protocol_path) != expected_protocol_sha256.lower():
        raise GuardError("evaluation protocol SHA-256 does not match the owner-pinned value")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "OWNER_APPROVED":
        raise GuardError("evaluation protocol is not OWNER_APPROVED")
    approval = protocol.get("owner_approval") or {}
    if approval.get("status") != "APPROVED" or not approval.get("approver") or not approval.get("approved_at_utc"):
        raise GuardError("dated, named owner approval is missing")
    if (protocol.get("evaluation") or {}).get("partition") != "held_out":
        raise GuardError("protocol partition must be exactly held_out")

    source = protocol.get("source_identity") or {}
    current_commit = _git("rev-parse", "HEAD")
    pinned_commit = source.get("platform_execution_commit")
    if not pinned_commit or pinned_commit == "OWNER_MUST_PIN_AFTER_REVIEW_AND_BEFORE_APPROVAL":
        raise GuardError("owner has not pinned the exact platform execution commit")
    if current_commit != expected_source_commit or current_commit != pinned_commit:
        raise GuardError("current platform commit does not match both owner-pinned revisions")
    if _git("status", "--porcelain"):
        raise GuardError("worktree must be clean before held-out execution")

    registry = ROOT / protocol["benchmark"]["registry"]
    score_lock = ROOT / protocol["score_lock"]["path"]
    if _sha256(registry) != protocol["benchmark"]["registry_sha256"].lower():
        raise GuardError("benchmark registry SHA-256 mismatch")
    if _sha256(score_lock) != protocol["score_lock"]["sha256"].lower():
        raise GuardError("score-lock SHA-256 mismatch")

    output = output.resolve()
    if output.exists():
        raise GuardError("output directory must be new; refusing overwrite")
    try:
        output.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise GuardError("held-out results must be written outside the Git worktree")

    executor = protocol.get("approved_executor")
    if not isinstance(executor, dict):
        raise GuardError("approved_executor is not configured; no evaluator will be launched")
    executor_path = (ROOT / executor["script"]).resolve()
    if _sha256(executor_path) != executor.get("sha256", "").lower():
        raise GuardError("approved evaluator script hash mismatch")
    command = [str(part) for part in executor.get("command", [])]
    if not command:
        raise GuardError("approved evaluator command is empty")
    substitutions = {
        "{python}": sys.executable,
        "{registry}": str(registry),
        "{rewire_scores}": str(rewire_scores.resolve()),
        "{output}": str(output),
    }
    command = [substitutions.get(part, part) for part in command]
    command[0] = sys.executable if command[0] == "{python}" else command[0]
    if str(executor_path) not in command and executor["script"] not in command:
        raise GuardError("executor command must invoke the hash-pinned evaluator")

    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise GuardError(f"approved evaluator returned exit code {completed.returncode}")
    if not output.is_dir():
        raise GuardError("approved evaluator did not create the new output directory")
    entries = _manifest(output)
    (output / "checksums.sha256").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in entries), encoding="utf-8"
    )
    record = {
        "status": "HELDOUT_EVALUATION_EXECUTED",
        "partition": "held_out",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "operator": approval["approver"],
        "platform_commit": current_commit,
        "evaluation_protocol_sha256": expected_protocol_sha256.lower(),
        "score_lock_sha256": protocol["score_lock"]["sha256"],
        "benchmark_registry_sha256": protocol["benchmark"]["registry_sha256"],
        "executor_sha256": executor["sha256"].lower(),
        "result_files": len(entries),
        "heldout_status": "EXECUTED_ONCE",
    }
    (output / "execution_record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--rewire-scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        execute(
            protocol_path=args.protocol,
            output=args.output,
            expected_protocol_sha256=args.expected_protocol_sha256,
            expected_source_commit=args.expected_source_commit,
            rewire_scores=args.rewire_scores,
        )
    except (GuardError, OSError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"HELDOUT_EXECUTION_REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
