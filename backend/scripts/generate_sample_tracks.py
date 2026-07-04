"""サンプル BGM を手続き的に生成する（完全オリジナル = CC0 / 再配布可）。

外部楽曲はライセンス確認が必要なため、サンプルは本スクリプトで合成した
オリジナル曲を同梱する。生成物は権利的にクリアで、動画への埋め込み・再配布が可能。

使い方:
    cd backend && source .venv/bin/activate && python scripts/generate_sample_tracks.py

`assets/music/` に calm.aac / happy.aac / epic.aac を出力する。
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

# 半音 → 周波数（A4=440）
def note_freq(semitones_from_a4: float) -> float:
    return 440.0 * (2.0 ** (semitones_from_a4 / 12.0))


# 主要音名 → A4 からの半音数
NOTE = {
    "C3": -21, "D3": -19, "E3": -17, "F3": -16, "G3": -14, "A3": -12, "B3": -10,
    "C4": -9, "D4": -7, "E4": -5, "F4": -4, "G4": -2, "A4": 0, "B4": 2,
    "C5": 3, "D5": 5, "E5": 7, "F5": 8, "G5": 10, "A5": 12, "B5": 14,
}


def adsr(n: int, attack=0.02, release=0.15) -> np.ndarray:
    env = np.ones(n)
    a = int(n * attack)
    r = int(n * release)
    if a > 0:
        env[:a] = np.linspace(0, 1, a)
    if r > 0:
        env[-r:] = np.linspace(1, 0, r)
    return env


def tone(freq: float, dur: float, partials=(1.0, 0.5, 0.25), detune=0.003) -> np.ndarray:
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    wave_ = np.zeros(n)
    for i, amp in enumerate(partials, start=1):
        # 軽いデチューンで厚みを出す
        wave_ += amp * np.sin(2 * np.pi * freq * i * (1 + detune * (i - 1)) * t)
    return wave_ * adsr(n)


def pad(chord_notes, dur: float) -> np.ndarray:
    """和音パッド。"""
    out = np.zeros(int(SR * dur))
    for name in chord_notes:
        out += tone(note_freq(NOTE[name]), dur, partials=(1.0, 0.4, 0.2))
    return out / max(1, len(chord_notes))


def arp(chord_notes, dur: float, steps: int) -> np.ndarray:
    """分散和音メロディ。"""
    n = int(SR * dur)
    out = np.zeros(n)
    step_dur = dur / steps
    seq = (chord_notes * ((steps // len(chord_notes)) + 1))[:steps]
    for i, name in enumerate(seq):
        s = int(i * step_dur * SR)
        note = tone(note_freq(NOTE[name]) * 2, step_dur, partials=(1.0, 0.3))
        out[s : s + len(note)] += note[: max(0, n - s)]
    return out * 0.6


def soft_clip(x: np.ndarray) -> np.ndarray:
    return np.tanh(x * 1.2)


def normalize(x: np.ndarray, peak=0.85) -> np.ndarray:
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 0 else x


def build_track(progression, bar_dur: float, pad_gain=0.7, arp_gain=0.5, arp_steps=8) -> np.ndarray:
    bars = []
    for chord in progression:
        mix = pad(chord, bar_dur) * pad_gain + arp(chord, bar_dur, arp_steps) * arp_gain
        bars.append(mix)
    mono = np.concatenate(bars)
    mono = soft_clip(mono)
    mono = normalize(mono)
    # 疑似ステレオ（左右に僅かな遅延）
    delay = int(SR * 0.012)
    left = mono
    right = np.concatenate([np.zeros(delay), mono])[: len(mono)]
    stereo = np.stack([left, right], axis=1)
    # 全体フェード
    fade = int(SR * 0.5)
    stereo[:fade] *= np.linspace(0, 1, fade)[:, None]
    stereo[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return stereo


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
    subprocess.run(
        [ffmpeg, "-y", "-i", wav_path, "-c:a", "aac", "-b:a", "192k", str(out_path)],
        check=True,
        capture_output=True,
    )
    Path(wav_path).unlink(missing_ok=True)


# 各トラックのコード進行（1小節=和音）
TRACKS = {
    # おだやか: C - Am - F - G（4小節 x 2 ループ）
    "calm": dict(
        progression=[["C4", "E4", "G4"], ["A3", "C4", "E4"], ["F4", "A4", "C5"], ["G4", "B4", "D5"]] * 3,
        bar_dur=2.4, pad_gain=0.8, arp_gain=0.35, arp_steps=6,
    ),
    # あかるい: C - G - Am - F、テンポ速め・分散和音多め
    "happy": dict(
        progression=[["C4", "E4", "G4"], ["G4", "B4", "D5"], ["A3", "C4", "E4"], ["F4", "A4", "C5"]] * 3,
        bar_dur=1.8, pad_gain=0.6, arp_gain=0.6, arp_steps=8,
    ),
    # 壮大: Am - F - C - G、低音厚め
    "epic": dict(
        progression=[["A3", "C4", "E4"], ["F4", "A4", "C5"], ["C4", "E4", "G4"], ["G4", "B4", "D5"]] * 3,
        bar_dur=2.6, pad_gain=0.9, arp_gain=0.45, arp_steps=4,
    ),
}


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, cfg in TRACKS.items():
        stereo = build_track(**cfg)
        out = ASSETS / f"{name}.aac"
        write_aac(stereo, out)
        dur = len(stereo) / SR
        print(f"generated {out.name}: {dur:.1f}s, {out.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
