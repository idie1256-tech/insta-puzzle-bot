"""게시 순서 관리: 아직 올리지 않은 문제 중 다음 차례를 고른다.

사용법
  python scripts/post_queue.py next        # 다음 차례 문제 번호
  python scripts/post_queue.py next 5      # 5번을 지정 (이미 올린 문제면 중단)
  python scripts/post_queue.py status      # 전체 현황
"""
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "posted.json"


def load_puzzles():
    with open(ROOT / "puzzles" / "puzzles.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["puzzles"]


def load_posted():
    if not STATE.exists():
        return []
    return json.loads(STATE.read_text(encoding="utf-8")).get("posted", [])


def emit(pid):
    name = f"{pid:03d}"
    print(f"다음 게시: {pid}번 문제")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"id={pid}\nname={name}\n")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    puzzles = load_puzzles()
    posted_ids = {p["id"] for p in load_posted()}
    waiting = [p["id"] for p in puzzles if p["id"] not in posted_ids]

    if cmd == "status":
        print(f"전체 {len(puzzles)}개 · 게시 완료 {len(posted_ids)}개 · 대기 {len(waiting)}개")
        print("대기 중:", ", ".join(map(str, waiting)) or "없음")
        return

    if cmd == "next":
        if len(sys.argv) > 2 and sys.argv[2].strip():
            pid = int(sys.argv[2])
            if pid not in {p["id"] for p in puzzles}:
                sys.exit(f"{pid}번 문제가 puzzles.yaml에 없습니다.")
            if pid in posted_ids:
                sys.exit(f"{pid}번 문제는 이미 게시했습니다. 중복 게시를 막기 위해 중단합니다.")
            emit(pid)
            return
        if not waiting:
            sys.exit("게시할 문제가 남아 있지 않습니다. puzzles/puzzles.yaml에 새 문제를 추가해주세요.")
        if len(waiting) <= 2:
            print(f"::warning::대기 중인 문제가 {len(waiting)}개뿐입니다. 새 문제를 추가해주세요.")
        emit(waiting[0])
        return

    sys.exit(f"알 수 없는 명령: {cmd}")


if __name__ == "__main__":
    main()
