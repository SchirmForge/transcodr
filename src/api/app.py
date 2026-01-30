"""FastAPI application for video transcoding daemon."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    DaemonStatus,
    EncodingRequest,
    JobInfo,
    JobListResponse,
    JobStatus,
    QueueInfo,
    SubmitJobRequest,
    SubmitJobResponse,
    CancelJobResponse,
    WatchFolderInfo,
    WatchFolderListResponse,
)
from .queue import JobQueue
from .watcher import WatchFolderManager, WatchfolderService
from ..config.manager import ConfigManager
from ..core.hardware import HardwareCapabilities

logger = logging.getLogger(__name__)

# Global state
_start_time: datetime = datetime.now()
_job_queue: Optional[JobQueue] = None
_watch_manager: Optional[WatchFolderManager] = None
_watchfolder_service: Optional[WatchfolderService] = None
_config = None

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    global _start_time, _job_queue, _watch_manager, _watchfolder_service, _config

    logger.info("Starting videotranscode daemon...")
    _start_time = datetime.now()

    # Ensure config directory structure exists
    ConfigManager.ensure_config_structure()

    # Load configuration
    _config = ConfigManager.load_config()
    logger.info(f"Configuration loaded from: {ConfigManager.DEFAULT_CONFIG_PATH}")

    # Initialize job queue
    _job_queue = JobQueue(
        max_concurrent=_config.daemon.max_concurrent_jobs,
        db_path=_config.get_jobs_db_path(),
    )
    await _job_queue.start()
    logger.info(f"Job queue started (max concurrent: {_config.daemon.max_concurrent_jobs})")

    # Initialize watch folder manager
    _watch_manager = WatchFolderManager(_job_queue)
    await _watch_manager.start()
    logger.info("Watch folder manager started")

    # Load hot folders from config
    for hot_folder in _config.hot_folders:
        request = EncodingRequest(
            mode="watch",
            profiles=[hot_folder.profile],
            source=str(hot_folder.path),
            recursive=hot_folder.recursive,
            min_age_seconds=hot_folder.min_age_seconds,
        )
        await _watch_manager.register(request)
        logger.info(f"Registered hot folder: {hot_folder.path}")

    # Initialize watchfolder service (for command file watchfolders)
    _watchfolder_service = WatchfolderService(_job_queue, _watch_manager)
    await _watchfolder_service.start()
    logger.info("Watchfolder service started")

    yield

    # Shutdown
    logger.info("Shutting down videotranscode daemon...")
    if _watchfolder_service:
        await _watchfolder_service.stop()
    if _watch_manager:
        await _watch_manager.stop()
    if _job_queue:
        await _job_queue.stop()
    logger.info("Daemon stopped")


# Create FastAPI app
app = FastAPI(
    title="Video Transcode Daemon",
    description="REST API for video transcoding with FFmpeg",
    version=VERSION,
    lifespan=lifespan,
)

# CORS middleware (for web UI access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Status Endpoints
# =============================================================================

@app.get("/", tags=["Status"])
async def root():
    """Root endpoint - basic API info."""
    return {
        "name": "Video Transcode Daemon",
        "version": VERSION,
        "docs": "/docs",
    }


@app.get("/status", response_model=DaemonStatus, tags=["Status"])
async def get_status():
    """Get daemon status including queue info and hardware capabilities."""
    global _start_time, _job_queue, _watch_manager, _config

    uptime = (datetime.now() - _start_time).total_seconds()

    # Get queue info
    queue_info = await _job_queue.get_queue_info() if _job_queue else QueueInfo(
        total_jobs=0,
        pending_jobs=0,
        running_jobs=0,
        completed_jobs=0,
        failed_jobs=0,
        max_concurrent=1,
        current_concurrent=0,
    )

    # Get watch folders
    watch_folders = await _watch_manager.list_folders() if _watch_manager else []

    # Get hardware capabilities
    hw = HardwareCapabilities()
    hardware = hw.get_summary()

    return DaemonStatus(
        running=True,
        version=VERSION,
        uptime_seconds=uptime,
        queue=queue_info,
        watch_folders=watch_folders,
        hardware=hardware,
        config_path=str(ConfigManager.DEFAULT_CONFIG_PATH),
    )


@app.get("/health", tags=["Status"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# =============================================================================
# Job Endpoints
# =============================================================================

@app.post("/jobs", response_model=SubmitJobResponse, tags=["Jobs"])
async def submit_job(request: SubmitJobRequest):
    """
    Submit a new encoding job or register a watch folder.

    For mode='encode': Creates encoding jobs for the source files.
    For mode='watch': Registers a watch folder for continuous monitoring.
    """
    global _job_queue, _watch_manager

    encoding_request = request.request

    # Validate request
    issues = encoding_request.validate_request()
    if issues:
        raise HTTPException(status_code=400, detail="; ".join(issues))

    if encoding_request.mode.value == "watch":
        # Register watch folder
        if not _watch_manager:
            raise HTTPException(status_code=500, detail="Watch manager not initialized")

        watch_folder_id = await _watch_manager.register(encoding_request)
        return SubmitJobResponse(
            success=True,
            job_ids=[],
            watch_folder_id=watch_folder_id,
            message=f"Watch folder registered: {encoding_request.source}",
        )
    else:
        # Submit encoding job(s)
        if not _job_queue:
            raise HTTPException(status_code=500, detail="Job queue not initialized")

        job_ids = await _job_queue.submit(encoding_request)
        return SubmitJobResponse(
            success=True,
            job_ids=job_ids,
            message=f"Submitted {len(job_ids)} job(s)",
        )


@app.get("/jobs", response_model=JobListResponse, tags=["Jobs"])
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum jobs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List jobs with optional filtering."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    jobs = await _job_queue.list_jobs(status=status, limit=limit, offset=offset)
    total = await _job_queue.count_jobs(status=status)

    return JobListResponse(jobs=jobs, total=total)


@app.get("/jobs/{job_id}", response_model=JobInfo, tags=["Jobs"])
async def get_job(job_id: str):
    """Get job details by ID."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    job = await _job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return job


@app.delete("/jobs/{job_id}", response_model=CancelJobResponse, tags=["Jobs"])
async def cancel_job(job_id: str):
    """Cancel a pending or running job."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    success = await _job_queue.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found or cannot be cancelled: {job_id}")

    return CancelJobResponse(success=True, message=f"Job cancelled: {job_id}")


@app.post("/jobs/{job_id}/retry", response_model=JobInfo, tags=["Jobs"])
async def retry_job(job_id: str):
    """Retry a failed job."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    job = await _job_queue.retry_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found or cannot be retried: {job_id}")

    return job


# =============================================================================
# Watch Folder Endpoints
# =============================================================================

@app.get("/watch-folders", response_model=WatchFolderListResponse, tags=["Watch Folders"])
async def list_watch_folders():
    """List all registered watch folders."""
    global _watch_manager

    if not _watch_manager:
        raise HTTPException(status_code=500, detail="Watch manager not initialized")

    folders = await _watch_manager.list_folders()
    return WatchFolderListResponse(watch_folders=folders, total=len(folders))


@app.get("/watch-folders/{folder_id}", response_model=WatchFolderInfo, tags=["Watch Folders"])
async def get_watch_folder(folder_id: str):
    """Get watch folder details."""
    global _watch_manager

    if not _watch_manager:
        raise HTTPException(status_code=500, detail="Watch manager not initialized")

    folder = await _watch_manager.get_folder(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail=f"Watch folder not found: {folder_id}")

    return folder


@app.delete("/watch-folders/{folder_id}", tags=["Watch Folders"])
async def remove_watch_folder(folder_id: str):
    """Remove a watch folder."""
    global _watch_manager

    if not _watch_manager:
        raise HTTPException(status_code=500, detail="Watch manager not initialized")

    success = await _watch_manager.unregister(folder_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Watch folder not found: {folder_id}")

    return {"success": True, "message": f"Watch folder removed: {folder_id}"}


@app.post("/watch-folders/{folder_id}/pause", tags=["Watch Folders"])
async def pause_watch_folder(folder_id: str):
    """Pause a watch folder."""
    global _watch_manager

    if not _watch_manager:
        raise HTTPException(status_code=500, detail="Watch manager not initialized")

    success = await _watch_manager.pause(folder_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Watch folder not found: {folder_id}")

    return {"success": True, "message": f"Watch folder paused: {folder_id}"}


@app.post("/watch-folders/{folder_id}/resume", tags=["Watch Folders"])
async def resume_watch_folder(folder_id: str):
    """Resume a paused watch folder."""
    global _watch_manager

    if not _watch_manager:
        raise HTTPException(status_code=500, detail="Watch manager not initialized")

    success = await _watch_manager.resume(folder_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Watch folder not found: {folder_id}")

    return {"success": True, "message": f"Watch folder resumed: {folder_id}"}


# =============================================================================
# Queue Control Endpoints
# =============================================================================

@app.post("/queue/pause", tags=["Queue"])
async def pause_queue():
    """Pause the job queue (no new jobs will start)."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    await _job_queue.pause()
    return {"success": True, "message": "Queue paused"}


@app.post("/queue/resume", tags=["Queue"])
async def resume_queue():
    """Resume the job queue."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    await _job_queue.resume()
    return {"success": True, "message": "Queue resumed"}


@app.delete("/queue/completed", tags=["Queue"])
async def clear_completed_jobs():
    """Clear all completed jobs from the queue."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    count = await _job_queue.clear_completed()
    return {"success": True, "message": f"Cleared {count} completed jobs"}


@app.delete("/queue/failed", tags=["Queue"])
async def clear_failed_jobs():
    """Clear all failed jobs from the queue."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    count = await _job_queue.clear_failed()
    return {"success": True, "message": f"Cleared {count} failed jobs"}
