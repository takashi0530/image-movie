"""画像→動画 生成 API。

- POST /videos          : 画像をアップロードしてジョブを開始（202 + job_id）
- GET  /videos/{id}     : ジョブ状態を取得
- GET  /videos/{id}/download : 完成した MP4 をダウンロード
"""
from __future__ import annotations

import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
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
logger = logging.getLogger("image_movie")

VALID_ROTATIONS = (0, 90, 180, 270)


def save_upload_capped(src, dest: Path, max_bytes: int) -> None:
    """アップロードをストリーム保存しつつサイズ上限を書き込み時にも強制する。

    multipart パートに content-length が無いクライアントでは UploadFile.size が
    None になり事前検証（validate_uploads）をすり抜けるため、実バイト数で防ぐ。
    Cloud Run はファイルシステムが RAM 共有のため、無制限書き込みは OOM に直結する。
    """
    written = 0
    with dest.open("wb") as out:
        while chunk := src.read(1 << 20):
            written += len(chunk)
            if written > max_bytes:
                raise image_service.ValidationError(
                    f"ファイルサイズが大きすぎます（上限 {max_bytes // (1024 * 1024)}MB）"
                )
            out.write(chunk)


def _process(job_id: str, src_paths: List[Path], rotation: int, audio_path: Path) -> None:
    """バックグラウンドで実行される動画生成処理。"""
    settings = get_settings()
    job = store.get(job_id)
    if job is None:
        return
    job.state = JobState.processing
    started = time.perf_counter()
    try:
        frames_dir = job.work_dir / "frames"
        count = image_service.normalize_images(
            sorted(src_paths),
            frames_dir,
            width=settings.width,
            height=settings.height,
            rotation=rotation,
        )
        normalized = time.perf_counter()
        output_path = job.work_dir / "movie.mp4"
        video_service.build_video(
            frames_dir,
            audio_path,
            output_path,
            input_framerate=settings.input_framerate,
            output_fps=settings.output_fps,
            preset=settings.encode_preset,
        )
        encoded = time.perf_counter()
        # 中間ファイルを即時解放（Cloud Run では書込FS=RAMのため、残すとメモリを圧迫する）
        shutil.rmtree(frames_dir, ignore_errors=True)
        shutil.rmtree(job.work_dir / "uploads", ignore_errors=True)
        job.output_path = output_path
        job.state = JobState.done
        logger.info(
            "job %s done: images=%d normalize=%.2fs encode=%.2fs total=%.2fs",
            job_id,
            count,
            normalized - started,
            encoded - normalized,
            encoded - started,
        )
    except Exception as exc:  # noqa: BLE001 - 失敗はジョブ状態へ集約
        job.state = JobState.error
        job.error = str(exc)
        logger.exception("job %s failed after %.2fs", job_id, time.perf_counter() - started)


@router.get("/tracks", response_model=TracksResponse)
async def list_tracks() -> TracksResponse:
    """選択可能な BGM トラック一覧（プレビューURL付き）。

    URL は相対パスで返す（絶対URLを url_for で組むとリバースプロキシ配下で
    内部ホスト/http スキームが露出するため）。クライアント側で API ベースURLを前置する。
    """
    items = [
        TrackInfo(
            id=t.id,
            title=t.title,
            credit=t.credit,
            license=t.license,
            preview_url=f"/tracks/{t.id}/preview",
        )
        for t in track_registry.TRACKS
    ]
    return TracksResponse(tracks=items)


@router.get("/tracks/{track_id}/preview")
async def preview_track(track_id: str) -> FileResponse:
    settings = get_settings()
    track = track_registry.get_track(track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="トラックが見つかりません")
    path = track_registry.track_path(settings.music_dir, track)
    if not path.is_file():
        # レジストリとディスクの乖離（デプロイ漏れ・改名忘れ）は 500 ではなく 404 で返す
        raise HTTPException(status_code=404, detail="音源ファイルがありません")
    return FileResponse(
        path,
        media_type="audio/aac",
        headers={"Cache-Control": "public, max-age=86400"},
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

    # ---- 検証はアップロード本体を読み込む前に済ませる（不正リクエストを即拒否）----
    if rotation not in VALID_ROTATIONS:
        raise HTTPException(status_code=400, detail="rotation は 0/90/180/270 のいずれか")

    track = track_registry.resolve(track_id, len(images))
    if track is None:
        raise HTTPException(status_code=400, detail=f"不明な track_id: {track_id}")
    audio_path = track_registry.track_path(settings.music_dir, track)
    if not audio_path.is_file():
        # レジストリとディスクの乖離。受理して無音動画を作るのではなく、ここで失敗させる
        raise HTTPException(status_code=500, detail=f"音源ファイルがありません: {track.id}")

    filenames = [f.filename or "" for f in images]
    sizes = [f.size or 0 for f in images]
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

    # 元の filename は使わず連番で保存（パストラバーサル回避 + 順序の安定化）。
    # 全ファイルをメモリに載せず、スプールからストリームコピーする（上限も再強制）。
    src_paths: List[Path] = []
    try:
        for idx, (name, upload) in enumerate(zip(filenames, images), start=1):
            ext = Path(name).suffix.lower()
            safe_path = uploads_dir / f"{idx:04d}{ext}"
            save_upload_capped(upload.file, safe_path, settings.max_file_size_bytes)
            src_paths.append(safe_path)
    except image_service.ValidationError as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc))

    store.create(job_id, work_dir)
    background_tasks.add_task(_process, job_id, src_paths, rotation, audio_path)
    return JobCreatedResponse(job_id=job_id, state=JobState.queued)


@router.get("/videos/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str) -> JobStatusResponse:
    # POST 契機だけだと長時間 POST が来ない場合に残置が続くため、参照時にも掃除する
    store.cleanup_expired(get_settings().job_ttl_seconds)
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    # 相対パスで返す（preview_url と同じ理由でプロキシ安全）。クライアントがベースURLを前置する
    download_url = f"/videos/{job_id}/download" if job.state == JobState.done else None

    return JobStatusResponse(
        job_id=job.id,
        state=job.state,
        error=job.error,
        download_url=download_url,
    )


@router.get("/videos/{job_id}/download")
async def download_video(job_id: str) -> FileResponse:
    job = store.get(job_id)
    if job is None or job.state != JobState.done or job.output_path is None:
        raise HTTPException(status_code=404, detail="動画がまだ準備できていません")
    return FileResponse(job.output_path, media_type="video/mp4", filename="movie.mp4")
