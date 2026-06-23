from pathlib import Path

from onlybtc.core.paths import PathResolver


def test_path_resolver_uses_project_root_and_data_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    data_root = tmp_path / "data-root"
    resolver = PathResolver(project_root=project_root, data_root=data_root)

    assert resolver.sqlite_db_path == data_root / "onlybtc.sqlite3"
    assert resolver.logs_dir == project_root / "logs"
    assert resolver.static_assets_dir == project_root / "static-assets"


def test_path_resolver_creates_directories(tmp_path: Path) -> None:
    resolver = PathResolver(project_root=tmp_path, data_root=tmp_path / "data")

    resolver.ensure_directories()

    assert resolver.data_root.exists()
    assert resolver.logs_dir.exists()
    assert resolver.playwright_artifacts_dir.exists()
