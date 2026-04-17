"""楽天ウェブサービス API の薄いラッパ。

この PoC で使う 2 つのエンドポイントだけを公開する:
- get_ranking(genre_id)  … IchibaItem/Ranking
- search_items(keyword)  … IchibaItem/Search

将来、別 EC サイトに差し替えるときはこのファイルと同じ I/F のモジュールを追加する。
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

RANKING_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20220601"
SEARCH_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"

_TIMEOUT = 15
_MAX_RETRY = 2
_RETRY_WAIT = 1.5


def _app_id() -> str:
    app_id = os.getenv("RAKUTEN_APP_ID", "").strip()
    if not app_id or app_id == "your_application_id_here":
        raise RuntimeError(
            "RAKUTEN_APP_ID が未設定です。.env を作成して App ID を入れてください。"
        )
    return app_id


def _get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    params = {**params, "applicationId": _app_id(), "format": "json"}
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


def get_ranking(genre_id: int) -> dict[str, Any]:
    return _get(RANKING_URL, {"genreId": genre_id})


def search_items(keyword: str, hits: int = 30) -> dict[str, Any]:
    return _get(SEARCH_URL, {"keyword": keyword, "hits": hits})
