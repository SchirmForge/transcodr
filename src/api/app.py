"""FastAPI application for Transcodr daemon."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
    process_encoding_request,
)
from .queue import JobQueue
from ..watcher import WatchfolderService
from ..config.manager import ConfigManager
from ..core.hardware import HardwareCapabilities
from ..profiles.manager import ProfileManager

logger = logging.getLogger(__name__)

# Global state
_start_time: datetime = datetime.now()
_job_queue: Optional[JobQueue] = None
_watchfolder_service: Optional[WatchfolderService] = None
_config = None

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    global _start_time, _job_queue, _watchfolder_service, _config

    logger.info("Starting transcodr daemon...")
    _start_time = datetime.now()

    # Ensure config directory structure exists
    ConfigManager.ensure_config_structure()

    # Load configuration
    _config = ConfigManager.load_config()
    logger.info(f"Configuration loaded from: {ConfigManager.DEFAULT_CONFIG_PATH}")

    # Validate configuration
    errors, warnings = ConfigManager.validate_config(_config)
    for warning in warnings:
        logger.warning(f"Config warning: {warning}")
    if errors:
        for error in errors:
            logger.error(f"Config error: {error}")
        raise RuntimeError(f"Configuration validation failed: {'; '.join(errors)}")

    # Initialize job queue
    _job_queue = JobQueue(
        max_concurrent=_config.daemon.max_concurrent_jobs,
        db_path=_config.get_jobs_db_path(),
        temp_dir=_config.storage.temp_dir,
        duration_tolerance_seconds=_config.validation.duration_tolerance,
        profile_name_separator=_config.storage.profile_name_separator,
        root_media=_config.storage.root_media,
    )
    await _job_queue.start()
    logger.info(f"Job queue started (max concurrent: {_config.daemon.max_concurrent_jobs}, temp: {_config.storage.temp_dir})")

    # Initialize watchfolder service (for config-based watchfolders)
    _watchfolder_service = WatchfolderService(_job_queue)
    await _watchfolder_service.start()
    logger.info("Watchfolder service started")

    yield

    # Shutdown
    logger.info("Shutting down transcodr daemon...")
    if _watchfolder_service:
        await _watchfolder_service.stop()
    if _job_queue:
        await _job_queue.stop()
    logger.info("Daemon stopped")


# Create FastAPI app
app = FastAPI(
    title="Transcodr Daemon",
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


# Middleware to strip /api prefix so web UI API calls (/api/jobs -> /jobs) work
@app.middleware("http")
async def strip_api_prefix(request: Request, call_next):
    path = request.scope["path"]
    if path.startswith("/api/") or path == "/api":
        request.scope["path"] = path[4:] or "/"
    return await call_next(request)


# =============================================================================
# Status Endpoints
# =============================================================================

@app.get("/status", response_model=DaemonStatus, tags=["Status"])
async def get_status():
    """Get daemon status including queue info and hardware capabilities."""
    global _start_time, _job_queue, _config

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

    # Get hardware capabilities
    hw = HardwareCapabilities()
    hardware = hw.get_summary()

    return DaemonStatus(
        running=True,
        version=VERSION,
        uptime_seconds=uptime,
        queue=queue_info,
        watch_folders=[],  # Config-based watchfolders are listed via /watchfolders endpoint
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
    Submit a new encoding job.

    Creates encoding jobs for the specified source files using the given profiles.
    """
    global _job_queue, _config

    encoding_request = request.request

    # Process request (expand $root_media, validate)
    encoding_request, issues = process_encoding_request(
        encoding_request,
        _config.storage.root_media
    )
    if issues:
        raise HTTPException(status_code=400, detail="; ".join(issues))

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

@app.get("/watchfolders", tags=["Watchfolders"])
async def list_watchfolders():
    """
    List all config-based watchfolders.

    Watchfolders are defined in ~/.config/transcodr/watchfolders/*.yaml
    """
    global _watchfolder_service

    result = {
        "watchfolders": [],
        "total": 0,
    }

    # Get config-based watchfolders
    if _watchfolder_service:
        config_watchers = _watchfolder_service.get_active_watchers()
        for watcher in config_watchers.get("command", []):
            watcher["source"] = "config"
            watcher["type"] = "command"
            result["watchfolders"].append(watcher)
        for watcher in config_watchers.get("media", []):
            watcher["source"] = "config"
            watcher["type"] = "media"
            result["watchfolders"].append(watcher)

    result["total"] = len(result["watchfolders"])
    return result


@app.get("/watchfolders/{folder_id}", tags=["Watchfolders"])
async def get_watchfolder(folder_id: str):
    """Get watchfolder details by ID."""
    global _watchfolder_service

    if _watchfolder_service:
        watcher = _watchfolder_service.get_watcher(folder_id)
        if watcher:
            watcher["source"] = "config"
            return watcher

    raise HTTPException(status_code=404, detail=f"Watchfolder not found: {folder_id}")


@app.delete("/watchfolders/{folder_id}", tags=["Watchfolders"])
async def remove_watchfolder(folder_id: str):
    """
    Remove a watchfolder.

    Config-based watchfolders cannot be removed via API - delete the YAML file instead.
    """
    global _watchfolder_service

    if _watchfolder_service:
        watcher = _watchfolder_service.get_watcher(folder_id)
        if watcher:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove config-based watchfolder via API. Delete the YAML file instead."
            )

    raise HTTPException(status_code=404, detail=f"Watchfolder not found: {folder_id}")


@app.post("/watchfolders/{folder_id}/pause", tags=["Watchfolders"])
async def pause_watchfolder(folder_id: str):
    """Pause a watchfolder."""
    global _watchfolder_service

    if _watchfolder_service:
        success = _watchfolder_service.pause_watcher(folder_id)
        if success:
            return {"success": True, "message": f"Watchfolder paused: {folder_id}"}

    raise HTTPException(status_code=404, detail=f"Watchfolder not found: {folder_id}")


@app.post("/watchfolders/{folder_id}/resume", tags=["Watchfolders"])
async def resume_watchfolder(folder_id: str):
    """Resume a paused watchfolder."""
    global _watchfolder_service

    if _watchfolder_service:
        success = _watchfolder_service.resume_watcher(folder_id)
        if success:
            return {"success": True, "message": f"Watchfolder resumed: {folder_id}"}

    raise HTTPException(status_code=404, detail=f"Watchfolder not found: {folder_id}")


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


# =============================================================================
# Admin Endpoints
# =============================================================================

@app.post("/reload", tags=["Admin"])
async def reload_config():
    """
    Reload configuration and watchfolders without restarting the daemon.

    This will:
    - Reload the main config file
    - Stop all current watchfolders
    - Reload and start watchfolders from config files
    """
    global _config, _watchfolder_service

    try:
        # Reload main config
        _config = ConfigManager.load_config()
        logger.info(f"Configuration reloaded from: {ConfigManager.DEFAULT_CONFIG_PATH}")

        # Validate configuration
        errors, warnings = ConfigManager.validate_config(_config)
        for warning in warnings:
            logger.warning(f"Config warning: {warning}")
        if errors:
            for error in errors:
                logger.error(f"Config error: {error}")
            raise HTTPException(
                status_code=400,
                detail=f"Configuration validation failed: {'; '.join(errors)}"
            )

        # Update job queue settings and clear profile cache
        if _job_queue:
            _job_queue.set_max_concurrent(_config.daemon.max_concurrent_jobs)
            _job_queue.set_root_media(_config.storage.root_media)
            _job_queue.clear_profile_cache()
            logger.info("Profile cache cleared")

        # Restart watchfolder service
        if _watchfolder_service:
            await _watchfolder_service.stop()
            await _watchfolder_service.start()
            logger.info("Watchfolder service reloaded")

        # Return configuration details
        from ..config.manager import expand_path
        root_media_expanded = str(expand_path(_config.storage.root_media))
        temp_dir_expanded = str(expand_path(_config.storage.temp_dir))

        return {
            "success": True,
            "message": "Configuration reloaded successfully",
            "config_path": str(ConfigManager.DEFAULT_CONFIG_PATH),
            "config": {
                "daemon": {
                    "host": _config.daemon.host,
                    "port": _config.daemon.port,
                    "max_concurrent_jobs": _config.daemon.max_concurrent_jobs,
                },
                "storage": {
                    "root_media": root_media_expanded,
                    "temp_dir": temp_dir_expanded,
                    "backup_dir": _config.storage.backup_dir,
                    "backup_originals": _config.storage.backup_originals,
                    "min_free_space_gb": _config.storage.min_free_space_gb,
                },
                "ffmpeg": {
                    "hardware_accel": _config.ffmpeg.hardware_accel,
                },
                "logging": {
                    "level": _config.logging.level,
                },
            },
        }
    except Exception as e:
        logger.error(f"Failed to reload configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reload configuration: {e}")


@app.post("/purge", tags=["Admin"])
async def purge_database(
    force: bool = Query(False, description="Force purge even if jobs are in progress"),
    confirm: bool = Query(False, description="Confirm the purge operation"),
):
    """
    Purge all jobs from the database (clear history).

    Requires confirm=true query parameter.
    Will fail if jobs are running/pending unless force=true.
    """
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Purge requires confirmation. Add ?confirm=true to proceed."
        )

    # Check for active jobs
    queue_info = await _job_queue.get_queue_info()
    active_jobs = queue_info.running_jobs + queue_info.pending_jobs

    if active_jobs > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot purge: {active_jobs} job(s) in progress. Use force=true to override."
        )

    # Purge all jobs
    count = await _job_queue.purge_all(force=force)

    return {
        "success": True,
        "message": f"Purged {count} job(s) from database",
        "jobs_purged": count,
    }


# =============================================================================
# Profile Endpoints
# =============================================================================

@app.get("/profiles", tags=["Profiles"])
async def list_profiles():
    """List all available encoding profiles."""
    pm = ProfileManager()
    profiles = pm.list_profiles()

    result = []
    for name in profiles:
        info = pm.get_profile_info(name)
        # Add source indicator (builtin vs user)
        profile_file = pm._find_profile_file(name)
        info["source"] = "builtin" if profile_file and "builtin" in str(profile_file) else "user"
        result.append(info)

    return {"profiles": result, "total": len(result)}


@app.get("/profiles/{name}", tags=["Profiles"])
async def get_profile(name: str):
    """Get profile details."""
    pm = ProfileManager()
    if not pm.profile_exists(name):
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}")

    info = pm.get_profile_info(name)
    profile_file = pm._find_profile_file(name)
    info["source"] = "builtin" if profile_file and "builtin" in str(profile_file) else "user"
    return info


@app.delete("/profiles/{name}", tags=["Profiles"])
async def delete_profile(
    name: str,
    confirm: bool = Query(False, description="Confirm the delete operation"),
):
    """
    Delete a user profile.

    Cannot delete built-in profiles.
    Requires confirm=true query parameter.
    """
    pm = ProfileManager()
    if not pm.profile_exists(name):
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}")

    profile_file = pm._find_profile_file(name)
    if profile_file and "builtin" in str(profile_file):
        raise HTTPException(status_code=400, detail="Cannot delete built-in profiles")

    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Delete requires confirmation. Add ?confirm=true to proceed."
        )

    profile_file.unlink()
    pm.clear_cache()
    return {"success": True, "message": f"Profile deleted: {name}"}


# =============================================================================
# Web UI Static Files (must be after all route definitions)
# =============================================================================

_webui_dir = Path(__file__).parent.parent.parent / "webui" / "dist"
if _webui_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_webui_dir), html=True), name="webui")
