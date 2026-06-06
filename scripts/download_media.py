from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tqdm import tqdm


MEDIA_SUFFIXES = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}


@dataclass(frozen=True)
class DownloadEntry:
    group_name: str
    url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download media URLs collected by the local crawlers.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pornhub-data-dir", type=Path, help="tools/pornhub_metadata_crawler/data directory.")
    source.add_argument("--reddit-posts-json", type=Path, help="posts.json exported by reddit_media_link_crawler.")
    source.add_argument("--urls-txt", type=Path, help="Plain text file with one media URL per line.")
    parser.add_argument("--name", default="", help="Group name for --urls-txt downloads.")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--archive-txt", type=Path, default=None)
    parser.add_argument("--format", default="bestvideo[height<=720]+bestaudio/best[height<=720]/best")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sleep-interval", type=float, default=1.0)
    parser.add_argument("--max-sleep-interval", type=float, default=3.0)
    parser.add_argument("--retries", type=int, default=10)
    parser.add_argument("--write-urls-only", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> object:
    if not path.exists():
        raise SystemExit(f"JSON file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_pornhub_entries(data_dir: Path) -> list[DownloadEntry]:
    if not data_dir.exists():
        raise SystemExit(f"PornHub crawler data dir not found: {data_dir}")

    entries: list[DownloadEntry] = []
    for path in sorted(data_dir.glob("*.json")):
        payload = read_json(path)
        if not isinstance(payload, dict):
            continue
        group_name = str(payload.get("model_name", "") or path.stem)
        videos = payload.get("videos", [])
        if not isinstance(videos, list):
            continue
        seen: set[str] = set()
        for item in videos:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            entries.append(DownloadEntry(group_name=group_name, url=url))
    return entries


def load_reddit_entries(posts_json: Path) -> list[DownloadEntry]:
    payload = read_json(posts_json)
    if not isinstance(payload, dict):
        raise SystemExit(f"Unexpected Reddit export payload: {posts_json}")

    subreddit = str(payload.get("subreddit", "") or posts_json.parent.name)
    entries: list[DownloadEntry] = []
    seen: set[str] = set()
    for section in ("redgifs", "other_links"):
        items = payload.get(section, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            url = str(item.get("external_url", "") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            entries.append(DownloadEntry(group_name=f"reddit_{subreddit}_{section}", url=url))
    return entries


def load_txt_entries(urls_txt: Path, name: str) -> list[DownloadEntry]:
    if not urls_txt.exists():
        raise SystemExit(f"URL file not found: {urls_txt}")
    group_name = name.strip() or urls_txt.stem
    urls: list[str] = []
    seen: set[str] = set()
    for raw_line in urls_txt.read_text(encoding="utf-8").splitlines():
        url = raw_line.strip()
        if not url or url.startswith("#") or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return [DownloadEntry(group_name=group_name, url=url) for url in urls]


def slice_entries(entries: list[DownloadEntry], start_index: int, limit: int) -> list[DownloadEntry]:
    start = max(0, min(start_index, len(entries)))
    selected = entries[start:]
    if limit > 0:
        selected = selected[:limit]
    return selected


def write_group_urls(output_root: Path, entries: list[DownloadEntry]) -> None:
    grouped: dict[str, list[str]] = {}
    for entry in entries:
        grouped.setdefault(entry.group_name, []).append(entry.url)
    for group_name, urls in grouped.items():
        group_dir = output_root / safe_path_name(group_name)
        group_dir.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(urls)
        if payload:
            payload += "\n"
        (group_dir / "urls.txt").write_text(payload, encoding="utf-8")


def extract_url_id(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("viewkey", "id", "v"):
        values = query.get(key)
        if values:
            return values[0]
    return parsed.path.rstrip("/").split("/")[-1]


def existing_media_ids(group_dir: Path) -> set[str]:
    ids: set[str] = set()
    if not group_dir.exists():
        return ids
    for path in group_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        parts = path.stem.split("_", 2)
        if len(parts) >= 2:
            ids.add(parts[1])
    return ids


def safe_path_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._- " else "_" for char in value).strip() or "media"


def output_template(group_dir: Path) -> str:
    return str(group_dir / "%(extractor)s_%(id)s_%(title).180B.%(ext)s")


def download_group(args: argparse.Namespace, group_name: str, urls: list[str]) -> tuple[int, int]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise SystemExit("yt-dlp is not installed. Run: pip install -r requirements.txt") from exc

    group_dir = args.output_root / safe_path_name(group_name)
    group_dir.mkdir(parents=True, exist_ok=True)
    existing_ids = existing_media_ids(group_dir)
    pending = [url for url in urls if extract_url_id(url) not in existing_ids]

    if not pending:
        return 0, len(urls)

    archive_txt = args.archive_txt or (args.output_root / "downloaded.txt")
    archive_txt.parent.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        "format": args.format,
        "outtmpl": output_template(group_dir),
        "download_archive": str(archive_txt),
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
        ydl.download(pending)
    return len(pending), len(urls) - len(pending)


def main() -> None:
    args = parse_args()
    args.output_root = args.output_root.resolve()
    args.output_root.mkdir(parents=True, exist_ok=True)

    if args.pornhub_data_dir is not None:
        entries = load_pornhub_entries(args.pornhub_data_dir)
        source = str(args.pornhub_data_dir)
    elif args.reddit_posts_json is not None:
        entries = load_reddit_entries(args.reddit_posts_json)
        source = str(args.reddit_posts_json)
    else:
        entries = load_txt_entries(args.urls_txt, args.name)
        source = str(args.urls_txt)

    selected = slice_entries(entries, args.start_index, args.limit)
    write_group_urls(args.output_root, selected)
    summary = {
        "source": source,
        "all_entries": len(entries),
        "selected_entries": len(selected),
        "output_root": str(args.output_root),
        "write_urls_only": args.write_urls_only,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.write_urls_only:
        return

    grouped: dict[str, list[str]] = {}
    for entry in selected:
        grouped.setdefault(entry.group_name, []).append(entry.url)

    downloaded = 0
    skipped = 0
    for group_name, urls in tqdm(grouped.items(), desc="Download groups", unit="group"):
        group_downloaded, group_skipped = download_group(args, group_name, urls)
        downloaded += group_downloaded
        skipped += group_skipped

    print(json.dumps({"downloaded_or_attempted": downloaded, "skipped_existing": skipped}, indent=2))


if __name__ == "__main__":
    main()
