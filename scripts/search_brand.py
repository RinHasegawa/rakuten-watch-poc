"""特定ブランドの商品を検索し、類似候補を収集して data/raw/ に保存する。

責務: raw データの保存のみ。スコアリング・レポート出力は make_report.py が行う。

フロー:
  1. watchlist.yaml の brand_queries を読む
  2. ブランド名（＋任意でカテゴリ）で楽天検索 → data/raw/brand_{slug}_{date}.json
  3. 結果からブランドプロフィール（価格帯・genre_id集合）を生成
  4. 主要 genre_id で候補商品を検索 → data/raw/brand_candidates_{slug}_{date}.json

将来別 EC サイトに対応するときは source パラメータで切り替える（現在は "rakuten" 固定）。
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

import yaml

from _rakuten import search_items
from _schema import normalize_rakuten_item

ROOT      = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "config" / "watchlist.yaml"
RAW_DIR   = ROOT / "data" / "raw"

_API_WAIT = 0.5   # API 連続呼び出し間隔（秒）
_BRAND_HITS      = 30   # ブランド検索で取得する商品数
_CANDIDATE_HITS  = 30   # 候補検索で取得する商品数
_TOP_GENRE_LIMIT = 3    # 候補検索に使う主要 genre_id の上限数


# ---------- ユーティリティ ----------

def _slug(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff]+", "_", s).strip("_")


def _normalize_all(raw_data: dict[str, Any], file_ref: str) -> list[dict[str, Any]]:
    items = []
    for idx, raw in enumerate(raw_data.get("Items", [])):
        items.append(
            normalize_rakuten_item(raw, rank=None, raw_ref=f"{file_ref}#{idx}")
        )
    return items


# ---------- ブランドプロフィール生成 ----------

def build_brand_profile(
    brand_name: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    正規化済みのブランド商品リストからプロフィールを生成する。

    返り値:
        {
            "name": str,
            "name_tokens": set[str],   # 全商品名のトークン和集合
            "price_min": int,          # 最小価格 × 0.8（バッファ込み）
            "price_max": int,          # 最大価格 × 1.2（バッファ込み）
            "price_median": float,
            "genre_ids": list[int],    # 出現頻度順
        }
    """
    token_re = re.compile(r"[0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff]+")

    all_tokens: set[str] = set()
    prices: list[int] = []
    genre_count: dict[int, int] = {}

    for item in items:
        # トークン収集
        for t in token_re.findall(item.get("name", "")):
            if len(t) >= 2:
                all_tokens.add(t)

        # 価格収集
        p = item.get("price")
        if p and p > 0:
            prices.append(p)

        # genre_id カウント
        gid = item.get("genre_id")
        if gid:
            genre_count[gid] = genre_count.get(gid, 0) + 1

    price_min = int(min(prices) * 0.8) if prices else 0
    price_max = int(max(prices) * 1.2) if prices else 999_999_999
    price_med = float(median(prices)) if prices else 0.0

    # genre_id を頻度順に並べ上位を候補検索に使う
    sorted_genres = sorted(genre_count, key=lambda g: -genre_count[g])

    return {
        "name": brand_name,
        "name_tokens": all_tokens,
        "price_min": price_min,
        "price_max": price_max,
        "price_median": price_med,
        "genre_ids": sorted_genres,
    }


# ---------- メイン ----------

def main() -> None:
    config = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}
    brand_queries: list[dict[str, str]] = config.get("brand_queries") or []

    if not brand_queries:
        print("watchlist.yaml に brand_queries が無いのでスキップしました。")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")

    for brand in brand_queries:
        bname    = brand.get("name", "").strip()
        category = brand.get("category", "").strip()
        if not bname:
            continue

        slug = _slug(bname)
        query = f"{bname} {category}".strip() if category else bname

        # ① ブランド商品検索
        print(f"\n[brand] '{query}' 検索中...")
        brand_raw = search_items(query, hits=_BRAND_HITS)
        brand_file = RAW_DIR / f"brand_{slug}_{date}.json"
        brand_file.write_text(
            json.dumps(brand_raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        brand_items = _normalize_all(brand_raw, brand_file.name)
        print(f"  → {brand_file.relative_to(ROOT)} ({len(brand_items)} items)")
        time.sleep(_API_WAIT)

        if not brand_items:
            print(f"  ⚠ {bname} の検索結果が空でした。スキップします。")
            continue

        # ② ブランドプロフィール生成
        profile = build_brand_profile(bname, brand_items)
        top_genres = profile["genre_ids"][:_TOP_GENRE_LIMIT]
        print(f"  プロフィール: price=[{profile['price_min']:,}〜{profile['price_max']:,}円] "
              f"genre_ids={top_genres}")

        # ③ 主要 genre_id で候補検索（genre_id ごとにカテゴリキーワードで検索）
        candidates_raw_items: list[dict[str, Any]] = []
        for gid in top_genres:
            # genre_id を使った絞り込みは Search API の genreId パラメータで行う
            # 現行 search_items() は keyword のみ対応のため、ブランド名を除いた
            # カテゴリキーワードで検索し genre_id はレポート側でフィルタする
            cand_query = category if category else bname
            print(f"  [candidates] genre_id={gid} keyword='{cand_query}' 候補収集中...")
            cand_raw = search_items(cand_query, hits=_CANDIDATE_HITS)
            candidates_raw_items.extend(cand_raw.get("Items", []))
            time.sleep(_API_WAIT)

        # 重複除去（itemCode ベース）
        seen_ids: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for raw_item in candidates_raw_items:
            item_code = raw_item.get("Item", raw_item).get("itemCode", "")
            if item_code and item_code not in seen_ids:
                seen_ids.add(item_code)
                deduped.append(raw_item)

        # ブランド自身の商品を候補から除外（ブランド名トークンが一致しすぎるもの）
        brand_token_re = re.compile(re.escape(bname), re.IGNORECASE)
        filtered = [
            it for it in deduped
            if not brand_token_re.search(it.get("Item", it).get("itemName", ""))
        ]

        # candidates を保存
        cand_payload = {"brand": bname, "profile": {
            "price_min": profile["price_min"],
            "price_max": profile["price_max"],
            "price_median": profile["price_median"],
            "genre_ids": profile["genre_ids"],
        }, "Items": filtered}

        cand_file = RAW_DIR / f"brand_candidates_{slug}_{date}.json"
        cand_file.write_text(
            json.dumps(cand_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  → {cand_file.relative_to(ROOT)} ({len(filtered)} candidates)")


if __name__ == "__main__":
    main()
