from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reddit_media_link_crawler export/check steps.")
    parser.add_argument("--tool-dir", type=Path, default=Path("tools") / "reddit_media_link_crawler")
    parser.add_argument("--subreddit", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output") / "reddit")
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--max-posts", type=int, default=0)
    parser.add_argument("--recent-rss-limit", type=int, default=0)
    parser.add_argument("--check-other-links", action="store_true")
    parser.add_argument("--max-check-urls", type=int, default=0)
    return parser.parse_args()


def crawler_python(tool_dir: Path) -> Path:
    python_path = tool_dir / ".venv" / "Scripts" / "python.exe"
    if not python_path.exists():
        raise SystemExit(f"Reddit crawler python not found. Run setup first: {python_path}")
    return python_path


def normalize_subreddit(subreddit: str) -> str:
    value = subreddit.strip()
    for prefix in (
        "https://www.reddit.com/r/",
        "http://www.reddit.com/r/",
        "https://reddit.com/r/",
        "http://reddit.com/r/",
        "/r/",
        "r/",
    ):
        value = value.removeprefix(prefix)
    value = value.strip("/")
    if "/" in value:
        value = value.split("/", 1)[0]
    if not value:
        raise SystemExit("Subreddit name is empty.")
    return value


def run_cmd(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=str(cwd), text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    args = parse_args()
    tool_dir = args.tool_dir.resolve()
    python_path = crawler_python(tool_dir)
    export_script = tool_dir / "scripts" / "export_reddit_subreddit.py"
    check_script = tool_dir / "scripts" / "check_other_links.py"
    if not export_script.exists():
        raise SystemExit(f"Reddit export script not found: {export_script}")

    output_dir = args.output_dir.resolve()
    subreddit = normalize_subreddit(args.subreddit)
    cmd = [
        str(python_path),
        str(export_script),
        "--subreddit",
        subreddit,
        "--output-dir",
        str(output_dir),
        "--sleep-seconds",
        str(args.sleep_seconds),
        "--max-posts",
        str(args.max_posts),
        "--recent-rss-limit",
        str(args.recent_rss_limit),
    ]
    run_cmd(cmd, cwd=tool_dir)

    subreddit_dir = output_dir / subreddit
    if args.check_other_links:
        if not check_script.exists():
            raise SystemExit(f"Reddit link checker script not found: {check_script}")
        other_links_txt = subreddit_dir / "other_links.txt"
        check_cmd = [
            str(python_path),
            str(check_script),
            "--input-txt",
            str(other_links_txt),
            "--output-dir",
            str(subreddit_dir),
            "--max-urls",
            str(args.max_check_urls),
        ]
        run_cmd(check_cmd, cwd=tool_dir)

    print(json.dumps({"subreddit_dir": str(subreddit_dir), "posts_json": str(subreddit_dir / "posts.json")}, indent=2))


if __name__ == "__main__":
    main()
