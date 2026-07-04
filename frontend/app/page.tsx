"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { UploadForm } from "@/components/UploadForm";
import { createVideo, getStatus, type JobState } from "@/lib/api";

const POLL_INTERVAL_MS = 1500;

const STATE_LABEL: Record<JobState, string> = {
  queued: "順番待ち…",
  processing: "動画を生成中…",
  done: "完成しました",
  error: "失敗しました",
};

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [state, setState] = useState<JobState | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const busy = state === "queued" || state === "processing";

  const reset = () => {
    setJobId(null);
    setState(null);
    setDownloadUrl(null);
    setError(null);
  };

  const handleSubmit = useCallback(
    async (files: File[], rotation: number, trackId: string) => {
      reset();
      try {
        const { job_id } = await createVideo(files, rotation, trackId);
        setJobId(job_id);
        setState("queued");
      } catch (e) {
        setError(e instanceof Error ? e.message : "不明なエラー");
      }
    },
    [],
  );

  // ジョブ状態のポーリング
  useEffect(() => {
    if (!jobId || !busy) return;

    let active = true;
    const poll = async () => {
      try {
        const status = await getStatus(jobId);
        if (!active) return;
        setState(status.state);
        if (status.state === "done") {
          setDownloadUrl(status.download_url);
        } else if (status.state === "error") {
          setError(status.error ?? "動画の生成に失敗しました");
        } else {
          timer.current = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "不明なエラー");
      }
    };
    // 生成は数秒で終わることが多いため、初回は待たずに即確認する
    poll();

    return () => {
      active = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [jobId, busy]);

  return (
    <main className="container">
      <h1>image-movie</h1>
      <p className="subtitle">画像から BGM 付きのスライドショー動画を作成します。</p>

      <UploadForm disabled={busy} onSubmit={handleSubmit} />

      {busy && (
        <div className="status">
          <span className="spinner" />
          {state && STATE_LABEL[state]}
        </div>
      )}

      {error && <p className="error">⚠️ {error}</p>}

      {state === "done" && downloadUrl && (
        <div className="result">
          <video src={downloadUrl} controls autoPlay loop muted />
          <a className="download" href={downloadUrl} download>
            <button type="button">動画をダウンロード</button>
          </a>
        </div>
      )}
    </main>
  );
}
