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

// Watch folder info - matches actual API response
export interface WatchFolderInfo {
  id: string
  path: string
  type: 'command' | 'media'
  source: 'config'
  active: boolean
  paused: boolean
  scan_interval: number
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
  destination?: string | null
  [key: string]: unknown
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
  }
  storage: {
    temp_dir: string
    backup_originals: boolean
    backup_dir: string
    min_free_space_gb: number
    root_media: string
    profile_name_separator: string
    on_extension_mismatch: string
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
