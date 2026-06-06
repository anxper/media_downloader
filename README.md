# media_downloader

Local orchestration for two metadata/link crawlers plus a separate media download step.

This repository does not crawl sites directly. It sets up crawler repositories under
`tools/`, runs them to collect URL lists/metadata, then downloads collected media with
`yt-dlp`.

## Crawlers

| Crawler | Local path | Purpose |
|---------|------------|---------|
| `pornhub_metadata_crawler` | `tools/pornhub_metadata_crawler` | Collects PornHub model video metadata into `data/*.json`. |
| `reddit_media_link_crawler` | `tools/reddit_media_link_crawler` | Exports subreddit posts into `posts.json`, `redgifs.txt`, `other_links.txt`, and text buckets. |

## Install

Install this downloader's dependencies:

```bash
pip install -r requirements.txt
```

Set up both crawler checkouts and their own virtual environments:

```bash
python scripts/setup_crawlers.py
```

Defaults:

- PornHub crawler is cloned from `https://github.com/anxper/pornhub_metadata_crawler.git`.
- Reddit crawler uses sibling `../reddit_media_link_crawler` when it exists; otherwise it tries `https://github.com/anxper/reddit_media_link_crawler.git`.

Override either source when needed:

```bash
python scripts/setup_crawlers.py --reddit-repo D:\Projects\reddit_media_link_crawler
python scripts/setup_crawlers.py --pornhub-repo https://github.com/anxper/pornhub_metadata_crawler.git
```

## PornHub Flow

Create a private model list:

```text
input/pornhub_models.txt
https://www.pornhub.com/model/example/videos
https://www.pornhub.com/pornstar/example/videos/upload
```

Write crawler config:

```bash
python scripts/write_pornhub_crawler_config.py --models-txt input/pornhub_models.txt
```

Collect metadata:

```bash
python scripts/run_pornhub_crawler.py
```

Download collected media:

```bash
python scripts/download_media.py ^
  --pornhub-data-dir tools/pornhub_metadata_crawler/data ^
  --output-root downloads/pornhub
```

## Reddit Flow

Collect subreddit links:

```bash
python scripts/run_reddit_crawler.py --subreddit example_subreddit
```

Optionally check `other_links.txt` availability:

```bash
python scripts/run_reddit_crawler.py --subreddit example_subreddit --check-other-links
```

Download collected Reddit media links:

```bash
python scripts/download_media.py ^
  --reddit-posts-json output/reddit/example_subreddit/posts.json ^
  --output-root downloads/reddit
```

To download only RedGifs exported by the Reddit crawler:

```bash
python scripts/download_media.py ^
  --urls-txt output/reddit/example_subreddit/redgifs.txt ^
  --name reddit_example_subreddit_redgifs ^
  --output-root downloads/reddit
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup_crawlers.py` | Clone/update both crawler repos under `tools/`, create venvs, install deps, install Playwright Chromium. |
| `scripts/write_pornhub_crawler_config.py` | Generate `tools/pornhub_metadata_crawler/config.json` from a private model URL list. |
| `scripts/run_pornhub_crawler.py` | Run the local PornHub crawler and mirror console output to `output/pornhub_metadata_crawler.log`. |
| `scripts/run_reddit_crawler.py` | Run the local Reddit crawler export, optionally followed by link availability checks. |
| `scripts/download_media.py` | Download media from PornHub crawler JSON, Reddit crawler JSON, or a plain URL txt file. |
| `scripts/download_redgifs_user.py` | Utility for downloading all media from one RedGifs user page. |
| `scripts/download_redgifs.py` | Legacy helper for old Reddit RedGifs JSON exports. Prefer `download_media.py --urls-txt`. |

`FFmpeg` on `PATH` is recommended for `yt-dlp` muxing.
