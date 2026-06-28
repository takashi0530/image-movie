"""画像→動画 生成 API。

- POST /videos          : 画像をアップロードしてジョブを開始（202 + job_id）
- GET  /videos/{id}     : ジョブ状態を取得
- GET  /videos/{id}/download : 完成した MP4 をダウンロード
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse

from .. import tracks as track_registry
from ..config import get_settings
from ..jobs import store
from ..schemas import (
    JobCreatedResponse,
    JobState,
    JobStatusResponse,
    TrackInfo,
    TracksResponse,
)
from ..services import images as image_service
from ..services import video as video_service

router = APIRouter()

VALID_ROTATIONS = (0, 90, 180, 270)


def _process(job_id: str, src_paths: List[Path], rotation: int, audio_path: Path) -> None:
    """バックグラウンドで実行される動画生成処理。"""
    settings = get_settings()
    job = store.get(job_id)
    if job is None:
        return
    job.state = JobState.processing
    try:
        frames_dir = job.work_dir / "frames"
        image_service.normalize_images(
            sorted(src_paths),
            frames_dir,
            width=settings.width,
            height=settings.height,
            rotation=rotation,
        )
        output_path = job.work_dir / "movie.mp4"
        video_service.build_video(
            frames_dir,
            audio_path,
            output_path,
            input_framerate=settings.input_framerate,
            output_fps=settings.output_fps,
        )
        job.output_path = output_path
        job.state = JobState.done
    except Exception as exc:  # noqa: BLE001 - 失敗はジョブ状態へ集約
        job.state = JobState.error
        job.error = str(exc)


@router.get("/tracks", response_model=TracksResponse)
async def list_tracks(request: Request) -> TracksResponse:
    """選択可能な BGM トラック一覧（プレビューURL付き）。"""
    items = [
        TrackInfo(
            id=t.id,
            title=t.title,
            credit=t.credit,
            license=t.license,
            preview_url=str(request.url_for("preview_track", track_id=t.id)),
        )
        for t in track_registry.TRACKS
    ]
    return TracksResponse(tracks=items)


@router.get("/tracks/{track_id}/preview", name="preview_track")
async def preview_track(track_id: str) -> FileResponse:
    settings = get_settings()
    track = track_registry.get_track(track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="トラックが見つかりません")
    return FileResponse(
        track_registry.track_path(settings.music_dir, track), media_type="audio/aac"
    )


@router.post("/videos", status_code=202, response_model=JobCreatedResponse)
async def create_video(
    background_tasks: BackgroundTasks,
    images: List[UploadFile] = File(...),
    rotation: int = Form(0),
    track_id: str = Form(track_registry.AUTO),
) -> JobCreatedResponse:
    settings = get_settings()
    store.cleanup_expired(settings.job_ttl_seconds)

    if rotation not in VALID_ROTATIONS:
        raise HTTPException(status_code=400, detail="rotation は 0/90/180/270 のいずれか")

    filenames = [f.filename or "" for f in images]
    contents = [await f.read() for f in images]
    sizes = [len(c) for c in contents]

    # BGM トラックを解決（auto は枚数で自動選曲）
    track = track_registry.resolve(track_id, len(filenames))
    if track is None:
        raise HTTPException(status_code=400, detail=f"不明な track_id: {track_id}")
    audio_path = track_registry.track_path(settings.music_dir, track)

    try:
        image_service.validate_uploads(
            filenames,
            sizes,
            allowed_extensions=settings.allowed_extensions,
            max_files=settings.max_files,
            max_file_size_bytes=settings.max_file_size_bytes,
        )
    except image_service.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job_id = uuid.uuid4().hex
    work_dir = settings.work_dir / job_id
    uploads_dir = work_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # 元の filename は使わず連番で保存（パストラバーサル回避 + 順序の安定化）
    src_paths: List[Path] = []
    for idx, (name, data) in enumerate(zip(filenames, contents), start=1):
        ext = Path(name).suffix.lower()
        safe_path = uploads_dir / f"{idx:04d}{ext}"
        safe_path.write_bytes(data)
        src_paths.append(safe_path)

    store.create(job_id, work_dir)
    background_tasks.add_task(_process, job_id, src_paths, rotation, audio_path)
    return JobCreatedResponse(job_id=job_id, state=JobState.queued)


@router.get("/videos/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str, request: Request) -> JobStatusResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    download_url = None
    if job.state == JobState.done:
        download_url = str(request.url_for("download_video", job_id=job_id))

    return JobStatusResponse(
        job_id=job.id,
        state=job.state,
        error=job.error,
        download_url=download_url,
    )


@router.get("/videos/{job_id}/download", name="download_video")
async def download_video(job_id: str) -> FileResponse:
    job = store.get(job_id)
    if job is None or job.state != JobState.done or job.output_path is None:
        raise HTTPException(status_code=404, detail="動画がまだ準備できていません")
    return FileResponse(job.output_path, media_type="video/mp4", filename="movie.mp4")
