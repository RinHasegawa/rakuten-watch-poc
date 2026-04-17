# Rakuten Watch レポート (YYYY-MM-DD) — サンプル

## ランキング Top10
- #1 [商品名A](https://item.rakuten.co.jp/...) — 2,980円 (genre_id=100939)
- #2 [商品名B](https://item.rakuten.co.jp/...) — 3,480円 (genre_id=100939)
- ...

## キーワード検索結果(各先頭5件)
### search_スキンケア_YYYYMMDD.json
- [商品名C](https://item.rakuten.co.jp/...) — 1,980円 (genre_id=100939)
- ...

## 類似候補(基準商品ごと)
### 基準: サンプル美容液 30ml (price=3000, genre_id=100939)
- score=4 [類似商品X](https://item.rakuten.co.jp/...) — 3,200円
    - matched: name_token, price_near, genre_match
- score=3 [類似商品Y](https://item.rakuten.co.jp/...) — 2,800円
    - matched: name_token, price_near

---
類似ルール: name_token(+2) / price_near ±20%(+1) / genre_match(+1)
