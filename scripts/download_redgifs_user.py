from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download all videos from a RedGifs user page with yt-dlp.")
    parser.add_argument("--user-url", required=True, help="RedGifs user URL, e.g. https://www.redgifs.com/users/name")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory where downloaded videos should be stored.")
    parser.add_argument(
        "--archive-txt",
        type=Path,
        default=None,
        help="yt-dlp download archive. Defaults to <output-dir>/redgifs_user_downloaded.txt.",
    )
    parser.add_argument("--sleep-interval", type=float, default=1.0, help="Seconds to sleep between downloads.")
    parser.add_argument(
        "--max-sleep-interval",
        type=float,
        default=3.0,
        help="Upper bound for randomized download sleep interval.",
    )
    parser.add_argument("--retries", type=int, default=10, help="yt-dlp retry count.")
    parser.add_argument("--playlist-start", type=int, default=1, help="Playlist item index to start from.")
    parser.add_argument("--playlist-end", type=int, default=0, help="Playlist item index to end at. 0 means no limit.")
    parser.add_argument("--write-info-json", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def build_output_template(output_dir: Path) -> str:
    return str(output_dir / "%(extractor)s_%(id)s_%(title).180B.%(ext)s")


def run_download(args: argparse.Namespace) -> None:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise SystemExit(
            "yt-dlp is not installed in the current environment. Run "
            "`make setup-redgifs-downloader` first."
        ) from exc

    output_dir = args.output_dir.resolve()
    archive_txt = (args.archive_txt or (output_dir / "redgifs_user_downloaded.txt")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_txt.parent.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "outtmpl": build_output_template(output_dir),
        "download_archive": str(archive_txt),
        "ignoreerrors": True,
        "retries": args.retries,
        "fragment_retries": args.retries,
        "sleep_interval": args.sleep_interval,
        "max_sleep_interval": args.max_sleep_interval,
        "restrictfilenames": False,
        "windowsfilenames": True,
        "continuedl": True,
        "overwrites": False,
        "writeinfojson": args.write_info_json,
        "writesubtitles": False,
        "quiet": False,
        "noplaylist": False,
        "playliststart": max(1, args.playlist_start),
    }
    if args.playlist_end > 0:
        ydl_opts["playlistend"] = args.playlist_end

    print(
        json.dumps(
            {
                "user_url": args.user_url,
                "output_dir": str(output_dir),
                "archive_txt": str(archive_txt),
                "playlist_start": max(1, args.playlist_start),
                "playlist_end": args.playlist_end,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([args.user_url])


def main() -> None:
    run_download(parse_args())


if __name__ == "__main__":
    main()
