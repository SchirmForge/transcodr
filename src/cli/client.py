#!/usr/bin/env python3
"""CLI client for interacting with the video transcode daemon."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import requests
except ImportError:
    print("Error: 'requests' package is required. Install with: pip install requests")
    sys.exit(1)

import yaml

from src.config.manager import ConfigManager


class DaemonClient:
    """Client for communicating with the daemon API."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make request to daemon API."""
        try:
            response = requests.request(method, self._url(path), **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.ConnectionError:
            print(f"Error: Cannot connect to daemon at {self.base_url}")
            print("Make sure the daemon is running: python -m src.cli.daemon")
            sys.exit(1)
        except requests.HTTPError as e:
            try:
                error = response.json()
                print(f"Error: {error.get('detail', str(e))}")
            except Exception:
                print(f"Error: {e}")
            sys.exit(1)

    def get_status(self) -> dict:
        """Get daemon status."""
        return self._request("GET", "/status")

    def submit_job(self, request: dict) -> dict:
        """Submit encoding job."""
        return self._request("POST", "/jobs", json={"request": request})

    def list_jobs(self, status: Optional[str] = None, limit: int = 20) -> dict:
        """List jobs."""
        params = {"limit": limit}
        if status:
            params["status"] = status
        return self._request("GET", "/jobs", params=params)

    def get_job(self, job_id: str) -> dict:
        """Get job details."""
        return self._request("GET", f"/jobs/{job_id}")

    def cancel_job(self, job_id: str) -> dict:
        """Cancel a job."""
        return self._request("DELETE", f"/jobs/{job_id}")

    def retry_job(self, job_id: str) -> dict:
        """Retry a failed job."""
        return self._request("POST", f"/jobs/{job_id}/retry")

    def list_watch_folders(self) -> dict:
        """List runtime-registered watch folders."""
        return self._request("GET", "/watch-folders")

    def list_watchfolders(self) -> dict:
        """List config-based watchfolders (from YAML files)."""
        return self._request("GET", "/watchfolders")

    def remove_watch_folder(self, folder_id: str) -> dict:
        """Remove a watch folder."""
        return self._request("DELETE", f"/watch-folders/{folder_id}")

    def pause_queue(self) -> dict:
        """Pause the job queue."""
        return self._request("POST", "/queue/pause")

    def resume_queue(self) -> dict:
        """Resume the job queue."""
        return self._request("POST", "/queue/resume")

    def clear_completed(self) -> dict:
        """Clear completed jobs."""
        return self._request("DELETE", "/queue/completed")

    def clear_failed(self) -> dict:
        """Clear failed jobs."""
        return self._request("DELETE", "/queue/failed")

    def reload_config(self) -> dict:
        """Reload daemon configuration."""
        return self._request("POST", "/reload")

    def purge_database(self, force: bool = False, confirm: bool = True) -> dict:
        """Purge all jobs from database."""
        params = {"force": str(force).lower(), "confirm": str(confirm).lower()}
        return self._request("POST", "/purge", params=params)


def get_client() -> DaemonClient:
    """Get daemon client with configured URL."""
    config = ConfigManager.load_config()
    base_url = f"http://{config.daemon.host}:{config.daemon.port}"
    return DaemonClient(base_url)


def cmd_status(args):
    """Show daemon status."""
    client = get_client()
    status = client.get_status()

    print("=" * 60)
    print("DAEMON STATUS")
    print("=" * 60)
    print()
    print(f"  Running:     {status['running']}")
    print(f"  Version:     {status['version']}")
    print(f"  Uptime:      {status['uptime_seconds']:.0f}s")
    print()

    queue = status['queue']
    print("QUEUE:")
    print(f"  Total jobs:     {queue['total_jobs']}")
    print(f"  Pending:        {queue['pending_jobs']}")
    print(f"  Running:        {queue['running_jobs']} / {queue['max_concurrent']}")
    print(f"  Completed:      {queue['completed_jobs']}")
    print(f"  Failed:         {queue['failed_jobs']}")
    print()

    hw = status['hardware']
    print("HARDWARE:")
    print(f"  VAAPI:          {'Yes' if hw.get('vaapi') else 'No'}")
    print(f"  NVIDIA:         {'Yes' if hw.get('nvidia_nvenc') else 'No'}")
    print(f"  Intel QSV:      {'Yes' if hw.get('intel_qsv') else 'No'}")
    print(f"  Recommended:    {hw.get('recommended') or 'CPU'}")
    print()

    if status['watch_folders']:
        print("WATCH FOLDERS:")
        for wf in status['watch_folders']:
            active = "Active" if wf['active'] else "Paused"
            print(f"  {wf['id'][:8]}... {wf['path']} [{active}]")
        print()


def cmd_submit(args):
    """Submit encoding job."""
    client = get_client()

    # Build request
    if args.file:
        # Load from YAML file
        with open(args.file) as f:
            request = yaml.safe_load(f)
    else:
        # Build from arguments
        request = {
            "source": args.source,
            "output_mode": "destination" if args.destination else "replace",
        }

        if args.profile:
            request["profiles"] = args.profile
        else:
            request["profile"] = "x265-balanced"

        if args.destination:
            request["destination"] = args.destination

        if args.no_backup:
            request["backup"] = False

        if args.recursive is not None:
            request["recursive"] = args.recursive

        if args.watch:
            request["mode"] = "watch"
            if args.min_age:
                request["min_age_seconds"] = args.min_age

    # Submit
    result = client.submit_job(request)

    if result['success']:
        if result.get('watch_folder_id'):
            print(f"Watch folder registered: {result['watch_folder_id']}")
        else:
            print(f"Submitted {len(result['job_ids'])} job(s):")
            for job_id in result['job_ids'][:10]:  # Show first 10
                print(f"  {job_id}")
            if len(result['job_ids']) > 10:
                print(f"  ... and {len(result['job_ids']) - 10} more")
    else:
        print(f"Failed: {result['message']}")


def cmd_jobs(args):
    """List jobs."""
    client = get_client()
    result = client.list_jobs(status=args.status, limit=args.limit)

    jobs = result['jobs']

    if not jobs:
        print("No jobs found")
        return

    print(f"{'ID':<14} {'Status':<12} {'Profile':<15} {'Progress':<10} {'Source'}")
    print("-" * 82)

    for job in jobs:
        job_id = job['id'][:12]  # Show first 12 chars (enough to be unique)
        status = job['status']
        profile = job['profile'][:13] + ".." if len(job['profile']) > 15 else job['profile']
        progress = f"{job['progress']:.0f}%"
        source = Path(job['source_path']).name[:30]

        print(f"{job_id:<14} {status:<12} {profile:<15} {progress:<10} {source}")

    print()
    print(f"Total: {result['total']} jobs")


def cmd_job(args):
    """Show job details."""
    client = get_client()
    job = client.get_job(args.job_id)

    print("=" * 60)
    print("JOB DETAILS")
    print("=" * 60)
    print()
    print(f"  ID:            {job['id']}")
    print(f"  Status:        {job['status']}")
    print(f"  Profile:       {job['profile']}")
    print(f"  Source:        {job['source_path']}")
    if job['output_path']:
        print(f"  Output:        {job['output_path']}")
    print()
    print(f"  Progress:      {job['progress']:.1f}%")
    print(f"  FPS:           {job['fps']:.1f}")
    print(f"  Frames:        {job['frames_processed']} / {job['frames_total']}")
    print()
    print(f"  Source size:   {job['source_size_bytes'] / 1024**2:.1f} MB")
    if job['output_size_bytes']:
        ratio = job['output_size_bytes'] / job['source_size_bytes'] * 100
        print(f"  Output size:   {job['output_size_bytes'] / 1024**2:.1f} MB ({ratio:.0f}%)")
    print()
    print(f"  Created:       {job['created_at']}")
    if job['started_at']:
        print(f"  Started:       {job['started_at']}")
    if job['completed_at']:
        print(f"  Completed:     {job['completed_at']}")
    if job['error_message']:
        print()
        print(f"  Error:         {job['error_message']}")


def cmd_cancel(args):
    """Cancel a job."""
    client = get_client()
    result = client.cancel_job(args.job_id)
    print(result['message'])


def cmd_retry(args):
    """Retry a failed job."""
    client = get_client()
    job = client.retry_job(args.job_id)
    print(f"Job {job['id']} requeued")


def cmd_watch(args):
    """List watchfolders."""
    client = get_client()

    result = client.list_watchfolders()
    watchfolders = result.get('watchfolders', [])

    if not watchfolders:
        print("No watchfolders running")
        print()
        print("Create a watchfolder config in ~/.config/videotranscode/watchfolders/")
        print("and restart the daemon.")
        return

    # Group by type
    command_watchers = [w for w in watchfolders if w.get('type') == 'command']
    media_watchers = [w for w in watchfolders if w.get('type') == 'media']

    if command_watchers:
        print("COMMAND WATCHFOLDERS (watch for YAML command files):")
        for watcher in command_watchers:
            status = "paused" if watcher.get('paused') else "active"
            source = watcher.get('source', 'config')
            print(f"  {watcher['path']} [{status}] ({source})")
        print()

    if media_watchers:
        print("MEDIA WATCHFOLDERS (watch for video files):")
        for watcher in media_watchers:
            status = "paused" if watcher.get('paused') else "active"
            source = watcher.get('source', 'config')
            profiles = ", ".join(watcher.get('profiles', []))
            dest = watcher.get('destination', 'N/A')
            pending = watcher.get('pending_files', 0)
            submitted = watcher.get('submitted_jobs', 0)
            print(f"  {watcher['path']} [{status}] ({source})")
            print(f"    profiles: {profiles}")
            print(f"    destination: {dest}")
            if pending or submitted:
                print(f"    pending: {pending}, submitted: {submitted}")
        print()


def cmd_pause(args):
    """Pause the queue."""
    client = get_client()
    result = client.pause_queue()
    print(result['message'])


def cmd_resume(args):
    """Resume the queue."""
    client = get_client()
    result = client.resume_queue()
    print(result['message'])


def cmd_clear(args):
    """Clear completed or failed jobs."""
    client = get_client()

    if args.failed:
        result = client.clear_failed()
    else:
        result = client.clear_completed()

    print(result['message'])


def cmd_profiles(args):
    """List available encoding profiles."""
    from src.profiles.manager import ProfileManager

    pm = ProfileManager()
    profiles = pm.list_profiles()

    if not profiles:
        print("No profiles found")
        return

    print(f"{'Profile':<18} {'Codec':<12} {'Hardware':<12} {'Description'}")
    print("-" * 80)

    for profile_name in profiles:
        try:
            info = pm.get_profile_info(profile_name)
            codec = info.get('codec', 'N/A')[:10]

            # Get hardware variants
            hw_variants = info.get('hardware_variants', [])
            if hw_variants:
                hardware = ','.join(hw_variants)[:10]
            else:
                hardware = '-'

            description = info.get('description', '')[:38]
            if len(info.get('description', '')) > 38:
                description += ".."

            print(f"{profile_name:<18} {codec:<12} {hardware:<12} {description}")
        except Exception as e:
            print(f"{profile_name:<18} {'Error':<12} {'-':<12} {str(e)[:38]}")

    print()
    print(f"Total: {len(profiles)} profiles")
    print(f"Location: {pm.user_profile_dir}")


def cmd_reload(args):
    """Reload daemon configuration."""
    client = get_client()
    result = client.reload_config()

    print()
    print("=" * 60)
    print("CONFIGURATION RELOADED")
    print("=" * 60)
    print()
    print(f"  Config file: {result.get('config_path', 'N/A')}")
    print()

    # Display configuration if available
    config = result.get('config', {})
    if config:
        daemon = config.get('daemon', {})
        storage = config.get('storage', {})
        ffmpeg = config.get('ffmpeg', {})

        print("DAEMON:")
        print(f"  Host:              {daemon.get('host', 'N/A')}")
        print(f"  Port:              {daemon.get('port', 'N/A')}")
        print(f"  Max concurrent:    {daemon.get('max_concurrent_jobs', 'N/A')}")
        print()
        print("STORAGE:")
        print(f"  Root media:        {storage.get('root_media', 'N/A')}")
        print(f"  Temp directory:    {storage.get('temp_dir', 'N/A')}")
        print(f"  Backup directory:  {storage.get('backup_dir', 'N/A')}")
        print(f"  Backup originals:  {storage.get('backup_originals', 'N/A')}")
        print(f"  Min free space:    {storage.get('min_free_space_gb', 'N/A')} GB")
        print()
        print("ENCODING:")
        print(f"  Hardware accel:    {ffmpeg.get('hardware_accel', 'N/A')}")
        print()

    print("=" * 60)


def cmd_purge(args):
    """Purge all jobs from database."""
    client = get_client()

    # Confirmation prompt unless -y/--yes is passed
    if not args.yes:
        response = input("This will delete all job history. Are you sure? [y/N] ")
        if response.lower() not in ('y', 'yes'):
            print("Aborted")
            return

    try:
        result = client.purge_database(force=args.force, confirm=True)
        print(result['message'])
    except Exception as e:
        error_msg = str(e)
        if "409" in error_msg and "in progress" in error_msg:
            print("Error: Cannot purge while jobs are in progress.")
            print("Use --force to cancel running jobs and purge anyway.")
        else:
            raise


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Video Transcode CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show daemon status")
    status_parser.set_defaults(func=cmd_status)

    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit encoding job")
    submit_parser.add_argument("source", nargs="?", help="Source file or folder")
    submit_parser.add_argument("-p", "--profile", action="append", help="Profile(s) to use")
    submit_parser.add_argument("-d", "--destination", help="Destination folder")
    submit_parser.add_argument("--no-backup", action="store_true", help="Don't backup originals")
    submit_parser.add_argument("-r", "--recursive", type=bool, help="Process recursively")
    submit_parser.add_argument("-f", "--file", help="Load request from YAML file")
    submit_parser.add_argument("--watch", action="store_true", help="Register as watch folder")
    submit_parser.add_argument("--min-age", type=int, help="Min file age for watch folder (seconds)")
    submit_parser.set_defaults(func=cmd_submit)

    # Jobs command
    jobs_parser = subparsers.add_parser("jobs", help="List jobs")
    jobs_parser.add_argument("-s", "--status", help="Filter by status")
    jobs_parser.add_argument("-l", "--limit", type=int, default=20, help="Max jobs to show")
    jobs_parser.set_defaults(func=cmd_jobs)

    # Job command
    job_parser = subparsers.add_parser("job", help="Show job details")
    job_parser.add_argument("job_id", help="Job ID")
    job_parser.set_defaults(func=cmd_job)

    # Cancel command
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a job")
    cancel_parser.add_argument("job_id", help="Job ID to cancel")
    cancel_parser.set_defaults(func=cmd_cancel)

    # Retry command
    retry_parser = subparsers.add_parser("retry", help="Retry a failed job")
    retry_parser.add_argument("job_id", help="Job ID to retry")
    retry_parser.set_defaults(func=cmd_retry)

    # Watch command
    watch_parser = subparsers.add_parser("watch", help="List watch folders")
    watch_parser.set_defaults(func=cmd_watch)

    # Pause command
    pause_parser = subparsers.add_parser("pause", help="Pause the queue")
    pause_parser.set_defaults(func=cmd_pause)

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume the queue")
    resume_parser.set_defaults(func=cmd_resume)

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear completed/failed jobs")
    clear_parser.add_argument("--failed", action="store_true", help="Clear failed instead of completed")
    clear_parser.set_defaults(func=cmd_clear)

    # Profiles command
    profiles_parser = subparsers.add_parser("profiles", help="List available encoding profiles")
    profiles_parser.set_defaults(func=cmd_profiles)

    # Reload command
    reload_parser = subparsers.add_parser("reload", help="Reload daemon configuration")
    reload_parser.set_defaults(func=cmd_reload)

    # Purge command
    purge_parser = subparsers.add_parser("purge", help="Purge all jobs from database")
    purge_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    purge_parser.add_argument("-f", "--force", action="store_true", help="Force purge even if jobs are in progress")
    purge_parser.set_defaults(func=cmd_purge)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Run command
    args.func(args)


if __name__ == "__main__":
    main()
