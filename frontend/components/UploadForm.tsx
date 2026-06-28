"use client";

import { useEffect, useState } from "react";

const ROTATIONS = [0, 90, 180, 270] as const;

interface Props {
  disabled: boolean;
  onSubmit: (files: File[], rotation: number) => void;
}

export function UploadForm({ disabled, onSubmit }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [rotation, setRotation] = useState<number>(0);
  const [previews, setPreviews] = useState<string[]>([]);

  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (files.length > 0) onSubmit(files, rotation);
  };

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
