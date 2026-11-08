"""문제 목록(puzzles/puzzles.yaml)을 읽어 인스타 피드용 1080x1350 JPEG 이미지와 캡션 파일을 만든다.

사용법
  python scripts/render.py            # 모든 문제 렌더링
  python scripts/render.py --id 2     # 2번 문제만
결과
  output/001.jpg, output/001.txt (캡션) ...
"""
import argparse
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT = 1080, 1350
CAPTION_MAX = 2200      # 인스타 캡션 최대 글자 수
HASHTAG_MAX = 30        # 인스타 해시태그 최대 개수
REQUIRED = {
    "lock": ["clues"],
    "sequence": ["terms"],
    "rows": ["rows"],
}


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate(puzzles):
    errors = []
    seen = set()
    for p in puzzles:
        pid = p.get("id")
        tag = f"[문제 {pid}]"
        if pid in seen:
            errors.append(f"{tag} id가 중복됩니다.")
        seen.add(pid)
        for key in ["id", "type", "difficulty", "title", "caption"]:
            if not p.get(key):
                errors.append(f"{tag} '{key}' 항목이 비어 있습니다.")
        ptype = p.get("type")
        if ptype not in REQUIRED:
            errors.append(f"{tag} type은 {', '.join(REQUIRED)} 중 하나여야 합니다.")
            continue
        for key in REQUIRED[ptype]:
            if not p.get(key):
                errors.append(f"{tag} type이 {ptype}이면 '{key}' 항목이 필요합니다.")
        if ptype == "lock" and p.get("clues"):
            lengths = {len(str(c["digits"])) for c in p["clues"]}
            if len(lengths) != 1:
                errors.append(f"{tag} 단서마다 숫자 자릿수가 다릅니다.")
        caption = p.get("caption") or ""
        if len(caption) > CAPTION_MAX:
            errors.append(f"{tag} 캡션이 {len(caption)}자입니다 (최대 {CAPTION_MAX}자).")
        tags = re.findall(r"#\S+", caption)
        if len(tags) > HASHTAG_MAX:
            errors.append(f"{tag} 해시태그가 {len(tags)}개입니다 (최대 {HASHTAG_MAX}개).")
    return errors


def font_stylesheets():
    """assets/fonts 폴더가 있으면 내장 글꼴을, 없으면 Google Fonts를 쓴다."""
    local = ROOT / "assets" / "fonts"
    if local.exists():
        return [
            (local / "noto-sans-kr" / "500.css").as_uri(),
            (local / "noto-sans-kr" / "700.css").as_uri(),
            (local / "noto-sans-kr" / "900.css").as_uri(),
            (local / "black-han-sans" / "400.css").as_uri(),
        ]
    return ["https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@500;700;900&display=block"]


def launch(p):
    # GitHub Actions 등에서는 `playwright install chromium`으로 받은 브라우저를,
    # 없으면 설치된 Chrome을 사용한다.
    try:
        return p.chromium.launch()
    except Exception:
        return p.chromium.launch(channel="chrome")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, help="이 번호의 문제만 렌더링")
    ap.add_argument("--out", default=str(ROOT / "output"))
    args = ap.parse_args()

    cfg = load_yaml(ROOT / "config.yaml")
    puzzles = load_yaml(ROOT / "puzzles" / "puzzles.yaml")["puzzles"]

    errors = validate(puzzles)
    if errors:
        print("문제 목록에 오류가 있습니다:\n  " + "\n  ".join(errors))
        sys.exit(1)

    if args.id is not None:
        puzzles = [p for p in puzzles if p["id"] == args.id]
        if not puzzles:
            print(f"{args.id}번 문제가 없습니다.")
            sys.exit(1)

    out = Path(args.out)
    (out / "html").mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True, undefined=StrictUndefined)
    template = env.get_template("card.html.j2")
    font_links = font_stylesheets()

    failed = False
    with sync_playwright() as pw:
        browser = launch(pw)
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
        for p in puzzles:
            p.setdefault("subtitle", None)
            p.setdefault("hint", None)
            p.setdefault("question", None)
            name = f"{p['id']:03d}"
            html_path = out / "html" / f"{name}.html"
            html_path.write_text(template.render(p=p, cfg=cfg, font_links=font_links), encoding="utf-8")

            page.goto(html_path.as_uri())
            page.evaluate("document.fonts.ready")
            overflow = page.evaluate(
                "() => { const c = document.getElementById('card');"
                " return [c.scrollHeight - c.clientHeight, c.scrollWidth - c.clientWidth]; }"
            )
            if overflow[0] > 0 or overflow[1] > 0:
                print(f"[문제 {p['id']}] 내용이 이미지 밖으로 넘칩니다 (세로 {overflow[0]}px, 가로 {overflow[1]}px). 글을 줄여주세요.")
                failed = True
                continue

            page.locator("#card").screenshot(path=str(out / f"{name}.jpg"), type="jpeg", quality=92)
            (out / f"{name}.txt").write_text(p["caption"].rstrip() + "\n", encoding="utf-8")
            print(f"[문제 {p['id']}] {out / (name + '.jpg')} 완성")
        browser.close()

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
