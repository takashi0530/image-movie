"""BGM を手続き的に生成する（完全オリジナル = CC0 / 再配布可）。

v2: 約60秒・5テイスト。ドラム（キック/スネア/ハイハット）・ベースライン・
デチューン重ねシンセパッド・アルペジオ・サイドチェイン・ディレイ・
セクション構成（イントロ→ビルド→フル→アウトロ）を持つ小さなシンセエンジン。

使い方:
    cd backend && source .venv/bin/activate && python scripts/generate_sample_tracks.py

`assets/music/` に upbeat/happy/calm/emo/epic の .aac を出力する。
シードを固定しているので再実行しても同じ音になる。
"""
from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np

SR = 44100
ASSETS = Path(__file__).resolve().parent.parent / "assets" / "music"
rng = np.random.default_rng(20260704)


def f(midi: float) -> float:
    """MIDI ノート番号 → 周波数（A4=69=440Hz）。"""
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


# ---------------------------------------------------------------- DSP 基礎

def fir_lowpass(x: np.ndarray, cutoff: float, taps: int = 127) -> np.ndarray:
    fc = min(cutoff, SR * 0.45) / (SR / 2)
    m = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(fc * m) * fc * np.hamming(taps)
    h /= h.sum()
    return np.convolve(x, h, mode="same")


def highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    return x - fir_lowpass(x, cutoff)


def adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    """秒指定の ADSR。合計が n を超える場合は比率を保って収める。"""
    na, nd, nr = int(SR * a), int(SR * d), int(SR * r)
    if na + nd + nr > n:
        scale = n / max(1, na + nd + nr)
        na, nd, nr = int(na * scale), int(nd * scale), int(nr * scale)
    ns = max(0, n - na - nd - nr)
    return np.concatenate([
        np.linspace(0, 1, max(1, na)),
        np.linspace(1, s, max(1, nd)),
        np.full(ns, s),
        np.linspace(s, 0, max(1, nr)),
    ])[:n]


def saw(freq: float, n: int, detune: float = 0.0, phase: float = 0.0) -> np.ndarray:
    t = np.arange(n) / SR
    ph = freq * (1 + detune) * t + phase
    return 2.0 * (ph % 1.0) - 1.0


def supersaw(freq: float, n: int, voices: int = 5, spread: float = 0.008) -> np.ndarray:
    out = np.zeros(n)
    for i in range(voices):
        d = spread * (i - (voices - 1) / 2)
        out += saw(freq, n, d, phase=float(rng.random()))
    return out / voices


def delay_fx(x: np.ndarray, time_s: float, feedback: float = 0.35, taps: int = 3) -> np.ndarray:
    """シンプルなフィードバックディレイ（アルペジオに空間を与える）。"""
    d = int(SR * time_s)
    out = x.copy()
    for i in range(1, taps + 1):
        if i * d < len(x):
            out[i * d :] += x[: -i * d] * (feedback ** i)
    return out


def sidechain_env(total: int, bpm: float, depth: float) -> np.ndarray:
    """キックに合わせてパッドが沈む「ポンプ」用エンベロープ。"""
    beat = int(SR * 60 / bpm)
    t = np.arange(beat) / SR
    curve = 1 - depth * np.exp(-t / 0.09)
    env = np.ones(total)
    for s in range(0, total, beat):
        e = min(total, s + beat)
        env[s:e] = curve[: e - s]
    return env


def place(buf: np.ndarray, clip: np.ndarray, start: float, gain: float = 1.0) -> None:
    s = int(start)
    if s >= len(buf):
        return
    e = min(len(buf), s + len(clip))
    buf[s:e] += clip[: e - s] * gain


def shift(x: np.ndarray, time_s: float) -> np.ndarray:
    d = int(SR * time_s)
    return np.concatenate([np.zeros(d), x])[: len(x)]


# ---------------------------------------------------------------- 楽器

def kick(base: float = 45.0) -> np.ndarray:
    n = int(SR * 0.35)
    t = np.arange(n) / SR
    freq = base + 110 * np.exp(-t / 0.03)  # ピッチスイープ
    phase = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(phase) * np.exp(-t / 0.13)
    click = rng.standard_normal(n) * np.exp(-t / 0.004) * 0.35
    return body + click


def snare() -> np.ndarray:
    n = int(SR * 0.22)
    t = np.arange(n) / SR
    noise = highpass(rng.standard_normal(n), 1800) * np.exp(-t / 0.055)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    return noise * 0.8 + body * 0.6


def hat(open_: bool = False) -> np.ndarray:
    decay = 0.22 if open_ else 0.04
    n = int(SR * decay * 4)
    t = np.arange(n) / SR
    return highpass(rng.standard_normal(n), 6500) * np.exp(-t / decay)


def swell(dur: float) -> np.ndarray:
    """セクション前のノイズライザー。"""
    n = int(SR * dur)
    t = np.linspace(0, 1, n)
    noise = highpass(rng.standard_normal(n), 2500)
    return noise * (t ** 2.5)


def pluck(midi: float, dur: float, bright: float = 6.0) -> np.ndarray:
    n = int(SR * dur)
    x = supersaw(f(midi), n, voices=3, spread=0.004)
    x = fir_lowpass(x, min(f(midi) * bright, 9000))
    t = np.arange(n) / SR
    return x * np.exp(-t / (dur * 0.3 + 0.02))


def pad_chord(midis, dur: float, cutoff: float, voices: int = 5, spread: float = 0.008) -> np.ndarray:
    n = int(SR * dur)
    x = np.zeros(n)
    for m in midis:
        x += supersaw(f(m), n, voices=voices, spread=spread)
    x = fir_lowpass(x / len(midis), cutoff)
    return x * adsr(n, a=dur * 0.15, d=dur * 0.1, s=0.8, r=dur * 0.25)


def bass_note(midi: float, dur: float) -> np.ndarray:
    n = int(SR * dur)
    t = np.arange(n) / SR
    x = 0.6 * saw(f(midi), n) + 0.7 * np.sin(2 * np.pi * f(midi) * t)  # saw + サブ
    x = fir_lowpass(x, 900)
    x = np.tanh(1.5 * x)  # 軽いドライブ
    return x * adsr(n, a=0.005, d=0.05, s=0.8, r=0.05)


# ---------------------------------------------------------------- 曲のレンダリング

def render(style: dict) -> np.ndarray:
    bpm, bars = style["bpm"], style["bars"]
    beat_s = 60.0 / bpm
    bar_n = int(SR * 4 * beat_s)   # 4/4
    step_n = bar_n / 16            # 16分音符
    total = bar_n * bars

    drums = np.zeros(total)
    bass = np.zeros(total)
    pads = np.zeros(total)
    arps = np.zeros(total)

    K, SN, HC, HO = kick(style.get("kick_base", 45.0)), snare(), hat(), hat(open_=True)
    prog = style["prog"]
    roots = style["bass_roots"]
    arp_pat = style.get("arp_pattern")

    def layers_at(bar: int) -> set:
        for until, layers in style["sections"]:
            if bar < until:
                return layers
        return set()

    for bar in range(bars):
        layers = layers_at(bar)
        chord = prog[bar % len(prog)]
        root = roots[bar % len(roots)]
        base = bar * bar_n

        if "kick" in layers:
            for s in style.get("kick_steps", (0, 4, 8, 12)):
                place(drums, K, base + s * step_n, 0.95)
        if "snare" in layers:
            for s in style.get("snare_steps", (4, 12)):
                place(drums, SN, base + s * step_n, 0.8)
        if "hat" in layers:
            for s in range(0, 16, 2):
                place(drums, HC, base + s * step_n, 0.22)
        if "ohat" in layers:
            for s in (2, 6, 10, 14):
                place(drums, HO, base + s * step_n, 0.18)
        if "bass" in layers:
            for s, oct_up in style.get("bass_steps", [(i, 0) for i in range(0, 16, 2)]):
                note = root + 12 * oct_up
                place(bass, bass_note(note, step_n * 2 / SR), base + s * step_n, 0.8)
        if "pad" in layers:
            place(pads, pad_chord(
                chord, 4 * beat_s * 1.02,
                cutoff=style.get("pad_cutoff", 3000),
                voices=style.get("pad_voices", 5),
                spread=style.get("pad_spread", 0.008),
            ), base, 0.9)
        if "arp" in layers and arp_pat:
            tones = sorted(chord) + [m + 12 for m in sorted(chord)]
            for i, idx in enumerate(arp_pat):
                if idx is None:
                    continue
                place(arps, pluck(tones[idx % len(tones)], step_n * 2.2 / SR,
                                  bright=style.get("arp_bright", 6.0)),
                      base + i * step_n, 0.75)

    # セクション境界のライザー
    for riser_bar in style.get("risers", ()):
        clip = swell(4 * beat_s)
        place(drums, clip, (riser_bar * bar_n) - len(clip), 0.5)

    # アルペジオに付点8分ディレイ
    arps = delay_fx(arps, beat_s * 0.75, feedback=0.35)

    # サイドチェイン（キックに合わせてパッドが沈む）
    if style.get("sidechain", 0):
        pads *= sidechain_env(total, bpm, depth=style["sidechain"])

    mix = (drums * style.get("g_drums", 1.0)
           + bass * style.get("g_bass", 0.9)
           + pads * style.get("g_pads", 0.8)
           + arps * style.get("g_arps", 0.8))

    # マスター: ソフトクリップ → 疑似ステレオ（パッド/アルペジオを左右に散らす）→ 正規化
    mix = np.tanh(1.2 * mix)
    side = pads + arps
    left = mix + 0.22 * shift(side, 0.011)
    right = mix + 0.22 * shift(side, 0.017)
    stereo = np.stack([left, right], axis=1)
    stereo /= max(1e-9, float(np.max(np.abs(stereo)))) / 0.88

    # クリックノイズ防止のフェード
    fin, fout = int(SR * 0.03), int(SR * 1.2)
    stereo[:fin] *= np.linspace(0, 1, fin)[:, None]
    stereo[-fout:] *= np.linspace(1, 0, fout)[:, None]
    return stereo


# ---------------------------------------------------------------- 5トラック定義
# コードは MIDI ノート番号（C4=60）。約60秒になるよう bars を BPM から逆算している。

TRACKS = {
    # アップテンポ: 128BPM 4つ打ち・サイドチェイン・16分アルペジオ（C-G-Am-F）
    "upbeat": dict(
        bpm=128, bars=32,
        prog=[[60, 64, 67, 74], [59, 62, 67, 74], [60, 64, 69, 76], [60, 65, 69, 77]],
        bass_roots=[36, 43, 45, 41],
        bass_steps=[(0, 0), (2, 1), (4, 0), (6, 1), (8, 0), (10, 1), (12, 0), (14, 1)],
        arp_pattern=[0, 2, 4, 2, 5, 2, 4, 2, 0, 2, 4, 2, 6, 4, 2, 4],
        sections=[
            (4, {"arp", "hat"}),
            (8, {"arp", "hat", "kick", "bass", "ohat"}),
            (24, {"arp", "hat", "kick", "bass", "ohat", "snare", "pad"}),
            (28, {"arp", "hat", "kick", "bass", "snare", "pad"}),
            (32, {"arp", "pad"}),
        ],
        risers=(8, 24), sidechain=0.55, pad_cutoff=3400, arp_bright=7.0,
    ),
    # あかるい: 112BPM バウンス（G-Em-C-D）、裏打ちベース
    "happy": dict(
        bpm=112, bars=28,
        prog=[[59, 62, 67], [59, 64, 67], [60, 64, 67], [62, 66, 69]],
        bass_roots=[43, 40, 36, 38],
        kick_steps=(0, 8), snare_steps=(4, 12),
        bass_steps=[(2, 0), (6, 0), (10, 0), (14, 1)],
        arp_pattern=[0, None, 2, None, 4, None, 2, None, 5, None, 4, None, 2, None, 4, None],
        sections=[
            (2, {"pad", "arp"}),
            (10, {"pad", "arp", "kick", "snare", "bass", "hat"}),
            (26, {"pad", "arp", "kick", "snare", "bass", "hat", "ohat"}),
            (28, {"pad", "arp"}),
        ],
        risers=(10,), sidechain=0.3, pad_cutoff=3000, arp_bright=6.5,
    ),
    # おだやか: 76BPM ドラムレス・ロングパッド（Fmaj7-Am7-B♭maj7-C）
    "calm": dict(
        bpm=76, bars=19,
        prog=[[53, 57, 60, 64], [57, 60, 64, 67], [58, 62, 65, 69], [55, 60, 64, 67]],
        bass_roots=[41, 45, 46, 48],
        bass_steps=[(0, 0)],  # 全音符
        arp_pattern=[0, None, None, None, 2, None, None, None,
                     4, None, None, None, 5, None, None, None],
        sections=[
            (2, {"pad"}),
            (17, {"pad", "arp", "bass"}),
            (19, {"pad"}),
        ],
        sidechain=0, pad_cutoff=1900, pad_voices=6, pad_spread=0.005,
        arp_bright=4.0, g_pads=1.0, g_arps=0.55, g_bass=0.6,
    ),
    # せつない: 90BPM ハーフタイム・マイナー（Am-F-C-G）
    "emo": dict(
        bpm=90, bars=22,
        prog=[[57, 60, 64], [57, 60, 65], [55, 60, 64], [55, 59, 62]],
        bass_roots=[45, 41, 36, 43],
        kick_steps=(0,), snare_steps=(8,),
        bass_steps=[(0, 0), (8, 0)],
        arp_pattern=[0, None, 2, None, 4, None, 5, None, 4, None, 2, None, 0, None, 2, None],
        sections=[
            (2, {"pad", "arp"}),
            (6, {"pad", "arp", "bass"}),
            (18, {"pad", "arp", "bass", "kick", "snare", "hat"}),
            (22, {"pad", "arp"}),
        ],
        sidechain=0.3, pad_cutoff=2200, arp_bright=4.5, g_drums=0.7,
    ),
    # 壮大: 100BPM シネマティック（Dm-B♭-F-C）、太いパッドとライザー
    "epic": dict(
        bpm=100, bars=25,
        prog=[[50, 53, 57, 62], [53, 58, 62, 65], [53, 57, 60, 65], [48, 55, 60, 64]],
        bass_roots=[38, 34, 41, 36],
        kick_base=55.0, kick_steps=(0, 4, 8, 12), snare_steps=(8,),
        bass_steps=[(0, 0), (8, 0)],
        arp_pattern=[0, None, None, 1, None, None, 2, None, 3, None, None, 2, None, None, 1, None],
        sections=[
            (4, {"pad", "bass"}),
            (12, {"pad", "bass", "kick", "arp"}),
            (20, {"pad", "bass", "kick", "snare", "arp", "hat"}),
            (25, {"pad", "bass"}),
        ],
        risers=(12, 20), sidechain=0.4,
        pad_cutoff=3600, pad_voices=7, pad_spread=0.012, g_pads=1.0, g_drums=0.9,
    ),
}


# ---------------------------------------------------------------- 出力

def write_aac(stereo: np.ndarray, out_path: Path) -> None:
    pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    with wave.open(wav_path, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [ffmpeg, "-y", "-i", wav_path, "-c:a", "aac", "-b:a", "192k", str(out_path)],
        capture_output=True, text=True,
    )
    Path(wav_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-1000:])


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, style in TRACKS.items():
        stereo = render(style)
        out = ASSETS / f"{name}.aac"
        write_aac(stereo, out)
        print(f"generated {out.name}: {len(stereo) / SR:.1f}s, {out.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
