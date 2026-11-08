"""인스타그램에 문제 하나를 게시한다 (Instagram API with Unified login, 시스템 사용자 토큰).

필요한 환경 변수 (GitHub Secrets에 저장)
  IG_ACCESS_TOKEN  Meta에서 받은 액세스 토큰 (EAA...로 시작)
  IG_USER_ID       인스타 계정 ID (비즈니스 설정 > Instagram 계정에 보이는 숫자)

사용법
  python scripts/publish.py --check                                  # 토큰과 계정 연결만 확인
  python scripts/publish.py --id 2 --video output/002.mp4            # 2번 문제를 릴스로 게시
  python scripts/publish.py --id 2 --video output/002.mp4 --no-publish  # 업로드·처리까지만 (게시 안 함)
  python scripts/publish.py --id 1 --image-url https://...           # 피드 이미지로 게시
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
VERSION = os.environ.get("GRAPH_API_VERSION", "v27.0")
API = os.environ.get("GRAPH_API_BASE") or f"https://graph.facebook.com/{VERSION}"
RUPLOAD = os.environ.get("RUPLOAD_BASE") or f"https://rupload.facebook.com/ig-api-upload/{VERSION}"


def env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"환경 변수 {name}가 비어 있습니다. GitHub 저장소의 Settings > Secrets에 등록했는지 확인해주세요.")
    return value


def send(req, label):
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            err = json.loads(body).get("error", {})
            msg = f"{err.get('message')} (code {err.get('code')}, subcode {err.get('error_subcode')})"
        except (ValueError, AttributeError):
            msg = body[:500]
        sys.exit(f"인스타 API 오류 [{label}]: {msg}")


def call(method, path, params):
    params = dict(params, access_token=env("IG_ACCESS_TOKEN"))
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{API}/{path}?{data.decode()}")
    else:
        req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    return send(req, f"{method} {path}")


def wait_until_ready(container, tries=60, delay=5):
    """인스타가 업로드된 파일 처리를 끝낼 때까지 기다린다 (최대 약 5분)."""
    for _ in range(tries):
        res = call("GET", container, {"fields": "status_code,status"})
        code = res.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            sys.exit(f"인스타가 파일을 처리하지 못했습니다 (상태: {code}, {res.get('status')}).")
        time.sleep(delay)
    sys.exit("처리 대기 시간이 초과됐습니다.")


def wait_for_url(url, tries=10):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                if r.status == 200:
                    return
        except urllib.error.URLError:
            pass
        time.sleep(3)
    sys.exit(f"이미지 주소가 열리지 않습니다: {url}")


def create_reel(ig_id, caption, video):
    size = video.stat().st_size
    res = call("POST", f"{ig_id}/media", {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "share_to_feed": "true",
        "audio_name": "째깍째깍 생각할 시간",
    })
    container = res["id"]
    uri = res.get("uri") or f"{RUPLOAD}/{container}"
    print(f"릴스 컨테이너 생성: {container} → 영상 업로드 중 ({size // 1024}KB)")
    req = urllib.request.Request(uri, data=video.read_bytes(), method="POST", headers={
        "Authorization": f"OAuth {env('IG_ACCESS_TOKEN')}",
        "offset": "0",
        "file_size": str(size),
    })
    up = send(req, "영상 업로드")
    if not up.get("success", True):
        sys.exit(f"영상 업로드 실패: {up}")
    return container


def create_image(ig_id, caption, image_url):
    wait_for_url(image_url)
    return call("POST", f"{ig_id}/media", {"image_url": image_url, "caption": caption})["id"]


def record(pid, fmt, media_id, permalink):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"posted": []}
    state["posted"].append({
        "id": pid,
        "format": fmt,
        "media_id": media_id,
        "permalink": permalink,
        "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="토큰과 계정 연결만 확인")
    ap.add_argument("--id", type=int)
    ap.add_argument("--video", help="릴스로 올릴 MP4 파일")
    ap.add_argument("--image-url", help="피드로 올릴 공개 이미지 주소")
    ap.add_argument("--no-publish", action="store_true", help="업로드와 처리까지만 하고 게시하지 않음")
    args = ap.parse_args()

    ig_id = env("IG_USER_ID")
    me = call("GET", ig_id, {"fields": "username"})
    print(f"연결된 계정: @{me.get('username')}")
    limit = call("GET", f"{ig_id}/content_publishing_limit", {"fields": "quota_usage"})
    print(f"최근 24시간 API 게시 수: {(limit.get('data') or [{}])[0].get('quota_usage')}")
    if args.check:
        return

    if args.id is None or not (args.video or args.image_url):
        sys.exit("--id와 함께 --video 또는 --image-url이 필요합니다.")
    with open(ROOT / "puzzles" / "puzzles.yaml", encoding="utf-8") as f:
        puzzle = next((p for p in yaml.safe_load(f)["puzzles"] if p["id"] == args.id), None)
    if not puzzle:
        sys.exit(f"{args.id}번 문제가 없습니다.")
    caption = puzzle["caption"].rstrip()

    if args.video:
        fmt, container = "reel", create_reel(ig_id, caption, Path(args.video))
    else:
        fmt, container = "feed", create_image(ig_id, caption, args.image_url)

    wait_until_ready(container)
    if args.no_publish:
        print(f"업로드 테스트 성공: 인스타가 {'영상' if fmt == 'reel' else '이미지'} 처리를 마쳤습니다. "
              "게시는 하지 않았습니다 (이 컨테이너는 24시간 뒤 자동으로 사라집니다).")
        return

    media_id = call("POST", f"{ig_id}/media_publish", {"creation_id": container})["id"]
    permalink = call("GET", media_id, {"fields": "permalink"}).get("permalink", "")
    record(args.id, fmt, media_id, permalink)
    print(f"게시 완료! {permalink}")


if __name__ == "__main__":
    main()
