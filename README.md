# Rakuten Watch PoC

楽天市場の公式 API を使って、ランキング・キーワード検索・類似候補抽出を行う最小 PoC。
Claude Code からも、素の Python からも同じように動かせます。

## できること
- 楽天ランキング(ジャンル別)取得
- キーワード検索
- 基準商品に対するルールベースの類似候補抽出
- Markdown + CSV のレポート出力

## セットアップ(5分)
```bash
# 1. 仮想環境(任意)
python3 -m venv .venv && source .venv/bin/activate

# 2. 依存
pip install -r requirements.txt

# 3. APIキー
cp .env.example .env
# .env を開いて RAKUTEN_APP_ID を埋める
# 取得: https://webservice.rakuten.co.jp/
```

## 実行
```bash
python scripts/fetch_ranking.py   # ランキング → data/raw/
python scripts/search_items.py    # 検索      → data/raw/
python scripts/make_report.py     # 整形+類似 → reports/report_YYYYMMDD.md
```

## 触る場所
- 監視対象: `config/watchlist.yaml`
- 類似ルール閾値: `scripts/make_report.py` の上部定数

## ディレクトリ
```
config/         監視対象の宣言
scripts/        取得・検索・整形の3本 + ユーティリティ2本
data/raw/       APIレスポンスそのまま(再実験用に保持)
data/processed/ 共通スキーマ正規化後のCSV
reports/        Markdownレポート
.claude/skills/ Claude Code から呼び出す実行導線
```

## Claude Code から
`.claude/skills/rakuten-watch/SKILL.md` の手順を参照。3スクリプトを順に実行して最新レポートを開きます。
