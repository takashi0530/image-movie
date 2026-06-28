"""ジョブの状態管理（インメモリ）。

フェーズ1は単一プロセス想定のためインメモリで十分。
複数プロセス/永続化が必要になったら Redis 等に差し替える。
"""
from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .schemas import JobState


@dataclass
class Job:
    id: str
    work_dir: Path
    state: JobState = JobState.queued
    error: Optional[str] = None
    output_path: Optional[Path] = None
    created_at: float = field(default_factory=time.time)


class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}

    def create(self, job_id: str, work_dir: Path) -> Job:
        job = Job(id=job_id, work_dir=work_dir)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def cleanup_expired(self, ttl_seconds: int) -> None:
        """TTL を超えたジョブの作業ディレクトリを削除し、レコードを破棄する。"""
        now = time.time()
        for job_id in list(self._jobs):
            job = self._jobs[job_id]
            if now - job.created_at > ttl_seconds:
                if job.work_dir.exists():
                    shutil.rmtree(job.work_dir, ignore_errors=True)
                del self._jobs[job_id]


store = JobStore()
