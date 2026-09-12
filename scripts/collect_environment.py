#!/usr/bin/env python3
"""Record selected compute resources without secrets or host identity fields."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def linux_cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip() in {"model name", "Hardware"}:
                return value.strip()
    except OSError:
        pass
    return platform.processor() or None


def memory_total_bytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def nvidia_report() -> dict:
    if shutil.which("nvidia-smi") is None:
        return {"status": "tool_unavailable", "devices": []}
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "query_failed_or_timed_out", "devices": []}
    if result.returncode != 0:
        return {"status": "driver_query_failed", "devices": []}
    devices = []
    for row in result.stdout.splitlines():
        fields = [value.strip() for value in row.rsplit(",", 2)]
        if len(fields) == 3:
            devices.append(
                {
                    "model": fields[0],
                    "memory_total_mib": fields[1],
                    "driver_version": fields[2],
                }
            )
    return {"status": "queried", "devices": devices}


def collect() -> dict:
    disk = shutil.disk_usage(Path.cwd())
    return {
        "schema_version": 1,
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
        },
        "cpu": {"model": linux_cpu_model(), "logical_count": os.cpu_count()},
        "memory_total_bytes": memory_total_bytes(),
        "current_filesystem": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
        },
        "nvidia": nvidia_report(),
        "notes": [
            "This records the computer where the script was executed.",
            "A missing NVIDIA tool does not prove no NVIDIA GPU is installed.",
            "No detector inference or performance benchmark is performed.",
            "Other GPU backends and non-Linux memory queries are not implemented.",
            "Dependency locks and model hashes are recorded with actual runs later.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="outputs/local/hardware.json")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output = None if args.output == "-" else Path(args.output)
    if output is not None and output.exists() and not args.overwrite:
        parser.error("output already exists; choose another path or use --overwrite")
    report = json.dumps(collect(), indent=2) + "\n"
    if output is None:
        sys.stdout.write(report)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w" if args.overwrite else "x") as handle:
            handle.write(report)
        print(f"Environment report written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
