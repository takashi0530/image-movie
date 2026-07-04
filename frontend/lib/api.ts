export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type JobState = "queued" | "processing" | "done" | "error";

export interface JobStatus {
  job_id: string;
  state: JobState;
  error: string | null;
  download_url: string | null;
}

export interface Track {
  id: string;
  title: string;
  credit: string;
  license: string;
  preview_url: string;
}

export const AUTO_TRACK = "auto";

async function detail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return typeof body?.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

async function request<T>(
  path: string,
  fallback: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    throw new Error(await detail(res, fallback));
  }
  return res.json();
}

// バックエンドはプロキシ安全のため相対パスを返す。ここでベースURLを前置して絶対化する。
const absolutize = (path: string | null) =>
  path ? `${API_BASE}${path}` : null;

export async function getTracks(): Promise<Track[]> {
  const body = await request<{ tracks: Track[] }>(
    "/tracks",
    "BGM一覧の取得に失敗しました",
  );
  return body.tracks.map((t) => ({
    ...t,
    preview_url: absolutize(t.preview_url)!,
  }));
}

export async function createVideo(
  files: File[],
  rotation: number,
  trackId: string = AUTO_TRACK,
): Promise<{ job_id: string }> {
  const form = new FormData();
  files.forEach((file) => form.append("images", file));
  form.append("rotation", String(rotation));
  form.append("track_id", trackId);

  return request("/videos", "アップロードに失敗しました", {
    method: "POST",
    body: form,
  });
}

export async function getStatus(jobId: string): Promise<JobStatus> {
  const status = await request<JobStatus>(
    `/videos/${jobId}`,
    "状態の取得に失敗しました",
  );
  return { ...status, download_url: absolutize(status.download_url) };
}
