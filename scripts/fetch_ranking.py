"""楽天ランキングをジャンル別に取得して data/raw/ に保存する。

watchlist.yaml の `genre_ids` を起点に、子ジャンルがあれば再帰的に末端まで展開してから
それぞれのランキングを取得する。整形や類似判定はしない。

例:
  genre_ids: [100944]  # スキンケア（親）
  → ジャンルAPIで子を展開 → 末端の全サブカテゴリのランキングを一括取得

  genre_ids: [216348]  # 美容液（末端）
  → 子なし → そのまま美容液ランキングを取得
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import yaml

from _rakuten import get_genre_children, get_ranking

ROOT      = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "config" / "watchlist.yaml"
RAW_DIR   = ROOT / "data" / "raw"

_GENRE_API_WAIT = 0.3   # ジャンルAPI 連続呼び出し間隔(秒)
_RANK_API_WAIT  = 0.5   # ランキングAPI 連続呼び出し間隔(秒)


# ---------- ジャンル再帰展開 ----------

def resolve_leaf_genres(
    genre_id: int,
    name: str = "",
    _visited: set[int] | None = None,
) -> list[dict[str, int | str]]:
    """
    genre_id が末端なら [{genreId, nameJa}] を返す。
    子がある場合は再帰的に末端まで辿り、リーフのみを返す。
    循環参照ガード付き。
    """
    if _visited is None:
        _visited = set()
    if genre_id in _visited:
        return []
    _visited.add(genre_id)

    time.sleep(_GENRE_API_WAIT)
    children = get_genre_children(genre_id)

    if not children:
        # 末端 → そのまま返す
        return [{"genreId": genre_id, "nameJa": name or str(genre_id)}]

    # 子あり → 各子を再帰展開
    leaves: list[dict[str, int | str]] = []
    for child in children:
        leaves.extend(
            resolve_leaf_genres(
                child["genreId"],
                child.get("nameJa", ""),
                _visited,
            )
        )
    return leaves


def collect_leaf_genres(genre_ids: list[int]) -> list[dict[str, int | str]]:
    """watchlist の genre_ids リストを末端ジャンルに展開し、重複を除いて返す。"""
    seen: set[int] = set()
    result: list[dict[str, int | str]] = []

    for gid in genre_ids:
        for leaf in resolve_leaf_genres(gid):
            if leaf["genreId"] not in seen:
                seen.add(leaf["genreId"])
                result.append(leaf)

    return result


# ---------- メイン ----------

def main() -> None:
    config    = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8"))
    genre_ids: list[int] = config.get("genre_ids") or []

    if not genre_ids:
        print("watchlist.yaml に genre_ids が無いのでスキップしました。")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")

    print(f"ジャンル展開中: {genre_ids} ...")
    leaves = collect_leaf_genres(genre_ids)
    print(f"→ 末端ジャンル {len(leaves)} 件に展開しました\n")

    for leaf in leaves:
        gid  = leaf["genreId"]
        name = leaf["nameJa"]
        print(f"[ranking] {name}(genre_id={gid}) 取得中...")
        data = get_ranking(gid)
        out  = RAW_DIR / f"ranking_{gid}_{date}.json"
        out.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        items = data.get("Items", [])
        print(f"  → {out.relative_to(ROOT)} ({len(items)} items)")
        time.sleep(_RANK_API_WAIT)


if __name__ == "__main__":
    main()
