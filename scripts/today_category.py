"""오늘(한국 시간) 올릴 문제 카테고리를 알려준다.

  python scripts/today_category.py            # 오늘
  python scripts/today_category.py --date 2026-11-09
  python scripts/today_category.py --week     # 이번 주 월~일
"""
import argparse
import datetime as dt
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DAYS = "월화수목금토일"
KST = dt.timezone(dt.timedelta(hours=9))


def category_for(day: dt.date, sched: dict) -> dict:
    week = day.isocalendar()[1]
    wd = day.weekday()
    base = sched["weekdays"][wd]
    special_wd = week % 7
    is_special = wd == special_wd
    cat = sched["extras"][week % len(sched["extras"])] if is_special else base
    return {
        "date": day.isoformat(),
        "weekday": DAYS[wd],
        "category": cat,
        "base_category": base,
        "special": is_special,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘, 한국 시간)")
    ap.add_argument("--week", action="store_true", help="그 주 월~일 전체")
    a = ap.parse_args()
    sched = yaml.safe_load((ROOT / "schedule.yaml").read_text(encoding="utf-8"))
    day = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(KST).date()
    if a.week:
        monday = day - dt.timedelta(days=day.weekday())
        for i in range(7):
            r = category_for(monday + dt.timedelta(days=i), sched)
            mark = f"  ← 추가 카테고리 (원래 {r['base_category']})" if r["special"] else ""
            print(f"{r['date']} ({r['weekday']}) {r['category']}{mark}")
    else:
        print(json.dumps(category_for(day, sched), ensure_ascii=False))


if __name__ == "__main__":
    main()
