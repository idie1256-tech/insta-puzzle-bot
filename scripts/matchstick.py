"""성냥개비 문제 도구.

- solve: 성냥개비 1개를 옮겨 맞는 식이 되는 모든 답을 찾는다.
- svg:   식을 성냥개비 그림(SVG)으로 그린다.

사용 예)
  python scripts/matchstick.py solve "5+7=2"
  python scripts/matchstick.py svg "5+7=2" assets/figures/match_5p7e2.svg
  python scripts/matchstick.py search      # 답이 하나뿐인 문제 후보 찾기

규칙: '='는 바꿀 수 없음. '+'의 세로 막대는 옮길 수 있음('+' → '-').
'-'에 세로 막대를 더하면 '+'가 됨.
"""
import sys
from itertools import product

# 7세그먼트: a 위, b 오른쪽 위, c 오른쪽 아래, d 아래, e 왼쪽 아래, f 왼쪽 위, g 가운데
DIGITS = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
    "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg",
}
SEG2DIGIT = {frozenset(v): k for k, v in DIGITS.items()}
SEGS = "abcdefg"


def parse(expr):
    """'5+7=2' → 칸 목록. 숫자 칸은 ('d', set), 연산자 칸은 ('op', set) where op set ⊆ {'h','v'}"""
    cells = []
    for ch in expr.replace(" ", ""):
        if ch.isdigit():
            cells.append(("d", set(DIGITS[ch])))
        elif ch == "+":
            cells.append(("op", {"h", "v"}))
        elif ch == "-":
            cells.append(("op", {"h"}))
        elif ch == "=":
            cells.append(("eq", None))
        else:
            raise ValueError(ch)
    return cells


def render_text(cells):
    out = []
    for kind, s in cells:
        if kind == "d":
            d = SEG2DIGIT.get(frozenset(s))
            if d is None:
                return None
            out.append(d)
        elif kind == "op":
            if s == {"h", "v"}:
                out.append("+")
            elif s == {"h"}:
                out.append("-")
            else:
                return None
        else:
            out.append("=")
    return "".join(out)


def is_true(text):
    if text is None or text.count("=") != 1:
        return False
    left, right = text.split("=")
    for side in (left, right):
        if not side or side[0] in "+-" or side[-1] in "+-":
            return False
        # 앞자리 0 금지 (예: 05)
        import re
        for num in re.findall(r"\d+", side):
            if len(num) > 1 and num[0] == "0":
                return False
    try:
        return eval(left) == eval(right)
    except Exception:
        return False


def slots(cells):
    """(칸 번호, 세그먼트) 전체 자리"""
    for i, (kind, s) in enumerate(cells):
        if kind == "d":
            for seg in SEGS:
                yield i, seg
        elif kind == "op":
            for seg in "hv":
                yield i, seg


def solve(expr):
    cells = parse(expr)
    filled = [(i, s) for i, s in slots(cells) if s in cells[i][1]]
    empty = [(i, s) for i, s in slots(cells) if s not in cells[i][1]]
    sols = set()
    for (i, s), (j, t) in product(filled, empty):
        # 가로/세로 방향이 다른 자리로 옮기는 것도 허용(성냥개비는 돌릴 수 있음)
        new = [(k, set(v) if v is not None else None) for k, v in cells]
        new[i][1].discard(s)
        new[j][1].add(t)
        txt = render_text(new)
        if is_true(txt):
            sols.add(txt)
    return sorted(sols)


def search():
    """한 자리 수 a ? b = c (c는 1~2자리) 중 틀린 식 + 답이 딱 하나인 것"""
    res = []
    for a, op, b in product("0123456789", "+-", "0123456789"):
        for c in [str(x) for x in range(0, 20)]:
            expr = f"{a}{op}{b}={c}"
            if is_true(expr):
                continue
            sols = solve(expr)
            if len(sols) == 1:
                res.append((expr, sols[0]))
    return res


# ---------------- SVG ----------------
W_DIGIT = 132      # 숫자 칸 너비
H_DIGIT = 236      # 숫자 칸 높이
W_OP = 104
GAP = 30
L = 84             # 연산자 성냥 길이
T = 12             # 성냥 굵기
HEAD = 9           # 머리 반지름
J = 13             # 이음매 간격(성냥끼리 겹치지 않게)

WOOD = "#F3D7A4"
WOOD_EDGE = "#C9A36A"
HEAD_C = "#D7402B"
HEAD_HI = "#F07A5F"


def stick(x1, y1, x2, y2):
    """(x1,y1)이 머리 쪽. 막대 + 머리"""
    import math
    ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
    length = math.hypot(x2 - x1, y2 - y1)
    return (
        f'<g transform="translate({x1:.1f},{y1:.1f}) rotate({ang:.1f})">'
        f'<rect x="0" y="{-T/2}" width="{length:.1f}" height="{T}" rx="3" fill="{WOOD}" stroke="{WOOD_EDGE}" stroke-width="2"/>'
        f'<ellipse cx="5" cy="0" rx="{HEAD+4}" ry="{HEAD}" fill="{HEAD_C}"/>'
        f'<ellipse cx="2" cy="-3" rx="4" ry="2.5" fill="{HEAD_HI}"/>'
        f'</g>'
    )


def digit_sticks(x, y, segs):
    """x,y: 숫자 칸 왼쪽 위. 머리는 위쪽/왼쪽"""
    pad = 10
    left, right = x + pad, x + W_DIGIT - pad
    top, mid, bot = y + pad, y + H_DIGIT / 2, y + H_DIGIT - pad
    hx1, hx2 = left + J, right - J
    pos = {
        "a": (hx1, top, hx2, top),
        "g": (hx1, mid, hx2, mid),
        "d": (hx1, bot, hx2, bot),
        "f": (left, top + J, left, mid - J),
        "b": (right, top + J, right, mid - J),
        "e": (left, mid + J, left, bot - J),
        "c": (right, mid + J, right, bot - J),
    }
    return "".join(stick(*pos[s]) for s in SEGS if s in segs)


def op_sticks(x, y, segs, kind):
    cx, cy = x + W_OP / 2, y + H_DIGIT / 2
    half = L / 2
    out = []
    if kind == "eq":
        out.append(stick(cx - half, cy - 22, cx + half, cy - 22))
        out.append(stick(cx - half, cy + 22, cx + half, cy + 22))
    else:
        if "h" in segs:
            out.append(stick(cx - half, cy, cx + half, cy))
        if "v" in segs:
            out.append(stick(cx, cy - half, cx, cy + half))
    return "".join(out)


def svg(expr, path, bg="#22303F"):
    cells = parse(expr)
    margin_x, margin_y = 56, 54
    widths = [W_DIGIT if k == "d" else W_OP for k, _ in cells]
    width = sum(widths) + GAP * (len(cells) - 1) + margin_x * 2
    height = H_DIGIT + margin_y * 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
             f'<rect width="{width}" height="{height}" fill="{bg}"/>']
    x = margin_x
    for (kind, s), w in zip(cells, widths):
        if kind == "d":
            parts.append(digit_sticks(x, margin_y, s))
        else:
            parts.append(op_sticks(x, margin_y, s or set(), kind))
        x += w + GAP
    parts.append("</svg>")
    with open(path, "w") as f:
        f.write("".join(parts))
    return width, height


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "solve":
        print(solve(sys.argv[2]))
    elif cmd == "svg":
        print(svg(sys.argv[2], sys.argv[3]))
    elif cmd == "search":
        for e, s in search():
            print(e, "→", s)
