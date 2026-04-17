"""楽天ウェブサービス API の薄いラッパ。

公開関数:
- get_ranking(genre_id)          … IchibaItem/Ranking
- search_items(keyword)          … IchibaItem/Search
- get_genre_children(genre_id)   … IchibaGenre/Search（子ジャンル一覧）

【2025年現行仕様】
- エンドポイントが openapi.rakuten.co.jp ベースに変更済み
- applicationId に加え accessKey が必須（両方 .env に設定）
- .env: RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY

将来、別 EC サイトに差し替えるときはこのファイルと同じ I/F のモジュールを追加する。
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

# 2025年現行エンドポイント
RANKING_URL = "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
SEARCH_URL  = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
GENRE_URL   = "https://openapi.rakuten.co.jp/ichibagt/api/IchibaGenre/Search/20260401"

_TIMEOUT    = 15
_MAX_RETRY  = 2
_RETRY_WAIT = 1.5


def _credentials() -> dict[str, str]:
    app_id     = os.getenv("RAKUTEN_APP_ID", "").strip()
    access_key = os.getenv("RAKUTEN_ACCESS_KEY", "").strip()

    missing = []
    if not app_id or app_id == "your_application_id_here":
        missing.append("RAKUTEN_APP_ID")
    if not access_key or access_key == "your_access_key_here":
        missing.append("RAKUTEN_ACCESS_KEY")

    if missing:
        raise RuntimeError(
            f"{', '.join(missing)} が未設定です。"
            ".env を確認してください。\n"
            "取得先: https://webservice.rakuten.co.jp/app/list"
        )
    return {"applicationId": app_id, "accessKey": access_key}


def _get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    params = {**params, **_credentials(), "format": "json"}
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRY + 1):
        try:
            res = requests.get(url, params=params, timeout=_TIMEOUT)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            last_err = e
            if attempt < _MAX_RETRY:
                time.sleep(_RETRY_WAIT)
    assert last_err is not None
    raise last_err


# ---------- ジャンル ----------

def get_genre_children(genre_id: int) -> list[dict[str, Any]]:
    """指定ジャンルの直下の子ジャンル一覧を返す。末端なら空リスト。"""
    data = _get(GENRE_URL, {"genreId": genre_id})
    return data.get("children", [])


# ---------- ランキング ----------

def get_ranking(genre_id: int | None = None) -> dict[str, Any]:
    """ランキング取得。genre_id を省略すると全体ランキング。"""
    params: dict[str, Any] = {}
    if genre_id is not None:
        params["genreId"] = genre_id
    return _get(RANKING_URL, params)


# ---------- 検索 ----------

def search_items(keyword: str, hits: int = 30) -> dict[str, Any]:
    return _get(SEARCH_URL, {"keyword": keyword, "hits": hits})
