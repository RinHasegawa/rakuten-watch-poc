"""raw JSON を読み込み、共通スキーマに正規化し、類似判定をしてレポート出力する。

- 入力: data/raw/ranking_*.json, data/raw/search_*.json
- 出力: data/processed/items_<date>.csv, reports/report_<date>.md

類似判定(整数加点、最大4点):
    name_token  +2  基準名と候補名で2文字以上のトークンが1つ以上一致
    price_near  +1  価格差が基準価格の ±20% 以内
    genre_match +1  genre_id が完全一致
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from _schema import COLUMNS, normalize_rakuten_item

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "config" / "watchlist.yaml"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"

# ルール閾値(触るならここだけ)
PRICE_NEAR_RATIO = 0.20  # ±20%
NAME_TOKEN_MIN_LEN = 2
NAME_TOKEN_POINTS = 2
PRICE_NEAR_POINTS = 1
GENRE_MATCH_POINTS = 1


# ---------- 読み込み & 正規化 ----------

def _load_raw_files() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(ranking_items, search_items) を共通スキーマで返す。"""
    ranking: list[dict[str, Any]] = []
    search: list[dict[str, Any]] = []

    for path in sorted(RAW_DIR.glob("ranking_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for idx, raw in enumerate(data.get("Items", [])):
            inner = raw.get("Item", raw)
            rank = inner.get("rank") or (idx + 1)
            ranking.append(
                normalize_rakuten_item(
                    raw,
                    rank=int(rank) if rank else None,
                    raw_ref=f"{path.name}#{idx}",
                )
            )

    for path in sorted(RAW_DIR.glob("search_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for idx, raw in enumerate(data.get("Items", [])):
            search.append(
                normalize_rakuten_item(raw, rank=None, raw_ref=f"{path.name}#{idx}")
            )

    return ranking, search


# ---------- 類似判定 ----------

_TOKEN_RE = re.compile(r"[0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff]+")


def _tokens(name: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(name or "") if len(t) >= NAME_TOKEN_MIN_LEN}


def score_against_reference(
    candidate: dict[str, Any], reference: dict[str, Any]
) -> tuple[int, list[str]]:
    matched: list[str] = []
    score = 0

    ref_tokens = _tokens(reference.get("name", ""))
    cand_tokens = _tokens(candidate.get("name", ""))
    if ref_tokens and cand_tokens and ref_tokens & cand_tokens:
        score += NAME_TOKEN_POINTS
        matched.append("name_token")

    ref_price = reference.get("price")
    cand_price = candidate.get("price")
    if ref_price and cand_price:
        if abs(cand_price - ref_price) <= ref_price * PRICE_NEAR_RATIO:
            score += PRICE_NEAR_POINTS
            matched.append("price_near")

    ref_genre = reference.get("genre_id")
    cand_genre = candidate.get("genre_id")
    if ref_genre and cand_genre and ref_genre == cand_genre:
        score += GENRE_MATCH_POINTS
        matched.append("genre_match")

    return score, matched


# ---------- 出力 ----------

def _write_csv(items: list[dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for it in items:
            w.writerow({c: it.get(c) for c in COLUMNS})


def _md_item_line(it: dict[str, Any]) -> str:
    rank = f"#{it['rank']} " if it.get("rank") else ""
    price = f"{it['price']:,}円" if it.get("price") else "-"
    return f"- {rank}[{it['name']}]({it['url']}) — {price} (genre_id={it.get('genre_id')})"


def _md_similar_line(it: dict[str, Any]) -> str:
    price = f"{it['price']:,}円" if it.get("price") else "-"
    rules = ", ".join(it.get("matched_rules") or [])
    return (
        f"- score={it['similarity_score']} [{it['name']}]({it['url']}) — {price}\n"
        f"    - matched: {rules}"
    )


def _write_markdown(
    ranking: list[dict[str, Any]],
    search: list[dict[str, Any]],
    similar_by_ref: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    out: Path,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = [f"# Rakuten Watch レポート ({date})", ""]

    lines.append("## ランキング Top10")
    if ranking:
        for it in ranking[:10]:
            lines.append(_md_item_line(it))
    else:
        lines.append("_(ランキングデータがありません。fetch_ranking.py を先に実行してください)_")
    lines.append("")

    lines.append("## キーワード検索結果(各先頭5件)")
    if search:
        # raw_ref のファイル名プレフィックスでざっくりグルーピング
        by_file: dict[str, list[dict[str, Any]]] = {}
        for it in search:
            key = it["raw_ref"].split("#", 1)[0]
            by_file.setdefault(key, []).append(it)
        for key, group in by_file.items():
            lines.append(f"### {key}")
            for it in group[:5]:
                lines.append(_md_item_line(it))
            lines.append("")
    else:
        lines.append("_(検索データがありません。search_items.py を先に実行してください)_")
        lines.append("")

    lines.append("## 類似候補(基準商品ごと)")
    if similar_by_ref:
        for ref, candidates in similar_by_ref:
            lines.append(
                f"### 基準: {ref.get('name')} "
                f"(price={ref.get('price')}, genre_id={ref.get('genre_id')})"
            )
            if not candidates:
                lines.append("_(スコア1以上の候補なし)_")
            else:
                for it in candidates[:10]:
                    lines.append(_md_similar_line(it))
            lines.append("")
    else:
        lines.append("_(reference_items が watchlist.yaml にありません)_")
        lines.append("")

    lines.append("---")
    lines.append("類似ルール: name_token(+2) / price_near ±20%(+1) / genre_match(+1)")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- メイン ----------

def main() -> None:
    config = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}
    references: list[dict[str, Any]] = config.get("reference_items") or []

    ranking, search = _load_raw_files()
    all_items = ranking + search
    print(f"正規化: ranking={len(ranking)} / search={len(search)}")

    similar_by_ref: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for ref in references:
        scored: list[dict[str, Any]] = []
        for cand in all_items:
            score, rules = score_against_reference(cand, ref)
            if score <= 0:
                continue
            scored.append(
                {**cand, "similarity_score": score, "matched_rules": rules,
                 "reference_id": ref.get("id")}
            )
        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        similar_by_ref.append((ref, scored))
        print(f"  基準 '{ref.get('name')}' → 候補 {len(scored)} 件")

    date = datetime.now().strftime("%Y%m%d")
    csv_out = PROCESSED_DIR / f"items_{date}.csv"
    md_out = REPORTS_DIR / f"report_{date}.md"

    _write_csv(all_items, csv_out)
    _write_markdown(ranking, search, similar_by_ref, md_out)

    print(f"CSV : {csv_out.relative_to(ROOT)}")
    print(f"MD  : {md_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
