"""문제 목록(puzzles/puzzles.yaml)을 읽어 인스타 게시물 파일을 만든다.

사용법
  python scripts/render.py                      # 모든 문제, 릴스 영상
  python scripts/render.py --id 2               # 2번 문제만
  python scripts/render.py --id 2 --format feed # 피드용 4:5 이미지
결과
  릴스: output/002.mp4 (+ 표지 확인용 002_reel.png)
  피드: output/002.jpg
  공통: output/002.txt (캡션)
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FEED = (1080, 1350)
REEL = (1080, 1920)
REEL_SAFE_BOTTOM = 1580  # 이보다 아래는 릴스 캡션·버튼에 가려진다
FPS = 30
CAPTION_MAX = 2200
HASHTAG_MAX = 5  # 2025년 12월부터 인스타 해시태그는 게시물당 5개까지
REQUIRED = {"lock": ["clues"], "sequence": ["terms"], "rows": ["rows"], "exam": ["question", "exam_label"]}


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
            if len({len(str(c["digits"])) for c in p["clues"]}) != 1:
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
            (local / "nanum-myeongjo" / "700.css").as_uri(),
            (local / "nanum-myeongjo" / "800.css").as_uri(),
        ]
    return ["https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Nanum+Myeongjo:wght@700;800"
            "&family=Noto+Sans+KR:wght@500;700;900&display=block"]


def launch(p):
    try:
        return p.chromium.launch()
    except Exception:
        return p.chromium.launch(channel="chrome")


def open_page(page, html, html_path, size):
    html_path.write_text(html, encoding="utf-8")
    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.goto(html_path.as_uri())
    page.evaluate("document.fonts.ready")


def overflow(page, el_id):
    return page.evaluate(
        f"() => {{ const c = document.getElementById('{el_id}');"
        " return [c.scrollHeight - c.clientHeight, c.scrollWidth - c.clientWidth]; }"
    )


def render_feed(page, env, p, cfg, ctx, out, name):
    html = env.get_template("card.html.j2").render(p=p, cfg=cfg, **ctx)
    open_page(page, html, out / "html" / f"{name}_feed.html", FEED)
    o = overflow(page, "card")
    if o[0] > 0 or o[1] > 0:
        return f"피드 이미지에서 내용이 넘칩니다 (세로 {o[0]}px). 글을 줄여주세요."
    page.locator("#card").screenshot(path=str(out / f"{name}.jpg"), type="jpeg", quality=92)
    return None


def render_reel(page, env, p, cfg, ctx, out, name):
    seconds = int(p.get("seconds") or cfg.get("reel_seconds", 9))
    timer = bool(cfg.get("reel_timer", False))
    show_badge = bool(cfg.get("reel_show_badge", False))
    html = env.get_template("reel.html.j2").render(p=p, seconds=seconds, timer=timer, show_badge=show_badge, **ctx)
    open_page(page, html, out / "html" / f"{name}_reel.html", REEL)
    o = overflow(page, "reel")
    if o[0] > 0 or o[1] > 0:
        return f"릴스 화면에서 내용이 넘칩니다 (세로 {o[0]}px). 글을 줄여주세요."
    bottom = page.evaluate("document.getElementById('safe-end').getBoundingClientRect().bottom")
    if bottom > REEL_SAFE_BOTTOM:
        return f"릴스 아래쪽 {int(bottom - REEL_SAFE_BOTTOM)}px이 캡션·버튼에 가려집니다. 글을 줄여주세요."

    base = out / f"{name}_reel.png"
    page.locator("#reel").screenshot(path=str(base))

    music = ROOT / "assets" / "music" / cfg.get("reel_music", "tick_tock.m4a")
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(base)]
        if timer:
            # 카운트다운 막대: 가득 찬 상태에서 0까지 줄어드는 프레임을 겹친다
            box = page.locator("#timer-track").bounding_box()
            x, y, w, h = (round(box[k]) for k in ("x", "y", "width", "height"))
            frames = seconds * FPS
            for i in range(frames):
                img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                fill = round(w * (1 - i / (frames - 1)))
                if fill > 0:
                    ImageDraw.Draw(img).rounded_rectangle(
                        (0, 0, max(fill, h) - 1, h - 1), radius=h // 2, fill=cfg.get("accent", "#FFC93C"))
                img.save(f"{tmp}/{i:04d}.png")
            cmd += ["-framerate", str(FPS), "-i", f"{tmp}/%04d.png"]
            video, audio_in = f"[0:v][1:v]overlay={x}:{y}:shortest=1,format=yuv420p[v]", 2
        else:
            # 정지 화면 + 배경음
            video, audio_in = "[0:v]format=yuv420p[v]", 1
        if music.exists():
            cmd += ["-stream_loop", "-1", "-i", str(music)]
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd += ["-filter_complex",
                f"{video};[{audio_in}:a]volume=6dB,alimiter=limit=0.95,afade=t=out:st={seconds - 0.8}:d=0.8[a]",
                "-map", "[v]", "-map", "[a]", "-t", str(seconds),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                "-movflags", "+faststart", str(out / f"{name}.mp4")]
        subprocess.run(cmd, check=True)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, help="이 번호의 문제만")
    ap.add_argument("--format", choices=["reel", "feed", "both"], default="reel")
    ap.add_argument("--out", default=str(ROOT / "output"))
    args = ap.parse_args()

    cfg = load_yaml(ROOT / "config.yaml")
    puzzles = load_yaml(ROOT / "puzzles" / "puzzles.yaml")["puzzles"]
    errors = validate(puzzles)
    if errors:
        sys.exit("문제 목록에 오류가 있습니다:\n  " + "\n  ".join(errors))
    if args.id is not None:
        puzzles = [p for p in puzzles if p["id"] == args.id]
        if not puzzles:
            sys.exit(f"{args.id}번 문제가 없습니다.")
    if args.format in ("reel", "both") and not shutil.which("ffmpeg"):
        sys.exit("릴스 영상을 만들려면 ffmpeg가 필요합니다.")

    out = Path(args.out)
    (out / "html").mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True, undefined=StrictUndefined)
    ctx = {"font_links": font_stylesheets(), "accent": cfg.get("accent", "#FFC93C")}

    failed = False
    with sync_playwright() as pw:
        browser = launch(pw)
        page = browser.new_page(device_scale_factor=1)
        for p in puzzles:
            for key in ("num", "subtitle", "hint", "question", "hook", "exam_period", "exam_no", "passage", "equations", "choices", "blank"):
                p.setdefault(key, None)
            name = f"{p['id']:03d}"
            formats = ["reel", "feed"] if args.format == "both" else [args.format]
            if p["type"] == "exam" and "feed" in formats:
                print(f"[문제 {p['id']}] 시험지 형식(exam)은 릴스 전용이라 피드 이미지는 건너뜁니다.")
                formats = [f for f in formats if f != "feed"]
            for fmt in formats:
                err = (render_reel if fmt == "reel" else render_feed)(page, env, p, cfg, ctx, out, name)
                if err:
                    print(f"[문제 {p['id']}] {err}")
                    failed = True
                else:
                    print(f"[문제 {p['id']}] {'릴스 영상' if fmt == 'reel' else '피드 이미지'} 완성")
            (out / f"{name}.txt").write_text(p["caption"].rstrip() + "\n", encoding="utf-8")
        browser.close()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
