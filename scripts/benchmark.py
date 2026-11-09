"""다른 퀴즈 계정의 릴스 성과와 내 릴스 성과를 모은다 (Instagram API, Business Discovery + Insights).

다른 계정: 비즈니스/크리에이터 계정만 가능. 공개 숫자(조회수·좋아요·댓글)와 캡션·썸네일만 받을 수 있다.
         공유·저장·시청 시간은 남의 계정에서는 받을 수 없다.
내 계정 : 조회수·도달·좋아요·댓글·공유·저장·평균 시청 시간·스킵률 등 인사이트.

사용법 (GitHub Actions에서 실행 — IG_ACCESS_TOKEN, IG_USER_ID 필요)
  python scripts/benchmark.py --check bluebottle    # 다른 계정 조회 권한 확인
  python scripts/benchmark.py --competitors         # benchmarks.yaml 계정들 수집
  python scripts/benchmark.py --own                 # 내 릴스 인사이트 수집
결과: output/bench/competitors.json, own.json, report.md, thumbs/*.jpg
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "bench"
VERSION = os.environ.get("GRAPH_API_VERSION", "v27.0")
API = os.environ.get("GRAPH_API_BASE") or f"https://graph.facebook.com/{VERSION}"
MEDIA_FIELDS = "id,caption,media_type,media_product_type,like_count,comments_count,view_count,timestamp,permalink,thumbnail_url"
OWN_METRICS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
               "ig_reels_avg_watch_time", "ig_reels_video_view_total_time", "reels_skip_rate"]


class ApiError(Exception):
    pass


def get(path, params):
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("IG_ACCESS_TOKEN 이 비어 있습니다.")
    q = urllib.parse.urlencode(dict(params, access_token=token))
    try:
        with urllib.request.urlopen(f"{API}/{path}?{q}", timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            err = json.loads(body).get("error", {})
            raise ApiError(f"{err.get('message')} (code {err.get('code')}, subcode {err.get('error_subcode')})")
        except ValueError:
            raise ApiError(body[:300])


def me():
    uid = os.environ.get("IG_USER_ID", "").strip()
    if not uid:
        sys.exit("IG_USER_ID 가 비어 있습니다.")
    return uid


def discover(username, limit=30):
    fields = (f"business_discovery.username({username})"
              f"{{username,followers_count,media_count,media.limit({limit}){{{MEDIA_FIELDS}}}}}")
    data = get(me(), {"fields": fields})["business_discovery"]
    return data


def days_old(ts):
    t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
    return (datetime.now(timezone.utc) - t).total_seconds() / 86400


def score_posts(account):
    followers = account.get("followers_count") or 0
    rows = []
    for m in (account.get("media") or {}).get("data", []):
        is_reel = m.get("media_product_type") == "REELS" or m.get("media_type") == "VIDEO"
        views = m.get("view_count")
        if not is_reel or not views:
            continue
        age = days_old(m["timestamp"])
        if age < 2 or age > 90:  # 너무 최신(아직 성장 중)·너무 오래된 것은 제외
            continue
        likes, comments = m.get("like_count"), m.get("comments_count") or 0
        rows.append({
            "username": account.get("username"),
            "followers": followers,
            "id": m["id"],
            "date": m["timestamp"][:10],
            "views": views,
            "likes": likes,
            "comments": comments,
            "views_per_follower": round(views / followers, 2) if followers else None,
            "like_rate": round(likes / views, 4) if likes is not None else None,
            "comment_rate": round(comments / views, 4),
            "caption": (m.get("caption") or "").strip(),
            "permalink": m.get("permalink"),
            "thumbnail_url": m.get("thumbnail_url"),
        })
    # 계정 평균 대비 몇 배인지 (계정 크기 차이를 줄이기 위해)
    if rows:
        avg = sum(r["views"] for r in rows) / len(rows)
        for r in rows:
            r["vs_account_avg"] = round(r["views"] / avg, 2)
    return rows


def download(url, path):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            path.write_bytes(r.read())
        return True
    except Exception:
        return False


def ocr(path):
    try:
        import pytesseract
        from PIL import Image
        txt = pytesseract.image_to_string(Image.open(path), lang="kor+eng")
        return " ".join(txt.split())[:80]
    except Exception:
        return None


def competitors(cfg):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "thumbs").mkdir(exist_ok=True)
    rows, errors = [], {}
    for u in cfg.get("accounts") or []:
        u = u.lstrip("@").strip()
        try:
            rows += score_posts(discover(u))
            print(f"  ✓ {u}")
        except (ApiError, KeyError) as e:
            errors[u] = str(e)
            print(f"  ✗ {u}: {e}")
    rows.sort(key=lambda r: (r.get("vs_account_avg") or 0), reverse=True)
    top = rows[: cfg.get("top_n", 15)]
    for r in top:
        if r.get("thumbnail_url"):
            f = OUT / "thumbs" / f"{r['id']}.jpg"
            r["thumb_file"] = f"thumbs/{r['id']}.jpg" if download(r["thumbnail_url"], f) else None
            if r["thumb_file"]:
                r["screen_text"] = ocr(f)
    (OUT / "competitors.json").write_text(json.dumps({"collected_at": datetime.now(timezone.utc).isoformat(),
                                                      "top": top, "all": rows, "errors": errors},
                                                     ensure_ascii=False, indent=2))
    return top, errors


def own(limit=30):
    OUT.mkdir(parents=True, exist_ok=True)
    media = get(f"{me()}/media", {"fields": "id,caption,media_product_type,timestamp,permalink", "limit": limit}).get("data", [])
    posted = {}
    sp = ROOT / "state" / "posted.json"
    if sp.exists():
        d = json.loads(sp.read_text())
        for x in (d.get("posted", []) if isinstance(d, dict) else d):
            posted[str(x.get("media_id"))] = x.get("id")
    out = []
    for m in media:
        row = {"media_id": m["id"], "puzzle_id": posted.get(m["id"]), "date": m["timestamp"][:10],
               "permalink": m.get("permalink"), "caption_first_line": (m.get("caption") or "").split("\n")[0]}
        for metric in OWN_METRICS:  # 지표마다 따로 요청 (하나가 없어도 나머지는 받도록)
            try:
                d = get(f"{m['id']}/insights", {"metric": metric}).get("data", [])
                row[metric] = d[0]["values"][0]["value"] if d else None
            except ApiError as e:
                row[metric] = None
                row.setdefault("_errors", {})[metric] = str(e)[:120]
        if row.get("views") and row.get("shares") is not None:
            row["share_rate"] = round(row["shares"] / row["views"], 4)
        out.append(row)
    (OUT / "own.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def report(top, errors, own_rows):
    lines = [f"# 퀴즈 릴스 벤치마크 ({datetime.now(timezone.utc).date()})", ""]
    if own_rows is not None:
        lines += ["## 내 릴스", "", "| 날짜 | 문제 | 조회 | 도달 | 좋아요 | 댓글 | 공유 | 저장 | 평균시청(ms) | 스킵률 | 팔로우 |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in own_rows:
            lines.append(f"| {r['date']} | {r.get('puzzle_id') or ''} {r['caption_first_line'][:20]} | {r.get('views')} | {r.get('reach')} | "
                         f"{r.get('likes')} | {r.get('comments')} | {r.get('shares')} | {r.get('saved')} | "
                         f"{r.get('ig_reels_avg_watch_time')} | {r.get('reels_skip_rate')} | {r.get('follows')} |")
        errs = {k: v for r in own_rows for k, v in (r.get("_errors") or {}).items()}
        if errs:
            lines += ["", "인사이트 오류:"] + [f"- {k}: {v}" for k, v in errs.items()]
        lines.append("")
    if top is not None:
        lines += ["## 다른 계정 상위 릴스 (계정 평균 대비 조회수 배수 순)", "",
                  "| 계정 | 날짜 | 조회 | 평균 대비 | 팔로워 대비 | 좋아요율 | 댓글율 | 캡션 첫 줄 | 화면 글자(OCR) | 링크 |", "|---|---|---|---|---|---|---|---|---|---|"]
        for r in top:
            cap = r["caption"].split("\n")[0][:30].replace("|", "/")
            lines.append(f"| {r['username']} | {r['date']} | {r['views']} | x{r.get('vs_account_avg')} | {r.get('views_per_follower')} | "
                         f"{r.get('like_rate')} | {r.get('comment_rate')} | {cap} | {(r.get('screen_text') or '').replace('|', '/')} | {r['permalink']} |")
        if errors:
            lines += ["", "## 조회 실패 계정", ""] + [f"- {u}: {e}" for u, e in errors.items()]
    (OUT / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", metavar="USERNAME", help="이 계정 하나로 조회 권한만 확인")
    ap.add_argument("--competitors", action="store_true")
    ap.add_argument("--own", action="store_true")
    ap.add_argument("--probe", metavar="U1,U2,...", help="여러 아이디가 조회 가능한지 한 번에 확인")
    a = ap.parse_args()
    if a.check:
        try:
            d = discover(a.check.lstrip("@"), limit=3)
            print(f"✓ 다른 계정 조회 가능: @{d.get('username')} 팔로워 {d.get('followers_count')}, 게시물 {d.get('media_count')}")
            for m in (d.get("media") or {}).get("data", []):
                print(f"  - {m.get('timestamp','')[:10]} {m.get('media_product_type')} 조회 {m.get('view_count')} 좋아요 {m.get('like_count')} 댓글 {m.get('comments_count')}")
        except ApiError as e:
            sys.exit(f"✗ 다른 계정 조회 실패: {e}")
        return
    if a.probe:
        found = []
        for u in [x.strip().lstrip("@") for x in a.probe.split(",") if x.strip()]:
            try:
                d = get(me(), {"fields": f"business_discovery.username({u}){{username,followers_count,media_count}}"})["business_discovery"]
                found.append((d.get("followers_count") or 0, d.get("username"), d.get("media_count")))
            except (ApiError, KeyError):
                pass
        print(f"조회 가능 {len(found)}개")
        for f, u, m in sorted(found, reverse=True):
            print(f"FOUND {u} 팔로워 {f} 게시물 {m}")
        return
    cfg = yaml.safe_load((ROOT / "benchmarks.yaml").read_text(encoding="utf-8")) or {}
    top = errors = own_rows = None
    if a.competitors:
        top, errors = competitors(cfg)
    if a.own:
        own_rows = own()
    report(top, errors or {}, own_rows)


if __name__ == "__main__":
    main()
