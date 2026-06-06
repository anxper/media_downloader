from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PORNHUB_REPO_URL = "https://github.com/anxper/pornhub_metadata_crawler.git"
REDDIT_REPO_URL = "https://github.com/anxper/reddit_media_link_crawler.git"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install local crawler checkouts under tools/.")
    parser.add_argument("--tools-dir", type=Path, default=Path("tools"))
    parser.add_argument("--pornhub-repo", default=PORNHUB_REPO_URL)
    parser.add_argument("--reddit-repo", default=default_reddit_repo())
    parser.add_argument("--base-python", type=Path, default=Path(sys.executable))
    parser.add_argument("--upgrade", action="store_true", help="Run git pull in existing checkouts.")
    parser.add_argument("--skip-install", action="store_true", help="Clone/update only; do not install Python deps.")
    return parser.parse_args()


def default_reddit_repo() -> str:
    env_value = os.environ.get("REDDIT_MEDIA_LINK_CRAWLER_REPO", "").strip()
    if env_value:
        return env_value

    sibling = Path.cwd().parent / "reddit_media_link_crawler"
    if sibling.exists():
        return str(sibling)

    return REDDIT_REPO_URL


def run_cmd(cmd: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def is_git_checkout(path: Path) -> bool:
    return (path / ".git").exists()


def ensure_repo(repo: str, target_dir: Path, upgrade: bool) -> None:
    if is_git_checkout(target_dir):
        if upgrade:
            print(f"Updating {target_dir}")
            run_cmd(["git", "pull", "--ff-only"], cwd=target_dir)
        else:
            print(f"Repository already exists: {target_dir}")
        return

    if target_dir.exists() and any(target_dir.iterdir()):
        raise SystemExit(f"Target directory exists and is not a git checkout: {target_dir}")

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"Cloning {repo} into {target_dir}")
    run_cmd(build_clone_command(repo, target_dir))


def build_clone_command(repo: str, target_dir: Path) -> list[str]:
    source_path = Path(repo)
    if source_path.exists():
        return [
            "git",
            "-c",
            f"safe.directory={source_path.resolve()}",
            "-c",
            f"safe.directory={(source_path / '.git').resolve()}",
            "clone",
            repo,
            str(target_dir),
        ]
    return ["git", "clone", "--depth", "1", repo, str(target_dir)]


def venv_python(target_dir: Path) -> Path:
    return target_dir / ".venv" / "Scripts" / "python.exe"


def ensure_venv(base_python: Path, target_dir: Path) -> Path:
    python_path = venv_python(target_dir)
    if python_path.exists():
        print(f"Virtual environment already exists: {python_path.parent.parent}")
        return python_path

    print(f"Creating virtual environment: {python_path.parent.parent}")
    run_cmd([str(base_python), "-m", "venv", str(python_path.parent.parent)])
    if not python_path.exists():
        raise SystemExit(f"Virtual environment python was not created: {python_path}")
    return python_path


def install_requirements(python_path: Path, target_dir: Path) -> None:
    requirements = target_dir / "requirements.txt"
    if not requirements.exists():
        print(f"No requirements.txt in {target_dir}; skipping dependency install")
        return

    print(f"Installing requirements for {target_dir.name}")
    run_cmd([str(python_path), "-m", "pip", "install", "--upgrade", "pip"], cwd=target_dir)
    run_cmd([str(python_path), "-m", "pip", "install", "-r", str(requirements)], cwd=target_dir)

    if "playwright" in requirements.read_text(encoding="utf-8").lower():
        run_cmd([str(python_path), "-m", "playwright", "install", "chromium"], cwd=target_dir)


def setup_one(name: str, repo: str, target_dir: Path, args: argparse.Namespace) -> None:
    print(f"\n== {name} ==")
    ensure_repo(repo, target_dir, args.upgrade)
    if args.skip_install:
        return
    python_path = ensure_venv(args.base_python, target_dir)
    install_requirements(python_path, target_dir)


def main() -> None:
    args = parse_args()
    tools_dir = args.tools_dir.resolve()
    setup_one("pornhub_metadata_crawler", args.pornhub_repo, tools_dir / "pornhub_metadata_crawler", args)
    setup_one("reddit_media_link_crawler", args.reddit_repo, tools_dir / "reddit_media_link_crawler", args)
    print("\nCrawler setup complete.")


if __name__ == "__main__":
    main()
