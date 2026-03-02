// Job status enum matching backend
export type JobStatus = 'pending' | 'queued' | 'running' | 'completed' | 'warning' | 'failed' | 'cancelled' | 'interrupted'

// Output mode enum
export type OutputMode = 'replace' | 'destination'

// Job information - matches JobInfo from backend
export interface JobInfo {
  id: string
  status: JobStatus
  profile: string
  source_path: string
  output_path: string | null

  // Multi-profile info
  profile_index: number
  total_profiles: number
  parent_job_id: string | null

  // Progress
  progress: number // 0.0 to 100.0
  fps: number
  frames_processed: number
  frames_total: number
  eta_seconds: number | null
  eta_quality: 'rough' | 'stable' | 'high' | null

  // Timing (ISO strings from API)
  created_at: string
  started_at: string | null
  completed_at: string | null

  // Size info
  source_size_bytes: number
  output_size_bytes: number

  // Error / Warning
  error_message: string | null
  warning_message: string | null

  // Encoding settings (populated from profile)
  hardware_accel: string | null
  video_codec: string | null
  audio_codec: string | null
  subtitle_mode: string | null
  container: string | null
  use_temp_folder: boolean
}

// Queue statistics
export interface QueueInfo {
  total_jobs: number
  pending_jobs: number
  running_jobs: number
  completed_jobs: number
  failed_jobs: number
  max_concurrent: number
  current_concurrent: number
  paused: boolean
}

// Hardware info
export interface HardwareInfo {
  cpu_count?: number
  cpu_model?: string
  vaapi_available?: boolean
  nvenc_available?: boolean
  qsv_available?: boolean
  vaapi?: boolean
  nvidia_nvenc?: boolean
  intel_qsv?: boolean
  [key: string]: unknown
}

export interface DiskUsageInfo {
  path: string
  total_bytes: number
  used_bytes: number
  free_bytes: number
  percent_used: number
}

export interface DiskLocationInfo {
  label: string
  path: string
  mount_path: string
  total_bytes: number
  used_bytes: number
  free_bytes: number
  percent_used: number
}

export interface ConfigLocationsInfo {
  config_file: string
  config_dir: string
  profiles_dir: string
  watchfolders_dir: string
  jobs_db: string
  root_media: string
  temp_dir: string
  log_dir: string | null
  backup_dir: string
}

// Watch folder info - matches actual API response
export interface WatchFolderInfo {
  id: string
  path: string
  type: 'command' | 'media'
  source: 'config'
  active: boolean
  paused: boolean
  scan_interval: number
  errors?: string[]  // set when watchfolder failed validation (missing folder, etc.)
  yaml_path?: string  // absolute path to the source YAML config file
  // Media watcher specific fields (optional for command watchers)
  profiles?: string[]
  destination?: string
  use_profile_destination?: boolean
  file_patterns?: string[]
  pending_files?: number
  submitted_jobs?: number
}

// Daemon status - matches DaemonStatus from backend
export interface DaemonStatus {
  running: boolean
  version: string
  uptime_seconds: number
  queue: QueueInfo
  watch_folders: WatchFolderInfo[]
  hardware: HardwareInfo
  disks: DiskUsageInfo[]
  disk_locations: DiskLocationInfo[]
  config_locations: ConfigLocationsInfo
  config_path: string
}

// Profile info
export interface ProfileInfo {
  name: string
  description?: string
  codec?: string
  container?: string
  preset?: string
  crf?: number
  source: 'builtin' | 'user'
  base_profile?: boolean
  destination?: string | null
  file_path?: string  // absolute path to the source YAML file
  error?: string  // set when profile has an invalid path (missing destination folder, etc.)
  [key: string]: unknown
}

export interface BuiltinProfileEntry {
  name: string
  description?: string
  tags: string[]
  already_installed: boolean
}

export interface BuiltinsResponse {
  builtins: BuiltinProfileEntry[]
  total: number
}

export interface ImportBuiltinsRequest {
  names: string[]
}

export interface ImportBuiltinsResponse {
  imported: string[]
  skipped: string[]
  message: string
}

// File browser types
export interface BrowseEntry {
  name: string
  type: 'directory' | 'file'
  path: string
  size?: number | null
}

export interface BrowseResponse {
  current_path: string
  parent_path: string | null
  root_media: string
  entries: BrowseEntry[]
}

// Job submission types
export interface EncodingRequest {
  source: string
  profiles: string[]
  output_mode: OutputMode
  destination?: string
  use_profile_destination?: boolean
  preserve_structure?: boolean
  backup?: boolean
  backup_dir?: string
  recursive?: boolean
  hardware_accel?: string
  priority?: number
  create_profile_folders?: boolean
  append_profile_name?: boolean
  delete_source?: boolean
  use_temp_folder?: boolean
  copy_source_to_temp?: boolean
  auto_embed_subtitles?: boolean
  subtitles_languages?: 'all' | string[]
  subtitle_fallback_mode?: 'carry' | 'skip' | 'fail'
}

export interface SubmitJobRequest {
  request: EncodingRequest
}

export interface SubmitJobResponse {
  success: boolean
  job_ids: string[]
  message: string
}

// API Response types
export interface JobListResponse {
  jobs: JobInfo[]
  total: number
}

export interface WatchfoldersResponse {
  watchfolders: WatchFolderInfo[]
  total: number
}

export interface ProfilesResponse {
  profiles: ProfileInfo[]
  total: number
}

export interface ActionResponse {
  success: boolean
  message: string
}

// Configuration types - matches GET /api/config response
export interface TranscodrConfig {
  ffmpeg: {
    binary_path: string
    hardware_accel: string
  }
  daemon: {
    host: string
    port: number
    max_concurrent_jobs: number
    pid_file: string | null
  }
  storage: {
    temp_dir: string
    backup_originals: boolean
    backup_dir: string
    min_free_space_gb: number
    root_media: string
    profile_name_separator: string
    on_extension_mismatch: string
    enable_temp_copy: boolean
  }
  logging: {
    level: string
    dir: string | null
    rotation: string
    per_job_logs: boolean
  }
  validation: {
    duration_tolerance: number
  }
  notifications: {
    enabled: boolean
    on_job_complete: boolean
    on_batch_complete: boolean
    on_queue_empty: boolean
    on_error: boolean
    desktop: {
      enabled: boolean
    }
    email: {
      enabled: boolean
      smtp_server: string
      smtp_port: number
      use_tls: boolean
      smtp_user: string
      smtp_password: string
      from_address: string
      recipients: string[]
    }
    apprise: {
      enabled: boolean
      urls: string[]
    }
  }
}

export interface ConfigUpdateResponse {
  success: boolean
  message: string
  warnings: string[]
}

export interface ReloadResponse {
  success: boolean
  message: string
}
