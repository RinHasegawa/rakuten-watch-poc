"""楽天ランキングをジャンル別に取得して data/raw/ に保存する。

watchlist.yaml の `genre_ids` を順に回すだけ。整形や類似判定はしない。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

from _rakuten import get_ranking

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "config" / "watchlist.yaml"
RAW_DIR = ROOT / "data" / "raw"


def main() -> None:
    config = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8"))
    genre_ids: list[int] = config.get("genre_ids") or []
    if not genre_ids:
        print("watchlist.yaml に genre_ids が無いのでスキップしました。")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")

    for gid in genre_ids:
        print(f"[ranking] genre_id={gid} 取得中...")
        data = get_ranking(gid)
        out = RAW_DIR / f"ranking_{gid}_{date}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        items = data.get("Items", [])
        print(f"  → {out.relative_to(ROOT)} ({len(items)} items)")


if __name__ == "__main__":
    main()
