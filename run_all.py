"""fetch_ranking → search_items → make_report を順に実行するワンコマンド起動スクリプト。

Skill や Claude Code からはこれ1本を呼べばよい。

実行方法:
    uv run python run_all.py        # uv がある場合(推奨)
    .venv/bin/python run_all.py     # venv をセットアップ済みの場合
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


def run(script: str) -> None:
    print(f"\n{'='*50}")
    print(f"▶ {script}")
    print("=" * 50)
    result = subprocess.run(
        [PYTHON, ROOT / "scripts" / script],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(f"\n[エラー] {script} が失敗しました(終了コード {result.returncode})。")
        sys.exit(result.returncode)


def main() -> None:
    run("fetch_ranking.py")
    run("search_items.py")
    run("search_brand.py")
    run("make_report.py")

    reports = sorted((ROOT / "reports").glob("report_*.md"))
    if reports:
        latest = reports[-1]
        print(f"\n最新レポート: {latest.relative_to(ROOT)}")
        print(latest.read_text(encoding="utf-8"))
    else:
        print("\nレポートが生成されませんでした。")


if __name__ == "__main__":
    main()
