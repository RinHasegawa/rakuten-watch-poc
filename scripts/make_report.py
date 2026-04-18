"""raw JSON を読み込み、共通スキーマに正規化し、類似判定をしてレポート出力する。

- 入力: data/raw/ranking_*.json, data/raw/search_*.json
         data/raw/brand_*.json, data/raw/brand_candidates_*.json
- 出力: data/processed/items_<date>.csv, reports/report_<date>.md

類似判定 A — reference_items ベース（整数加点、最大4点）:
    name_token  +2  基準名と候補名で2文字以上のトークンが1つ以上一致
    price_near  +1  価格差が基準価格の ±20% 以内
    genre_match +1  genre_id が完全一致

類似判定 B — brand_queries ベース（整数加点、最大4点）:
    name_token  +2  候補名にブランド商品群のトークン集合と共通するトークンが1つ以上ある
    price_range +1  候補価格がブランドの [price_min, price_max] 内
    genre_match +1  候補の genre_id がブランドの genre_ids 集合に含まれる
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

ROOT          = Path(__file__).resolve().parents[1]
WATCHLIST     = ROOT / "config" / "watchlist.yaml"
RAW_DIR       = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR   = ROOT / "reports"

# ルール閾値（触るならここだけ）
PRICE_NEAR_RATIO   = 0.20   # reference_items 用 ±20%
NAME_TOKEN_MIN_LEN = 2
NAME_TOKEN_POINTS  = 2
PRICE_NEAR_POINTS  = 1
GENRE_MATCH_POINTS = 1


# ---------- 読み込み & 正規化 ----------

def _load_raw_files() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(ranking_items, search_items) を共通スキーマで返す。"""
    ranking: list[dict[str, Any]] = []
    search:  list[dict[str, Any]] = []

    for path in sorted(RAW_DIR.glob("ranking_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for idx, raw in enumerate(data.get("Items", [])):
            inner = raw.get("Item", raw)
            rank  = inner.get("rank") or (idx + 1)
            ranking.append(
                normalize_rakuten_item(
                    raw, rank=int(rank) if rank else None,
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


def _load_brand_files() -> list[dict[str, Any]]:
    """
    brand_candidates_*.json を読み込み、以下を返す:
    [
        {
            "brand": str,
            "profile": {price_min, price_max, price_median, genre_ids},
            "name_tokens": set[str],   # brand_*.json から生成
            "candidates": [normalized_item, ...]
        },
        ...
    ]
    """
    token_re  = re.compile(r"[0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff]+")
    date_re   = re.compile(r"^brand_candidates_(.+)_(\d{8})$")
    result: list[dict[str, Any]] = []

    # ブランドごとに最新日付のファイルだけ使う
    latest_per_brand: dict[str, tuple[Path, str]] = {}
    for p in RAW_DIR.glob("brand_candidates_*.json"):
        m = date_re.match(p.stem)
        if not m:
            continue
        brand_slug, date_str = m.group(1), m.group(2)
        if brand_slug not in latest_per_brand or date_str > latest_per_brand[brand_slug][1]:
            latest_per_brand[brand_slug] = (p, date_str)

    for cand_path, _ in sorted(latest_per_brand.values(), key=lambda x: x[0].name):
        data = json.loads(cand_path.read_text(encoding="utf-8"))
        brand_name = data.get("brand", cand_path.stem)
        profile    = data.get("profile", {})

        # 対応する brand_*.json からトークン集合を再生成
        slug = cand_path.stem.replace("brand_candidates_", "")   # e.g. SK_II_20260417
        brand_files = list(RAW_DIR.glob(f"brand_{slug}.json"))
        name_tokens: set[str] = set()
        if brand_files:
            bdata = json.loads(brand_files[0].read_text(encoding="utf-8"))
            for raw in bdata.get("Items", []):
                item = raw.get("Item", raw)
                for t in token_re.findall(item.get("itemName", "")):
                    if len(t) >= NAME_TOKEN_MIN_LEN:
                        name_tokens.add(t)

        # 候補を正規化
        candidates = []
        for idx, raw in enumerate(data.get("Items", [])):
            candidates.append(
                normalize_rakuten_item(raw, rank=None, raw_ref=f"{cand_path.name}#{idx}")
            )

        # top_refs: ブランド人気上位N件（search_brand.py が top_as_reference で保存したもの）
        top_refs = []
        for idx, raw in enumerate(data.get("top_refs", [])):
            top_refs.append(
                normalize_rakuten_item(raw, rank=idx + 1, raw_ref=f"{cand_path.name}#ref{idx}")
            )

        result.append({
            "brand":       brand_name,
            "mode":        data.get("mode", "similar"),   # "popular" or "similar"
            "profile":     profile,
            "name_tokens": name_tokens,
            "candidates":  candidates,
            "top_refs":    top_refs,   # 類似検索の基準商品（空リストなら使わない）
        })

    return result


# ---------- 類似判定 A: reference_items ----------

_TOKEN_RE = re.compile(r"[0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff]+")


def _tokens(name: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(name or "") if len(t) >= NAME_TOKEN_MIN_LEN}


def score_against_reference(
    candidate: dict[str, Any],
    reference: dict[str, Any],
) -> tuple[int, list[str]]:
    matched: list[str] = []
    score   = 0

    ref_tokens  = _tokens(reference.get("name", ""))
    cand_tokens = _tokens(candidate.get("name", ""))
    if ref_tokens and cand_tokens and ref_tokens & cand_tokens:
        score += NAME_TOKEN_POINTS
        matched.append("name_token")

    ref_price  = reference.get("price")
    cand_price = candidate.get("price")
    if ref_price and cand_price:
        if abs(cand_price - ref_price) <= ref_price * PRICE_NEAR_RATIO:
            score += PRICE_NEAR_POINTS
            matched.append("price_near")

    ref_genre  = reference.get("genre_id")
    cand_genre = candidate.get("genre_id")
    if ref_genre and cand_genre and ref_genre == cand_genre:
        score += GENRE_MATCH_POINTS
        matched.append("genre_match")

    return score, matched


# ---------- 類似判定 B: brand_profile ----------

def score_against_brand(
    candidate: dict[str, Any],
    brand_name_tokens: set[str],
    profile: dict[str, Any],
) -> tuple[int, list[str]]:
    """
    ブランドプロフィール全体を基準に候補をスコアリングする。
    同じ最大4点 + matched_rules の枠組みで説明可能に保つ。
    """
    matched: list[str] = []
    score   = 0

    cand_tokens = _tokens(candidate.get("name", ""))
    if brand_name_tokens and cand_tokens and brand_name_tokens & cand_tokens:
        score += NAME_TOKEN_POINTS
        matched.append("name_token")

    cand_price = candidate.get("price")
    p_min = profile.get("price_min", 0)
    p_max = profile.get("price_max", 999_999_999)
    if cand_price and p_min <= cand_price <= p_max:
        score += PRICE_NEAR_POINTS
        matched.append("price_range")

    cand_genre   = candidate.get("genre_id")
    brand_genres = set(profile.get("genre_ids", []))
    if cand_genre and brand_genres and cand_genre in brand_genres:
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
    rank  = f"#{it['rank']} " if it.get("rank") else ""
    price = f"{it['price']:,}円" if it.get("price") else "-"
    review = f" ⭐{it['review_count']:,}件" if it.get("review_count") else ""
    return f"- {rank}[{it['name']}]({it['url']}) — {price}{review} (genre_id={it.get('genre_id')})"


def _md_similar_line(it: dict[str, Any]) -> str:
    price = f"{it['price']:,}円" if it.get("price") else "-"
    rules = ", ".join(it.get("matched_rules") or [])
    return (
        f"- score={it['similarity_score']} [{it['name']}]({it['url']}) — {price}\n"
        f"    - matched: {rules}"
    )


def _write_markdown(
    ranking:          list[dict[str, Any]],
    search:           list[dict[str, Any]],
    similar_by_ref:   list[tuple[dict[str, Any], list[dict[str, Any]]]],
    brand_results:    list[tuple[str, str, dict[str, Any], list[dict[str, Any]]]],
    top_ref_results:  list[tuple[str, list[tuple[dict[str, Any], list[dict[str, Any]]]]]],
    out: Path,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    date  = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = [f"# Rakuten Watch レポート ({date})", ""]

    # ── ランキング ──
    lines.append("## ランキング Top10")
    if ranking:
        for it in ranking[:10]:
            lines.append(_md_item_line(it))
    else:
        lines.append("_(ランキングデータがありません)_")
    lines.append("")

    # ── キーワード検索 ──
    lines.append("## キーワード検索結果（各先頭5件）")
    if search:
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
        lines.append("_(検索データがありません)_")
        lines.append("")

    # ── 基準商品による類似候補 ──
    lines.append("## 類似候補（reference_items 基準）")
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

    # ── ブランド類似候補 ──
    lines.append("## ブランド情報（brand_queries 基準）")
    if brand_results:
        for brand_name, mode, profile, candidates in brand_results:
            p_min = f"{profile.get('price_min', '-'):,}" if isinstance(profile.get('price_min'), int) else "-"
            p_max = f"{profile.get('price_max', '-'):,}" if isinstance(profile.get('price_max'), int) else "-"

            if mode == "popular":
                # カテゴリ未指定: ブランド自身の人気商品を一覧表示
                lines.append(
                    f"### {brand_name} の人気商品"
                    f"（価格帯 ¥{p_min}〜¥{p_max}）"
                )
                if not candidates:
                    lines.append("_(商品データがありません)_")
                else:
                    for it in candidates[:10]:
                        lines.append(_md_item_line(it))
            else:
                # カテゴリ指定: 類似商品をスコア付きで表示
                lines.append(
                    f"### {brand_name} に類似する商品"
                    f"（価格帯 ¥{p_min}〜¥{p_max} / genre_ids={profile.get('genre_ids', [])}）"
                )
                if not candidates:
                    lines.append("_(スコア1以上の類似候補なし)_")
                else:
                    for it in candidates[:10]:
                        lines.append(_md_similar_line(it))
            lines.append("")
    else:
        lines.append("_(brand_queries が watchlist.yaml にないか、search_brand.py 未実行)_")
        lines.append("")

    # ── ブランド人気TOP商品に類似する他ブランド商品（top_as_reference 指定時のみ） ──
    if top_ref_results:
        lines.append("## ブランド人気TOP商品に類似する他ブランド商品")
        for brand_name, ref_similar in top_ref_results:
            lines.append(f"### {brand_name} 人気上位商品を基準とした類似検索")
            for ref, similar_items in ref_similar:
                ref_price = f"¥{ref['price']:,}" if ref.get("price") else "-"
                ref_review = f" / レビュー{ref.get('review_count', 0):,}件" if ref.get("review_count") else ""
                lines.append(
                    f"#### 基準: {ref.get('name', '')[:60]}"
                    f"（{ref_price}{ref_review}、genre_id={ref.get('genre_id')}）"
                )
                if not similar_items:
                    lines.append("_(スコア1以上の類似候補なし)_")
                else:
                    for it in similar_items[:5]:
                        lines.append(_md_similar_line(it))
                lines.append("")
        lines.append("")

    lines.append("---")
    lines.append(
        "類似ルール A(reference): name_token(+2) / price_near ±20%(+1) / genre_match(+1)  \n"
        "類似ルール B(brand):     name_token(+2) / price_range(+1) / genre_match(+1)  \n"
        "類似ルール C(top_ref):   同上 A と同じルール（top_as_reference 指定ブランドのみ）"
    )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- メイン ----------

def main() -> None:
    config     = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}
    references = config.get("reference_items") or []

    ranking, search = _load_raw_files()
    all_items = ranking + search
    print(f"正規化: ranking={len(ranking)} / search={len(search)}")

    # 類似判定 A: reference_items
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
        print(f"  基準商品 '{ref.get('name')}' → 候補 {len(scored)} 件")

    # 類似判定 B: brand_queries
    brand_data   = _load_brand_files()
    brand_results: list[tuple[str, str, dict[str, Any], list[dict[str, Any]]]] = []
    # 類似判定 C: brand top_refs → all_items を相手に reference 類似検索
    top_ref_results: list[tuple[str, list[tuple[dict[str, Any], list[dict[str, Any]]]]]] = []

    for entry in brand_data:
        bname        = entry["brand"]
        mode         = entry.get("mode", "similar")
        profile      = entry["profile"]
        name_tokens  = entry["name_tokens"]
        candidates   = entry["candidates"]
        top_refs     = entry.get("top_refs", [])

        if mode == "popular":
            # カテゴリ未指定: スコアリングなし、人気順のまま
            brand_results.append((bname, mode, profile, candidates))
            print(f"  ブランド '{bname}' → 人気商品 {len(candidates)} 件（popular モード）")
        else:
            # 類似モード: スコアリングして絞り込み
            scored: list[dict[str, Any]] = []
            for cand in candidates:
                score, rules = score_against_brand(cand, name_tokens, profile)
                if score <= 0:
                    continue
                scored.append(
                    {**cand, "similarity_score": score, "matched_rules": rules,
                     "brand_ref": bname}
                )
            scored.sort(key=lambda x: x["similarity_score"], reverse=True)
            brand_results.append((bname, mode, profile, scored))
            print(f"  ブランド '{bname}' → 類似候補 {len(scored)} 件（similar モード）")

        # 類似判定 C: top_refs が指定されている場合、各基準商品で all_items を類似検索
        if top_refs:
            brand_token_re = re.compile(re.escape(bname), re.IGNORECASE)
            ref_similar: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
            for ref in top_refs:
                # ブランド自身の商品は除外してスコアリング
                scored_ref: list[dict[str, Any]] = []
                for cand in all_items:
                    if brand_token_re.search(cand.get("name", "")):
                        continue   # 同ブランド除外
                    score, rules = score_against_reference(cand, ref)
                    if score <= 0:
                        continue
                    scored_ref.append(
                        {**cand, "similarity_score": score, "matched_rules": rules,
                         "reference_id": ref.get("id")}
                    )
                scored_ref.sort(key=lambda x: x["similarity_score"], reverse=True)
                ref_similar.append((ref, scored_ref))
                print(f"    top_ref '{ref.get('name', '')[:40]}' → 類似 {len(scored_ref)} 件")
            top_ref_results.append((bname, ref_similar))

    date    = datetime.now().strftime("%Y%m%d")
    csv_out = PROCESSED_DIR / f"items_{date}.csv"
    md_out  = REPORTS_DIR   / f"report_{date}.md"

    _write_csv(all_items, csv_out)
    _write_markdown(ranking, search, similar_by_ref, brand_results, top_ref_results, md_out)

    print(f"CSV : {csv_out.relative_to(ROOT)}")
    print(f"MD  : {md_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
