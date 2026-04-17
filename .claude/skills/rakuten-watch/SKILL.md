---
name: rakuten-watch
description: 楽天市場のランキング取得・キーワード検索・類似候補抽出を実行し、最新レポートを表示する。ユーザーが「ランキング確認」「類似商品を集めて」「watch 回して」などと言ったときに使う。
---

# rakuten-watch

楽天市場の公式 API を使って、ランキング・検索・類似判定を一括で走らせるための実行導線。
ロジックは Python スクリプトに置いてあり、この Skill は手順と前提確認だけを担う。

## 前提
- プロジェクトルート: このリポジトリのトップ階層
- `.env` に `RAKUTEN_APP_ID` が設定済みであること(未設定ならユーザーに案内する)
- `requirements.txt` の依存がインストール済みであること

## 実行手順
以下を順番に実行する。途中でエラーが出たら、そこで止めてユーザーに原因を説明する。

1. **ランキング取得**
   ```bash
   python scripts/fetch_ranking.py
   ```
2. **キーワード検索**
   ```bash
   python scripts/search_items.py
   ```
3. **整形 + 類似判定 + レポート**
   ```bash
   python scripts/make_report.py
   ```
4. 生成された最新レポート `reports/report_YYYYMMDD.md` を Read して、
   「ランキング Top10」「類似候補」セクションのハイライトをユーザーに要約する。

## 監視対象の変更
`config/watchlist.yaml` を編集する:
- `genre_ids` … ランキングを取りたい楽天ジャンルID
- `keywords` … 検索語
- `reference_items` … 類似判定の基準商品(name / price / genre_id)

## 類似ルール(参考)
- `name_token`(+2): 基準名と2文字以上のトークンが1つ以上一致
- `price_near`(+1): 価格差が基準価格の ±20% 以内
- `genre_match`(+1): genre_id が完全一致
- 閾値は `scripts/make_report.py` 冒頭の定数で調整可能

## 触らない場所
- `data/raw/` は削除しない(再実験のため保持)
- `scripts/_schema.py` の共通カラムは相談なしに増やさない(特に推測値の brand 等)
