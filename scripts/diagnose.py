"""토큰·앱·인스타 계정 상태 진단 (토큰 값은 출력하지 않음)."""
import json, os, urllib.error, urllib.parse, urllib.request
API = f"https://graph.facebook.com/{os.environ.get('GRAPH_API_VERSION', 'v27.0')}"
TOKEN = os.environ["IG_ACCESS_TOKEN"].strip()
IG = os.environ["IG_USER_ID"].strip()

def get(path, **p):
    q = urllib.parse.urlencode(dict(p, access_token=TOKEN))
    try:
        with urllib.request.urlopen(f"{API}/{path}?{q}", timeout=60) as r:
            return "OK", json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get("error", {})
        except ValueError:
            err = {"message": "응답 해석 불가"}
        keep = {k: err.get(k) for k in ("message", "type", "code", "error_subcode", "error_user_title", "error_user_msg", "is_transient")}
        return f"HTTP {e.code}", keep

print("토큰 앞 4글자:", TOKEN[:4], "/ 길이:", len(TOKEN))
for label, path, params in [
    ("토큰 주인", "me", {"fields": "id,name"}),
    ("허용된 권한", "me/permissions", {}),
    ("인스타 계정", "IG", {"fields": "username,followers_count,media_count"}),
    ("최근 게시물", "IG/media", {"fields": "id,timestamp", "limit": 2}),
    ("게시 한도", "IG/content_publishing_limit", {"fields": "quota_usage,config"}),
]:
    status, body = get(path.replace("IG", IG), **params)
    if label == "인스타 계정" and status == "OK":
        body.pop("id", None)
    if label == "최근 게시물" and status == "OK":
        body = {"개수": len(body.get("data", []))}
    print(f"[{label}] {status}: {json.dumps(body, ensure_ascii=False)}")
