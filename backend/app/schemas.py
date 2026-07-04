"""API のリクエスト/レスポンススキーマ。"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class JobState(str, Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    error = "error"


class JobCreatedResponse(BaseModel):
    job_id: str
    state: JobState


class JobStatusResponse(BaseModel):
    job_id: str
    state: JobState
    error: Optional[str] = None
    download_url: Optional[str] = None


class TrackInfo(BaseModel):
    id: str
    title: str
    credit: str
    license: str
    preview_url: str


class TracksResponse(BaseModel):
    tracks: List[TrackInfo]
