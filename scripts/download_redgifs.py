from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlparse


MEDIA_SUFFIXES = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
INFO_JSON_SUFFIX = ".info.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export RedGifs links from a subreddit export and optionally download them with yt-dlp."
    )
    parser.add_argument(
        "--posts-json",
        type=Path,
        required=True,
        help="Subreddit export JSON created by export_reddit_subreddit.py.",
    )
    parser.add_argument(
        "--urls-txt",
        type=Path,
        required=True,
        help="Where to write the deduplicated RedGifs URL list.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where yt-dlp should place downloaded media.",
    )
    parser.add_argument(
        "--archive-txt",
        type=Path,
        default=None,
        help="yt-dlp download archive file to avoid re-downloading completed items.",
    )
    parser.add_argument(
        "--unavailable-txt",
        type=Path,
        help="Optional text file with known unavailable RedGifs URLs to skip before yt-dlp.",
    )
    parser.add_argument(
        "--write-links-only",
        action="store_true",
        help="Only export the deduplicated RedGifs URL list and stop before downloading.",
    )
    parser.add_argument("--start-index", type=int, default=0, help="Start download from this index in the deduplicated URL list.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of URLs to download. 0 means no limit.")
    parser.add_argument("--sleep-interval", type=float, default=1.0, help="Seconds to sleep between downloads.")
    parser.add_argument(
        "--max-sleep-interval",
        type=float,
        default=3.0,
        help="Upper bound for randomized download sleep interval.",
    )
    parser.add_argument("--retries", type=int, default=10, help="yt-dlp retry count.")
    parser.add_argument(
        "--flat-output",
        action="store_true",
        help="Store files directly in output-dir instead of output-dir/redgifs/.",
    )
    return parser.parse_args()


def load_redgifs_urls(posts_json: Path) -> list[str]:
    if not posts_json.exists():
        raise SystemExit(f"Posts JSON not found: {posts_json}")

    payload = json.loads(posts_json.read_text(encoding="utf-8"))
    items = payload.get("redgifs")
    if not isinstance(items, list):
        raise SystemExit(f"Unexpected export payload in {posts_json}")

    urls: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("external_url", "") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def write_urls_txt(urls: list[str], urls_txt: Path) -> None:
    urls_txt.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(urls)
    if payload:
        payload += "\n"
    urls_txt.write_text(payload, encoding="utf-8")


def read_urls_txt(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def slice_urls(urls: list[str], start_index: int, limit: int) -> list[str]:
    start_index = max(0, min(start_index, len(urls)))
    sliced = urls[start_index:]
    if limit > 0:
        sliced = sliced[:limit]
    return sliced


def normalize_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def extract_redgifs_id(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return ""
    if len(parts) >= 2 and parts[-2].lower() in {"watch", "ifr", "iframe", "gifs"}:
        return parts[-1]
    return parts[-1]


def iter_existing_outputs(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    paths: list[Path] = []
    for path in output_dir.rglob("*"):
        if not path.is_file():
            continue
        lower_name = path.name.lower()
        if path.suffix.lower() in MEDIA_SUFFIXES or lower_name.endswith(INFO_JSON_SUFFIX):
            paths.append(path)
    return paths


def build_existing_id_index(output_dir: Path) -> set[str]:
    existing_ids: set[str] = set()
    for path in iter_existing_outputs(output_dir):
        lower_name = path.name.lower()
        stem = path.name[: -len(INFO_JSON_SUFFIX)] if lower_name.endswith(INFO_JSON_SUFFIX) else path.stem
        normalized_stem = normalize_id(stem)
        if normalized_stem:
            existing_ids.add(normalized_stem)

        if lower_name.endswith(INFO_JSON_SUFFIX):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for key in ("id", "display_id"):
                value = normalize_id(str(payload.get(key, "") or ""))
                if value:
                    existing_ids.add(value)
            webpage_url = str(payload.get("webpage_url", "") or "")
            if webpage_url:
                redgifs_id = normalize_id(extract_redgifs_id(webpage_url))
                if redgifs_id:
                    existing_ids.add(redgifs_id)
    return existing_ids


def split_existing_urls(urls: list[str], output_dir: Path) -> tuple[list[str], list[str]]:
    existing_ids = build_existing_id_index(output_dir)
    if not existing_ids:
        return urls, []

    pending: list[str] = []
    skipped: list[str] = []
    for url in urls:
        redgifs_id = normalize_id(extract_redgifs_id(url))
        if redgifs_id and any(redgifs_id in existing_id or existing_id in redgifs_id for existing_id in existing_ids):
            skipped.append(url)
        else:
            pending.append(url)
    return pending, skipped


def split_unavailable_urls(urls: list[str], unavailable_txt: Path | None) -> tuple[list[str], list[str]]:
    unavailable_ids = {normalize_id(extract_redgifs_id(url)) for url in read_urls_txt(unavailable_txt)}
    unavailable_ids.discard("")
    if not unavailable_ids:
        return urls, []

    pending: list[str] = []
    skipped: list[str] = []
    for url in urls:
        redgifs_id = normalize_id(extract_redgifs_id(url))
        if redgifs_id and redgifs_id in unavailable_ids:
            skipped.append(url)
        else:
            pending.append(url)
    return pending, skipped


def build_output_template(output_dir: Path, flat_output: bool) -> str:
    base_dir = output_dir
    if not flat_output:
        # Keep all files in one predictable directory on Windows.
        base_dir = output_dir
    return str(base_dir / "%(extractor)s_%(id)s_%(title).180B.%(ext)s")


def run_download(args: argparse.Namespace, urls: list[str]) -> None:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise SystemExit(
            "yt-dlp is not installed in the current environment. Run "
            "`make setup-redgifs-downloader` first."
        ) from exc

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.archive_txt is None:
        args.archive_txt = args.output_dir / "redgifs_downloaded.txt"
    args.archive_txt.parent.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "outtmpl": build_output_template(args.output_dir, args.flat_output),
        "download_archive": str(args.archive_txt),
        "ignoreerrors": True,
        "retries": args.retries,
        "fragment_retries": args.retries,
        "sleep_interval": args.sleep_interval,
        "max_sleep_interval": args.max_sleep_interval,
        "restrictfilenames": False,
        "windowsfilenames": True,
        "noplaylist": True,
        "continuedl": True,
        "overwrites": False,
        "writeinfojson": True,
        "writesubtitles": False,
        "quiet": False,
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download(urls)


def main() -> None:
    args = parse_args()
    urls = load_redgifs_urls(args.posts_json)
    write_urls_txt(urls, args.urls_txt)

    selected_urls = slice_urls(urls, args.start_index, args.limit)
    summary = {
        "posts_json": str(args.posts_json),
        "urls_txt": str(args.urls_txt),
        "all_redgifs_urls": len(urls),
        "selected_urls": len(selected_urls),
        "start_index": max(0, args.start_index),
        "limit": args.limit,
        "write_links_only": args.write_links_only,
        "unavailable_txt": str(args.unavailable_txt) if args.unavailable_txt is not None else "",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.write_links_only:
        return
    if not selected_urls:
        print("No RedGifs URLs selected for download.")
        return

    pending_urls, skipped_existing_urls = split_existing_urls(selected_urls, args.output_dir)
    pending_urls, skipped_unavailable_urls = split_unavailable_urls(pending_urls, args.unavailable_txt)
    print(
        json.dumps(
            {
                "selected_urls": len(selected_urls),
                "skipped_existing": len(skipped_existing_urls),
                "skipped_unavailable": len(skipped_unavailable_urls),
                "pending_downloads": len(pending_urls),
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not pending_urls:
        print("All selected RedGifs URLs already exist locally.")
        return

    run_download(args, pending_urls)


if __name__ == "__main__":
    main()
