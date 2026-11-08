"""인스타그램에 문제 하나를 게시한다 (Instagram API with Unified login, 시스템 사용자 토큰).

필요한 환경 변수 (GitHub Secrets에 저장)
  IG_ACCESS_TOKEN  Meta에서 받은 액세스 토큰 (EAA...로 시작)
  IG_USER_ID       인스타 계정 ID (비즈니스 설정 > Instagram 계정에 보이는 숫자)

사용법
  python scripts/publish.py --check                         # 토큰과 계정 연결만 확인
  python scripts/publish.py --id 1 --image-url https://...  # 1번 문제 게시
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "posted.json"
API = os.environ.get("GRAPH_API_BASE") or f"https://graph.facebook.com/{os.environ.get('GRAPH_API_VERSION', 'v27.0')}"


def env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"환경 변수 {name}가 비어 있습니다. GitHub 저장소의 Settings > Secrets에 등록했는지 확인해주세요.")
    return value


def call(method, path, params):
    params = dict(params, access_token=env("IG_ACCESS_TOKEN"))
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{API}/{path}?{data.decode()}")
    else:
        req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            err = json.loads(body).get("error", {})
            msg = f"{err.get('message')} (code {err.get('code')}, subcode {err.get('error_subcode')})"
        except ValueError:
            msg = body[:500]
        sys.exit(f"인스타 API 오류 [{method} {path}]: {msg}")


def wait_for_image(url, tries=10):
    """방금 올린 이미지가 공개 주소에서 열리는지 확인한다."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200:
                    return
        except urllib.error.URLError:
            pass
        time.sleep(3)
    sys.exit(f"이미지 주소가 열리지 않습니다: {url}")


def record(pid, media_id, permalink):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"posted": []}
    state["posted"].append({
        "id": pid,
        "media_id": media_id,
        "permalink": permalink,
        "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="토큰과 계정 연결만 확인")
    ap.add_argument("--id", type=int)
    ap.add_argument("--image-url")
    args = ap.parse_args()

    ig_id = env("IG_USER_ID")
    me = call("GET", ig_id, {"fields": "username"})
    print(f"연결된 계정: @{me.get('username')}")
    limit = call("GET", f"{ig_id}/content_publishing_limit", {"fields": "quota_usage"})
    usage = (limit.get("data") or [{}])[0].get("quota_usage")
    print(f"최근 24시간 API 게시 수: {usage}")
    if args.check:
        return

    if args.id is None or not args.image_url:
        sys.exit("--id와 --image-url이 필요합니다.")
    with open(ROOT / "puzzles" / "puzzles.yaml", encoding="utf-8") as f:
        puzzle = next((p for p in yaml.safe_load(f)["puzzles"] if p["id"] == args.id), None)
    if not puzzle:
        sys.exit(f"{args.id}번 문제가 없습니다.")

    wait_for_image(args.image_url)

    # 1) 미디어 컨테이너 만들기
    container = call("POST", f"{ig_id}/media", {
        "image_url": args.image_url,
        "caption": puzzle["caption"].rstrip(),
    })["id"]
    print(f"컨테이너 생성: {container}")

    # 2) 처리가 끝날 때까지 기다리기
    for _ in range(20):
        status = call("GET", container, {"fields": "status_code"}).get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            sys.exit(f"인스타가 이미지를 처리하지 못했습니다 (상태: {status}).")
        time.sleep(3)
    else:
        sys.exit("이미지 처리 대기 시간이 초과됐습니다.")

    # 3) 게시
    media_id = call("POST", f"{ig_id}/media_publish", {"creation_id": container})["id"]
    permalink = call("GET", media_id, {"fields": "permalink"}).get("permalink", "")
    record(args.id, media_id, permalink)
    print(f"게시 완료! {permalink}")


if __name__ == "__main__":
    main()
