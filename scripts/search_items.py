"""楽天商品検索をキーワードで回して data/raw/ に保存する。

watchlist.yaml の `keywords` を順に検索するだけ。整形や類似判定はしない。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import yaml

from _rakuten import search_items

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "config" / "watchlist.yaml"
RAW_DIR = ROOT / "data" / "raw"


def _slug(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff]+", "_", s).strip("_")


def main() -> None:
    config = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8"))
    keywords: list[str] = config.get("keywords") or []
    if not keywords:
        print("watchlist.yaml に keywords が無いのでスキップしました。")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")

    for kw in keywords:
        print(f"[search] keyword={kw!r} 取得中...")
        data = search_items(kw)
        out = RAW_DIR / f"search_{_slug(kw)}_{date}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        items = data.get("Items", [])
        print(f"  → {out.relative_to(ROOT)} ({len(items)} items)")


if __name__ == "__main__":
    main()
