# Claude Code 向けメモ

このリポジトリは楽天市場の最小情報収集 PoC です。
作業時に守ってほしい前提を以下にまとめます。

## 前提
- API キーは `.env` の `RAKUTEN_APP_ID` から読む。コードに直書きしない。
- 楽天 API は公式のみ使用。スクレイピングはしない。
- raw データ(`data/raw/`)は消さない。再実験・再整形のために保持する。

## スクリプトの責務
- `scripts/fetch_ranking.py` … ランキング取得 → raw 保存のみ
- `scripts/search_items.py` … キーワード検索 → raw 保存のみ
- `scripts/make_report.py` … raw 読込 → 正規化 → 類似判定 → CSV/Markdown 出力
- `scripts/_rakuten.py` … 楽天 API クライアント(adapter 差し替え点)
- `scripts/_schema.py` … 共通スキーマへの正規化(唯一の場所)

## 共通スキーマ(変更時は要相談)
```
id, source, fetched_at, rank, name, price, genre_id, url, image_url, raw_ref
```
- **`brand` 等の推測値カラムは追加しない**(説明責任のため)
- 新しい source を足すときは `_schema.py` でこのカラムに揃える

## 類似判定
- ルールベース、整数加点(最大4点)、`matched_rules` で説明
- 重み付き小数スコアにしない。閾値は1か所(`make_report.py` 冒頭)

## 拡張時の指針
- 新しい EC サイト → `_<source>.py` を追加し `_schema.py` に正規化関数を1つ足す
- embedding 等はスコア関数の差し替えで対応(構造は変えない)
