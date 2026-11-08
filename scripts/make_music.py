"""저작권 걱정 없는 릴스용 배경음을 직접 합성한다 (한 번만 실행, 결과는 assets/music/에 저장).

째깍째깍 시계 소리 + 잔잔한 코드 진행 + 낮은 베이스로 '생각하는 시간' 느낌을 낸다.
사용법: python scripts/make_music.py   (numpy, ffmpeg 필요)
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SR = 44100
BPM = 120
LENGTH = 32.0  # 초. 릴스 길이보다 길게 만들어 두고 영상 길이에 맞춰 자른다.
rng = np.random.default_rng(7)


def env(n, attack, release_rate):
    t = np.arange(n) / SR
    a = np.minimum(1.0, t / max(attack, 1e-4))
    return a * np.exp(-t * release_rate)


def tick(freq, length=0.09, gain=0.5):
    n = int(SR * length)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2.7 * t)
    click = rng.normal(0, 1, n) * np.exp(-t * 400) * 0.3
    return (body * env(n, 0.001, 55) + click) * gain


def pad_chord(freqs, length, gain=0.07):
    n = int(SR * length)
    t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2 * t) for f in freqs)
    fade = np.minimum(1, t / 0.25) * np.minimum(1, (length - t) / 0.35)
    return s * fade * gain / len(freqs)


def bass(freq, length, gain=0.18):
    n = int(SR * length)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * freq * 2 * t)
    return s * env(n, 0.005, 3.5) * gain


def note(name):
    names = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
    octave = int(name[-1])
    return 440.0 * 2 ** ((names[name[0]] + 12 * (octave - 4)) / 12)


def main():
    total = int(SR * LENGTH)
    mix = np.zeros(total)
    beat = 60 / BPM

    def add(sig, start):
        i = int(start * SR)
        j = min(total, i + len(sig))
        mix[i:j] += sig[: j - i]

    # 째깍째깍: 박마다 높고 낮은 소리를 번갈아
    for k in range(int(LENGTH / beat)):
        add(tick(1500 if k % 2 == 0 else 1050, gain=0.42 if k % 2 == 0 else 0.34), k * beat)

    # 잔잔한 코드 진행 (Am - F - C - G), 코드마다 4박
    chords = [
        (["A3", "C4", "E4"], "A2"),
        (["F3", "A3", "C4"], "F2"),
        (["C4", "E4", "G4"], "C3"),
        (["G3", "B3", "D4"], "G2"),
    ]
    bar = beat * 4
    for k in range(int(LENGTH / bar)):
        tones, root = chords[k % 4]
        add(pad_chord([note(x) for x in tones], bar), k * bar)
        add(bass(note(root), beat * 1.5), k * bar)
        add(bass(note(root), beat * 1.5, gain=0.12), k * bar + beat * 2.5)

    mix /= np.max(np.abs(mix)) / 0.8
    out_dir = ROOT / "assets" / "music"
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / "tick_tock.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    m4a = out_dir / "tick_tock.m4a"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "2", "-c:a", "aac", "-b:a", "128k", str(m4a)], check=True)
    wav.unlink()
    print(f"완성: {m4a}")


if __name__ == "__main__":
    main()
