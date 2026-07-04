"use client";

import { useEffect, useState } from "react";
import { AUTO_TRACK, getTracks, type Track } from "@/lib/api";

const ROTATIONS = [0, 90, 180, 270] as const;

interface Props {
  disabled: boolean;
  onSubmit: (files: File[], rotation: number, trackId: string) => void;
}

export function UploadForm({ disabled, onSubmit }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [rotation, setRotation] = useState<number>(0);
  const [previews, setPreviews] = useState<string[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [trackId, setTrackId] = useState<string>(AUTO_TRACK);
  const [tracksError, setTracksError] = useState<string | null>(null);

  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  useEffect(() => {
    getTracks()
      .then((list) => {
        setTracks(list);
        setTracksError(null);
      })
      .catch(() => {
        setTracks([]);
        setTracksError(
          "BGM一覧を取得できませんでした。おまかせ（自動選曲）で生成されます。",
        );
      });
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (files.length > 0) onSubmit(files, rotation, trackId);
  };

  const selectedTrack = tracks.find((t) => t.id === trackId) ?? null;

  return (
    <form className="panel" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="images">画像を選択（複数可・jpg/png/webp）</label>
        <input
          id="images"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          disabled={disabled}
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
        />
        {previews.length > 0 && (
          <div className="preview">
            {previews.map((src, i) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={i} src={src} alt={`preview ${i + 1}`} />
            ))}
          </div>
        )}
      </div>

      <div className="field">
        <label>BGM</label>
        <div className="track-chips">
          <button
            type="button"
            className={`chip${trackId === AUTO_TRACK ? " selected" : ""}`}
            disabled={disabled}
            onClick={() => setTrackId(AUTO_TRACK)}
          >
            おまかせ
          </button>
          {tracks.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`chip${trackId === t.id ? " selected" : ""}`}
              disabled={disabled}
              onClick={() => setTrackId(t.id)}
            >
              {t.title}
            </button>
          ))}
        </div>
        {selectedTrack && (
          <div className="track-preview">
            {/* key で曲切替時にプレーヤーを作り直す */}
            <audio
              key={selectedTrack.id}
              controls
              preload="none"
              src={selectedTrack.preview_url}
            />
            {/* CC BY 楽曲のためクレジットは常時可視で表示する */}
            <small className="track-credit">
              {selectedTrack.credit}（{selectedTrack.license}）
            </small>
          </div>
        )}
        {tracksError && <p className="field-note">{tracksError}</p>}
      </div>

      <div className="field">
        <label htmlFor="rotation">回転</label>
        <select
          id="rotation"
          value={rotation}
          disabled={disabled}
          onChange={(e) => setRotation(Number(e.target.value))}
        >
          {ROTATIONS.map((deg) => (
            <option key={deg} value={deg}>
              {deg}°
            </option>
          ))}
        </select>
      </div>

      <button type="submit" disabled={disabled || files.length === 0}>
        {files.length > 0 ? `${files.length} 枚で動画を作成` : "画像を選択してください"}
      </button>
    </form>
  );
}
