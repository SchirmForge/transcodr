<p align="center">
  <img src="./docs/assets/transcodr-alpha.png" alt="Transcodr"/>
</p>

# Transcodr

Transcodr is a local-first video transcoding system built for reliable batch processing. It runs a daemon with a clean REST API, and a fast Web UI that uses the same API for job control, profiles, and system status.

## Key Features

- Daemon + REST API core
- Web UI powered by the API
- Profile-driven encoding (single or multi-profile)
- Hardware acceleration: VAAPI (AMD/Intel), NVENC, QSV
- Watchfolders for automated ingest
- Safe replace or destination outputs
- SQLite-backed queue that survives restarts
- Multi-daemon orchestration (planned, not yet implemented)

## Get Started

- Quick install: docs/configuration.md#prerequisites
- Full install and configuration: docs/configuration.md
- Development setup: local-docs/readme-dev.md

## Learn More

- Profiles guide: docs/profiles.md
- Watchfolders guide: docs/watchfolders.md
- Architecture: docs/architecture.md
- API reference: docs/api-reference.md
- CLI reference: docs/cli-reference.md
- Performance tuning: docs/concurrency-tuning.md
- Roadmap: docs/roadmap.md
- Current dev status: local-docs/version0.4.md

## License

TBD
