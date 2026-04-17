---
name: rakuten-watch
description: 楽天市場のランキング取得・キーワード検索・類似候補抽出を実行し、最新レポートを表示する。ユーザーが「ランキング確認」「類似商品を集めて」「watch 回して」「情報収集して」などと言ったときに使う。セットアップも含めて自動で処理する。
---

# rakuten-watch

楽天市場の公式 API を使って、ランキング・検索・類似判定を一括で走らせる Skill。
**セットアップ(依存インストール・.env 準備)も含めて自動で処理する。手動操作は不要。**

---

## 実行手順(必ずこの順番で行う)

### Step 0 — セットアップ確認

**① .venv がなければ作成してパッケージをインストール**
```bash
uv venv .venv --quiet && uv pip install -r requirements.txt --quiet
```
`uv` がない場合は `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -q` で代替する。
エラーが出た場合のみユーザーに報告する。

**② .env の準備**
`.env` が存在しない場合のみ、`.env.example` からコピーして作成する:
```bash
cp .env.example .env
```
すでに `.env` があればスキップする。

**③ API キーの確認**
```bash
.venv/bin/python -c "from dotenv import load_dotenv; import os; load_dotenv(); a=os.getenv('RAKUTEN_APP_ID',''); k=os.getenv('RAKUTEN_ACCESS_KEY',''); print('OK' if a and k and 'your_' not in a else 'NG')"
```
`OK` が返れば次へ進む。`NG` の場合は「`.env` の `RAKUTEN_APP_ID` / `RAKUTEN_ACCESS_KEY` を確認してください」とユーザーに伝えて止まる。

---

### Step 1 — 一括実行
```bash
.venv/bin/python run_all.py
```
内部で `fetch_ranking.py` → `search_items.py` → `make_report.py` を順に実行し、
最後にレポート全文を標準出力に表示する。

### Step 2 — レポート要約
`run_all.py` の出力、または生成された `reports/report_YYYYMMDD.md`(日付が最新のもの)を Read して、
以下のポイントをユーザーに日本語で要約する:
- ランキング Top5 の商品名・価格
- 類似候補の中でスコアが高い商品(matched_rules つき)

---

## 監視対象の変更
`config/watchlist.yaml` を編集する:
- `genre_ids` … ランキングを取りたい楽天ジャンルID(例: 100939 = 美容・コスメ)
- `keywords` … 検索語(例: スキンケア、美容液)
- `reference_items` … 類似判定の基準商品(name / price / genre_id を直接書く)

---

## 類似判定ルール(参考)
| ルール | 点数 | 条件 |
|---|---|---|
| `name_token` | +2 | 商品名の2文字以上のトークンが1つ以上一致 |
| `price_near` | +1 | 価格差が基準価格の ±20% 以内 |
| `genre_match` | +1 | genre_id が完全一致 |

閾値を変えたいときは `scripts/make_report.py` の上部定数だけ触ればよい。

---

## 注意
- `data/raw/` のファイルは削除しない(再実験用に保持)
- `brand` などの推測値カラムは追加しない(説明責任のため)
- 新しいキーワードやジャンルを追加したいときは `config/watchlist.yaml` を編集してから再実行する
