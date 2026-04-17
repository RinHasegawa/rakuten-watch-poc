"""共通スキーマへの正規化。

共通スキーマ:
    id, source, fetched_at, rank, name, price, genre_id, url, image_url, raw_ref

推測値カラム(brand 等)は意図的に持たない。
新しい source を足すときは、この共通スキーマに揃えた dict を返す関数をここに追加する。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

COLUMNS = [
    "id",
    "source",
    "fetched_at",
    "rank",
    "name",
    "price",
    "genre_id",
    "url",
    "image_url",
    "raw_ref",
]


def normalize_rakuten_item(
    raw_item: dict[str, Any],
    *,
    rank: int | None,
    raw_ref: str,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """楽天 API の 1 アイテム(Items[n]["Item"])を共通スキーマに変換する。"""
    item = raw_item.get("Item", raw_item)

    image_url = None
    images = item.get("mediumImageUrls") or []
    if images:
        first = images[0]
        image_url = first.get("imageUrl") if isinstance(first, dict) else first

    return {
        "id": item.get("itemCode"),
        "source": "rakuten",
        "fetched_at": fetched_at or datetime.now().isoformat(timespec="seconds"),
        "rank": rank,
        "name": item.get("itemName") or "",
        "price": int(item.get("itemPrice") or 0),
        "genre_id": int(item.get("genreId")) if item.get("genreId") else None,
        "url": item.get("itemUrl") or "",
        "image_url": image_url,
        "raw_ref": raw_ref,
    }
