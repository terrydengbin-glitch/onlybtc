from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathResolver:
    """Resolve all local paths from a movable project root and data root."""

    project_root: Path
    data_root: Path

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> PathResolver:
        resolved_project_root = (
            Path(os.environ["ONLYBTC_HOME"])
            if os.environ.get("ONLYBTC_HOME")
            else project_root or Path(__file__).resolve().parents[4]
        ).resolve()

        resolved_data_root = (
            Path(os.environ["ONLYBTC_DATA_DIR"])
            if os.environ.get("ONLYBTC_DATA_DIR")
            else resolved_project_root / "data"
        ).resolve()

        return cls(project_root=resolved_project_root, data_root=resolved_data_root)

    @property
    def app_root(self) -> Path:
        return self.project_root / "backend" / "src" / "onlybtc"

    @property
    def config_dir(self) -> Path:
        return self.project_root / "configs"

    @property
    def sqlite_db_path(self) -> Path:
        return self.data_root / "onlybtc.sqlite3"

    @property
    def cache_dir(self) -> Path:
        return self.project_root / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.project_root / "logs"

    @property
    def exports_dir(self) -> Path:
        return self.project_root / "exports"

    @property
    def screenshots_dir(self) -> Path:
        return self.project_root / "screenshots"

    @property
    def playwright_artifacts_dir(self) -> Path:
        return self.project_root / "playwright-artifacts"

    @property
    def seed_data_dir(self) -> Path:
        return self.project_root / "seed-data"

    @property
    def ui_references_dir(self) -> Path:
        return self.project_root / "ui-references"

    @property
    def static_assets_dir(self) -> Path:
        return self.project_root / "static-assets"

    @property
    def backup_dir(self) -> Path:
        return self.project_root / "backups"

    def as_dict(self) -> dict[str, str]:
        return {
            "project_root": str(self.project_root),
            "app_root": str(self.app_root),
            "config_dir": str(self.config_dir),
            "data_dir": str(self.data_root),
            "sqlite_db_path": str(self.sqlite_db_path),
            "cache_dir": str(self.cache_dir),
            "logs_dir": str(self.logs_dir),
            "exports_dir": str(self.exports_dir),
            "screenshots_dir": str(self.screenshots_dir),
            "playwright_artifacts_dir": str(self.playwright_artifacts_dir),
            "seed_data_dir": str(self.seed_data_dir),
            "ui_references_dir": str(self.ui_references_dir),
            "static_assets_dir": str(self.static_assets_dir),
            "backup_dir": str(self.backup_dir),
        }

    def ensure_directories(self) -> None:
        for path in (
            self.config_dir,
            self.data_root,
            self.cache_dir,
            self.logs_dir,
            self.exports_dir,
            self.screenshots_dir,
            self.playwright_artifacts_dir,
            self.seed_data_dir,
            self.static_assets_dir,
            self.backup_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


paths = PathResolver.from_env()
