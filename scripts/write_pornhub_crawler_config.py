from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse, urlunparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write config.json for pornhub_metadata_crawler.")
    parser.add_argument(
        "--config-json",
        type=Path,
        default=Path("tools") / "pornhub_metadata_crawler" / "config.json",
    )
    parser.add_argument(
        "--models-txt",
        type=Path,
        default=Path("input") / "pornhub_models.txt",
        help="Text file with one PornHub model/pornstar URL per line.",
    )
    parser.add_argument("--delay-between-pages", type=float, default=2.0)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def normalize_model_url(model_url: str) -> str:
    value = model_url.strip()
    if not value:
        return value

    parsed = urlparse(value)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or "www.pornhub.com"
    if netloc.endswith("pornhub.com"):
        netloc = "www.pornhub.com"

    path = parsed.path.rstrip("/")
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0] in {"model", "pornstar"}:
        profile_type = parts[0]
        profile_name = parts[1]
        if profile_type == "model":
            path = f"/model/{profile_name}/videos"
        else:
            path = f"/pornstar/{profile_name}/videos/upload"

    return urlunparse((scheme, netloc, path, "", "", ""))


def read_models(models_txt: Path) -> list[str]:
    if not models_txt.exists():
        raise SystemExit(f"Model list not found: {models_txt}")

    models: list[str] = []
    seen: set[str] = set()
    for raw_line in models_txt.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        normalized = normalize_model_url(line)
        if normalized in seen:
            continue
        seen.add(normalized)
        models.append(normalized)
    return models


def main() -> None:
    args = parse_args()
    models = read_models(args.models_txt)
    if not models:
        raise SystemExit(f"No model URLs found in {args.models_txt}")

    payload = {
        "models": models,
        "delay_between_pages": args.delay_between_pages,
        "headless": args.headless,
    }
    args.config_json.parent.mkdir(parents=True, exist_ok=True)
    args.config_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "config_json": str(args.config_json),
                "models_txt": str(args.models_txt),
                "models_count": len(models),
                "headless": args.headless,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
