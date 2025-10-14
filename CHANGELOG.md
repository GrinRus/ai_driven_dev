# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

## [Unreleased]

### Added
- Payload manifest (`manifest.json`) with per-file checksums enforced at runtime.
- `claude-workflow sync/upgrade --release` for fetching payloads from GitHub Releases with caching and bundled fallback.
- Release packaging script (`scripts/package_payload_archive.py`) that produces versioned payload zip, manifest copy and checksum files for publication.

## [0.1.0] - 2025-02-XX

### Added
- Initial release of `claude-workflow-cli` packaging and installation instructions.
