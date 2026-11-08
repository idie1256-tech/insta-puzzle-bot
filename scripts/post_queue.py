"""게시 순서 관리.

사용법
  python scripts/post_queue.py status              # 전체 현황
  python scripts/post_queue.py check 5             # 5번 문제가 있는지 확인 (미리보기·테스트용)
  python scripts/post_queue.py check 5 --publish   # 실제 게시용: 이미 올린 문제면 중단
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
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"id={pid}\nname={pid:03d}\n")


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "status"
    puzzles = load_puzzles()
    posted_ids = {p["id"] for p in load_posted()}
    waiting = [p["id"] for p in puzzles if p["id"] not in posted_ids]

    if cmd == "status":
        print(f"전체 {len(puzzles)}개 · 게시 완료 {len(posted_ids)}개 · 대기 {len(waiting)}개")
        print("대기 중:", ", ".join(map(str, waiting)) or "없음")
        return

    if cmd == "check":
        if len(args) < 2 or not args[1].strip():
            sys.exit("문제 번호를 입력해주세요.")
        pid = int(args[1])
        if pid not in {p["id"] for p in puzzles}:
            sys.exit(f"{pid}번 문제가 puzzles.yaml에 없습니다.")
        if "--publish" in args and pid in posted_ids:
            sys.exit(f"{pid}번 문제는 이미 게시했습니다. 중복 게시를 막기 위해 중단합니다.")
        print(f"{pid}번 문제 확인")
        emit(pid)
        return

    sys.exit(f"알 수 없는 명령: {cmd}")


if __name__ == "__main__":
    main()
