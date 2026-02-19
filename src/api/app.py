"""FastAPI application for Transcodr daemon."""

import logging
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    BrowseEntry,
    BrowseResponse,
    ConfigLocationsInfo,
    ConfigUpdateRequest,
    DiskLocationInfo,
    DiskUsageInfo,
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
from ..config.schema import Config
from .queue import JobQueue
from ..watcher import WatchfolderService
from ..config.manager import ConfigManager, expand_path
from ..core.hardware import HardwareCapabilities
from ..profiles.store import get_profile_manager

logger = logging.getLogger(__name__)

# Global state
_start_time: datetime = datetime.now()
_job_queue: Optional[JobQueue] = None
_watchfolder_service: Optional[WatchfolderService] = None
_config = None

VERSION = "0.3.6"

def _build_disk_usage(path: str) -> Optional[DiskUsageInfo]:
    """Build disk usage info for a path."""
    try:
        usage = shutil.disk_usage(path)
    except Exception:
        return None

    used = usage.total - usage.free
    percent_used = (used / usage.total * 100.0) if usage.total > 0 else 0.0

    return DiskUsageInfo(
        path=path,
        total_bytes=usage.total,
        used_bytes=used,
        free_bytes=usage.free,
        percent_used=round(percent_used, 1),
    )


def _resolve_usage_path(path: Path) -> Path:
    """Resolve path for disk queries, falling back to nearest existing parent."""
    expanded = expand_path(path)
    if not expanded.is_absolute():
        expanded = (Path.cwd() / expanded)

    try:
        resolved = expanded.resolve()
    except Exception:
        resolved = expanded

    candidate = resolved
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent

    if candidate.exists():
        return candidate
    return Path("/")


def _find_mount_point(path: Path) -> Path:
    """Find mount point for a path by walking parents."""
    current = _resolve_usage_path(path)

    while True:
        try:
            if os.path.ismount(current):
                return current
        except Exception:
            pass

        if current.parent == current:
            return current
        current = current.parent


def _get_disk_usage_summary(
    disk_locations: list[DiskLocationInfo],
) -> list[DiskUsageInfo]:
    """Get deduplicated mount usage summary from disk locations."""
    disks: list[DiskUsageInfo] = []
    seen_paths: set[str] = set()

    for location in disk_locations:
        if location.mount_path in seen_paths:
            continue
        seen_paths.add(location.mount_path)
        disks.append(
            DiskUsageInfo(
                path=location.mount_path,
                total_bytes=location.total_bytes,
                used_bytes=location.used_bytes,
                free_bytes=location.free_bytes,
                percent_used=location.percent_used,
            )
        )

    disks.sort(key=lambda d: (d.path != "/", d.path))
    return disks


def _get_disk_location_summary(
    config_locations: Optional[ConfigLocationsInfo],
) -> list[DiskLocationInfo]:
    """Get disk usage mapped to key runtime locations."""
    locations: list[DiskLocationInfo] = []
    usage_cache: dict[str, tuple[Path, DiskUsageInfo]] = {}

    items: list[tuple[str, Path]] = [("System (/)", Path("/"))]
    if config_locations:
        items.extend(
            [
                ("Config", Path(config_locations.config_dir)),
                ("Source", Path(config_locations.root_media)),
                ("Temp", Path(config_locations.temp_dir)),
                ("Backup", Path(config_locations.backup_dir)),
            ]
        )
        if config_locations.log_dir:
            items.append(("Logs", Path(config_locations.log_dir)))

    for label, path in items:
        mount_path_obj = _find_mount_point(path)
        mount_path = str(mount_path_obj)
        if mount_path not in usage_cache:
            usage_path = _resolve_usage_path(path)
            usage = _build_disk_usage(str(usage_path))
            if not usage:
                continue
            usage_cache[mount_path] = (usage_path, usage)

        _, usage = usage_cache[mount_path]
        locations.append(
            DiskLocationInfo(
                label=label,
                path=str(path),
                mount_path=mount_path,
                total_bytes=usage.total_bytes,
                used_bytes=usage.used_bytes,
                free_bytes=usage.free_bytes,
                percent_used=usage.percent_used,
            )
        )

    return locations


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
    logger.info(f"Configuration loaded from: {ConfigManager.get_default_config_path()}")

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
        min_free_space_gb=_config.storage.min_free_space_gb,
        on_extension_mismatch=_config.storage.on_extension_mismatch.value,
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


# API Router - all API endpoints live under /api prefix
api_router = APIRouter()


# =============================================================================
# Status Endpoints
# =============================================================================

@api_router.get("/status", response_model=DaemonStatus, tags=["Status"])
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

    config_dir = expand_path(_config.get_config_dir()) if _config else ConfigManager.get_config_dir()
    config_file = expand_path(ConfigManager.get_default_config_path())
    profiles_dir = expand_path(_config.get_profiles_dir()) if _config else config_dir / "profiles"
    watchfolders_dir = config_dir / "watchfolders"
    jobs_db = expand_path(_config.get_jobs_db_path()) if _config else config_dir / "jobs.db"
    root_media = expand_path(_config.storage.root_media) if _config else Path.home() / "Videos"
    temp_dir = expand_path(_config.storage.temp_dir) if _config else Path("/tmp/transcodr")
    log_dir = expand_path(_config.logging.dir) if (_config and _config.logging.dir) else None

    backup_raw = Path(
        os.path.expandvars(
            os.path.expanduser(
                str(_config.storage.backup_dir if _config else "./.originals")
            )
        )
    )
    backup_dir = backup_raw if backup_raw.is_absolute() else root_media / backup_raw
    backup_dir = expand_path(backup_dir)

    config_locations = ConfigLocationsInfo(
        config_file=str(config_file),
        config_dir=str(config_dir),
        profiles_dir=str(profiles_dir),
        watchfolders_dir=str(watchfolders_dir),
        jobs_db=str(jobs_db),
        root_media=str(root_media),
        temp_dir=str(temp_dir),
        log_dir=str(log_dir) if log_dir else None,
        backup_dir=str(backup_dir),
    )
    disk_locations = _get_disk_location_summary(config_locations)
    disks = _get_disk_usage_summary(disk_locations)

    return DaemonStatus(
        running=True,
        version=VERSION,
        uptime_seconds=uptime,
        queue=queue_info,
        watch_folders=[],  # Config-based watchfolders are listed via /watchfolders endpoint
        hardware=hardware,
        disks=disks,
        disk_locations=disk_locations,
        config_locations=config_locations,
        config_path=str(ConfigManager.get_default_config_path()),
    )


@api_router.get("/health", tags=["Status"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# =============================================================================
# Job Endpoints
# =============================================================================

@api_router.post("/jobs", response_model=SubmitJobResponse, tags=["Jobs"])
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


@api_router.get("/jobs", response_model=JobListResponse, tags=["Jobs"])
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


@api_router.get("/jobs/{job_id}", response_model=JobInfo, tags=["Jobs"])
async def get_job(job_id: str):
    """Get job details by ID."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    job = await _job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return job


@api_router.delete("/jobs/{job_id}", response_model=CancelJobResponse, tags=["Jobs"])
async def cancel_job(job_id: str):
    """Cancel a pending or running job."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    success = await _job_queue.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found or cannot be cancelled: {job_id}")

    return CancelJobResponse(success=True, message=f"Job cancelled: {job_id}")


@api_router.post("/jobs/{job_id}/retry", response_model=JobInfo, tags=["Jobs"])
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

@api_router.get("/watchfolders", tags=["Watchfolders"])
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


@api_router.get("/watchfolders/{folder_id}", tags=["Watchfolders"])
async def get_watchfolder(folder_id: str):
    """Get watchfolder details by ID."""
    global _watchfolder_service

    if _watchfolder_service:
        watcher = _watchfolder_service.get_watcher(folder_id)
        if watcher:
            watcher["source"] = "config"
            return watcher

    raise HTTPException(status_code=404, detail=f"Watchfolder not found: {folder_id}")


@api_router.delete("/watchfolders/{folder_id}", tags=["Watchfolders"])
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


@api_router.post("/watchfolders/{folder_id}/pause", tags=["Watchfolders"])
async def pause_watchfolder(folder_id: str):
    """Pause a watchfolder."""
    global _watchfolder_service

    if _watchfolder_service:
        success = _watchfolder_service.pause_watcher(folder_id)
        if success:
            return {"success": True, "message": f"Watchfolder paused: {folder_id}"}

    raise HTTPException(status_code=404, detail=f"Watchfolder not found: {folder_id}")


@api_router.post("/watchfolders/{folder_id}/resume", tags=["Watchfolders"])
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

@api_router.post("/queue/pause", tags=["Queue"])
async def pause_queue():
    """Pause the job queue (no new jobs will start)."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    await _job_queue.pause()
    return {"success": True, "message": "Queue paused"}


@api_router.post("/queue/resume", tags=["Queue"])
async def resume_queue():
    """Resume the job queue."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    await _job_queue.resume()
    return {"success": True, "message": "Queue resumed"}


@api_router.delete("/queue/completed", tags=["Queue"])
async def clear_completed_jobs():
    """Clear all completed jobs from the queue."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    count = await _job_queue.clear_completed()
    return {"success": True, "message": f"Cleared {count} completed jobs"}


@api_router.delete("/queue/failed", tags=["Queue"])
async def clear_failed_jobs():
    """Clear all failed jobs from the queue."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    count = await _job_queue.clear_failed()
    return {"success": True, "message": f"Cleared {count} failed jobs"}


@api_router.delete("/queue/warning", tags=["Queue"])
async def clear_warning_jobs():
    """Clear all warning jobs (completed with warnings) from the queue."""
    global _job_queue

    if not _job_queue:
        raise HTTPException(status_code=500, detail="Job queue not initialized")

    count = await _job_queue.clear_warning()
    return {"success": True, "message": f"Cleared {count} warning jobs"}


# =============================================================================
# Admin Endpoints
# =============================================================================

@api_router.get("/config", tags=["Admin"])
async def get_config():
    """Get current daemon configuration."""
    global _config

    return {
        "ffmpeg": {
            "binary_path": _config.ffmpeg.binary_path,
            "hardware_accel": _config.ffmpeg.hardware_accel,
        },
        "daemon": {
            "host": _config.daemon.host,
            "port": _config.daemon.port,
            "max_concurrent_jobs": _config.daemon.max_concurrent_jobs,
        },
        "storage": {
            "temp_dir": str(_config.storage.temp_dir),
            "backup_originals": _config.storage.backup_originals,
            "backup_dir": _config.storage.backup_dir,
            "min_free_space_gb": _config.storage.min_free_space_gb,
            "root_media": str(_config.storage.root_media),
            "profile_name_separator": _config.storage.profile_name_separator,
            "on_extension_mismatch": _config.storage.on_extension_mismatch.value,
        },
        "logging": {
            "level": _config.logging.level,
            "dir": str(_config.logging.dir) if _config.logging.dir else None,
            "rotation": _config.logging.rotation,
            "per_job_logs": _config.logging.per_job_logs,
        },
        "validation": {
            "duration_tolerance": _config.validation.duration_tolerance,
        },
    }


@api_router.put("/config", tags=["Admin"])
async def update_config(update: ConfigUpdateRequest):
    """
    Update daemon configuration. Writes to config.yaml and reloads.
    Only provided sections are updated; omitted sections are unchanged.
    """
    global _config

    config_path = ConfigManager.get_default_config_path()

    # Build merged config dict from current config
    current = _config.model_dump(mode="python")

    # Merge updates into current config
    if update.ffmpeg:
        current.setdefault("ffmpeg", {}).update(update.ffmpeg)
    if update.daemon:
        current.setdefault("daemon", {}).update(update.daemon)
    if update.storage:
        current.setdefault("storage", {}).update(update.storage)
    if update.logging:
        current.setdefault("logging", {}).update(update.logging)
    if update.validation:
        current.setdefault("validation", {}).update(update.validation)

    # Validate by constructing Config (raises on invalid values)
    try:
        new_config = Config(**current)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {e}")

    # Validate runtime (paths exist, etc.)
    errors, config_warnings = ConfigManager.validate_config(new_config)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=f"Config validation failed: {'; '.join(errors)}"
        )

    # Check if host/port changed — warn that restart is needed
    response_warnings = list(config_warnings)
    if (new_config.daemon.host != _config.daemon.host or
            new_config.daemon.port != _config.daemon.port):
        response_warnings.append(
            "Host/port changes require a daemon restart to take effect."
        )

    # Save to disk
    ConfigManager.save_config(new_config, config_path)

    # Apply to running daemon
    _config = new_config
    if _job_queue:
        _job_queue.set_max_concurrent(_config.daemon.max_concurrent_jobs)
        _job_queue.set_root_media(_config.storage.root_media)
        _job_queue.clear_profile_cache()

    logger.info("Configuration updated and saved via API")

    return {
        "success": True,
        "message": "Configuration saved and reloaded",
        "warnings": response_warnings,
    }


@api_router.post("/reload", tags=["Admin"])
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
        logger.info(f"Configuration reloaded from: {ConfigManager.get_default_config_path()}")

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
            "config_path": str(ConfigManager.get_default_config_path()),
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
                    "on_extension_mismatch": _config.storage.on_extension_mismatch.value,
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


@api_router.post("/purge", tags=["Admin"])
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

@api_router.get("/profiles", tags=["Profiles"])
async def list_profiles():
    """List all available encoding profiles."""
    pm = get_profile_manager()
    profiles = pm.list_profiles()

    result = []
    for name in profiles:
        info = pm.get_profile_info(name)
        # Add source indicator (builtin vs user)
        profile_file = pm._find_profile_file(name)
        info["source"] = "builtin" if profile_file and "builtin" in str(profile_file) else "user"
        result.append(info)

    return {"profiles": result, "total": len(result)}


@api_router.get("/profiles/{name}", tags=["Profiles"])
async def get_profile(name: str):
    """Get profile details."""
    pm = get_profile_manager()
    if not pm.profile_exists(name):
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}")

    info = pm.get_profile_info(name)
    profile_file = pm._find_profile_file(name)
    info["source"] = "builtin" if profile_file and "builtin" in str(profile_file) else "user"
    return info


@api_router.delete("/profiles/{name}", tags=["Profiles"])
async def delete_profile(
    name: str,
    confirm: bool = Query(False, description="Confirm the delete operation"),
):
    """
    Delete a user profile.

    Cannot delete built-in profiles.
    Requires confirm=true query parameter.
    """
    pm = get_profile_manager()
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
# File Browser Endpoint
# =============================================================================

_VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m2ts", ".ts", ".mts"}
_BLOCKED_PATHS = {"/proc", "/sys", "/dev", "/etc", "/boot", "/root"}

@api_router.get("/browse", response_model=BrowseResponse, tags=["Browse"])
async def browse_filesystem(
    path: Optional[str] = Query(None, description="Directory path to browse"),
):
    """
    Browse the filesystem for video files and directories.

    Defaults to root_media from config. Returns directories and video files only.
    """
    global _config

    root_media = str(expand_path(_config.storage.root_media))

    # Default to root_media
    browse_path = Path(path if path else root_media).resolve()

    # Security: block sensitive paths
    browse_str = str(browse_path)
    for blocked in _BLOCKED_PATHS:
        if browse_str == blocked or browse_str.startswith(blocked + "/"):
            raise HTTPException(status_code=403, detail=f"Access denied: {browse_str}")

    if not browse_path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {browse_str}")

    if not browse_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {browse_str}")

    # Build parent path
    parent_path = str(browse_path.parent) if browse_path != browse_path.parent else None

    # Scan directory
    dirs: list[BrowseEntry] = []
    files: list[BrowseEntry] = []

    try:
        import os
        with os.scandir(browse_path) as scanner:
            count = 0
            for entry in scanner:
                if count >= 1000:
                    break
                try:
                    if entry.name.startswith("."):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(BrowseEntry(
                            name=entry.name,
                            type="directory",
                            path=str(Path(entry.path).resolve()),
                        ))
                        count += 1
                    elif entry.is_file(follow_symlinks=False):
                        ext = Path(entry.name).suffix.lower()
                        if ext in _VIDEO_EXTENSIONS:
                            files.append(BrowseEntry(
                                name=entry.name,
                                type="file",
                                path=str(Path(entry.path).resolve()),
                                size=entry.stat().st_size,
                            ))
                            count += 1
                except PermissionError:
                    continue
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {browse_str}")

    # Sort: directories first (alpha), then files (alpha)
    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=lambda e: e.name.lower())

    return BrowseResponse(
        current_path=browse_str,
        parent_path=parent_path,
        root_media=root_media,
        entries=dirs + files,
    )


# Include API router with /api prefix
app.include_router(api_router, prefix="/api")


# =============================================================================
# Web UI SPA (must be after all route definitions)
# =============================================================================

_webui_dir = Path(__file__).parent.parent.parent / "webui" / "dist"
if _webui_dir.is_dir():
    _webui_assets = _webui_dir / "assets"
    if _webui_assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_webui_assets)), name="webui-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for SPA client-side routing."""
        if full_path:
            file_path = (_webui_dir / full_path).resolve()
            if file_path.is_relative_to(_webui_dir.resolve()) and file_path.is_file():
                return FileResponse(file_path)
        return FileResponse(_webui_dir / "index.html")
