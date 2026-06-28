export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type JobState = "queued" | "processing" | "done" | "error";

export interface JobStatus {
  job_id: string;
  state: JobState;
  error: string | null;
  download_url: string | null;
}

async function detail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return typeof body?.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

export interface Track {
  id: string;
  title: string;
  credit: string;
  license: string;
  preview_url: string;
}

export const AUTO_TRACK = "auto";

export async function getTracks(): Promise<Track[]> {
  const res = await fetch(`${API_BASE}/tracks`);
  if (!res.ok) {
    throw new Error(await detail(res, "BGM一覧の取得に失敗しました"));
  }
  const body = await res.json();
  return body.tracks;
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

  const res = await fetch(`${API_BASE}/videos`, { method: "POST", body: form });
  if (!res.ok) {
    throw new Error(await detail(res, "アップロードに失敗しました"));
  }
  return res.json();
}

export async function getStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/videos/${jobId}`);
  if (!res.ok) {
    throw new Error(await detail(res, "状態の取得に失敗しました"));
  }
  return res.json();
}
