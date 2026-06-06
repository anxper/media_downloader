from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local pornhub_metadata_crawler checkout.")
    parser.add_argument("--tool-dir", type=Path, default=Path("tools") / "pornhub_metadata_crawler")
    parser.add_argument("--log-file", type=Path, default=Path("output") / "pornhub_metadata_crawler.log")
    parser.add_argument("--schedule", action="store_true")
    return parser.parse_args()


def build_command(tool_dir: Path, schedule: bool) -> list[str]:
    python_path = tool_dir / ".venv" / "Scripts" / "python.exe"
    main_path = tool_dir / "main.py"
    config_path = tool_dir / "config.json"
    if not python_path.exists():
        raise SystemExit(f"Crawler python not found. Run setup first: {python_path}")
    if not main_path.exists():
        raise SystemExit(f"Crawler main.py not found: {main_path}")
    if not config_path.exists():
        raise SystemExit(f"Crawler config not found. Run write_pornhub_crawler_config first: {config_path}")

    cmd = [str(python_path), "-u", str(main_path)]
    if schedule:
        cmd.append("--schedule")
    return cmd


def main() -> None:
    args = parse_args()
    tool_dir = args.tool_dir.resolve()
    log_file = args.log_file.resolve()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_command(tool_dir, args.schedule)

    with log_file.open("a", encoding="utf-8") as log_handle:
        log_handle.write(f"[{datetime.now().isoformat()}] START command={' '.join(cmd)}\n")
        log_handle.flush()
        process = subprocess.Popen(
            cmd,
            cwd=str(tool_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for raw_line in process.stdout:
            print(raw_line, end="")
            log_handle.write(raw_line)
        process.wait()
        log_handle.write(f"[{datetime.now().isoformat()}] END returncode={process.returncode}\n")
        if process.returncode:
            raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
