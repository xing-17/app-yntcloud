#!/usr/bin/env python
from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional


class PackageInstall:
    def __init__(
        self,
        root: Path,
        package: Optional[str] = None,
        strategy: Optional[str] = "auto",
    ) -> None:
        self.root = root
        self.package_root = self.root / "package"
        self.packages = self._resolve_packages(package)
        self.strategy = self._resolve_strategy(strategy)

    def _resolve_packages(
        self,
        package: Optional[str] = None,
    ) -> List[str]:
        packages = []
        if package:
            packages.append(package)
        else:
            for item in self.package_root.iterdir():
                if item.is_dir() and (item / "package.toml").exists():
                    packages.append(item.name)
        return packages

    def _resolve_strategy(
        self,
        strategy: Optional[str] = "auto",
    ) -> str:
        if not strategy:
            strategy = "auto"
        else:
            strategy = strategy.lower()
        return strategy

    # ----------------- individual -----------------
    def load_metadata(
        self,
        path: Path,
    ) -> dict:
        metafile = path / "package.toml"
        if not metafile.exists():
            raise FileNotFoundError(f"package.toml not found at: {metafile}")
        with metafile.open("rb") as f:
            raw = tomllib.load(f)
            metadata = raw.get("package", {}) or {}
            return metadata

    def get_name(self, package: str, metadata: Dict[str, Any]) -> str | None:
        name = metadata.get("name")
        if not name:
            raise ValueError(f"[install:{package}] name not found in metadata")
        print(f"[install:{package}] package name = {name}")
        return name

    def get_version(self, package: str, metadata: Dict[str, Any]) -> str | None:
        version = metadata.get("version", "latest")
        print(f"[install:{package}] package version = {version}")
        return version

    def get_where(self, package: str, metadata: Dict[str, Any]) -> Path | None:
        where = metadata.get("where")
        if not where:
            return None
        path = (
            (self.package_root / package / where).resolve()
            if not where.startswith("/")
            else Path(where)
        )
        if path.exists() and path.is_dir():
            return path
        print(f"[install:{package}] source path not found: {where}")
        return None

    def get_editable(self, package: str, metadata: Dict[str, Any]) -> bool | None:
        editable = metadata.get("editable", False)
        print(f"[install:{package}] package editable = {editable}")
        return bool(editable)

    def uninstall(self, package: str, metadata: Dict[str, Any]) -> None:
        name = self.get_name(package, metadata)
        if not name:
            return
        cmd = [sys.executable, "-m", "pip", "uninstall", "-y", name]
        print(f"[install:{package}][uninstall]", " ".join(cmd))
        subprocess.run(cmd, check=False)

    def local_install(self, package: str, metadata: Dict[str, Any]) -> None:
        where = self.get_where(package, metadata)
        editable = self.get_editable(package, metadata)
        if where is None:
            raise ValueError(f"[install:{package}] {where} is not valid")
        cmd = [sys.executable, "-m", "pip", "install"]
        if editable:
            cmd.append("-e")
        cmd.append(str(where))
        print(f"[install:{package}][local]", " ".join(cmd))
        subprocess.check_call(cmd)

    def remote_install(self, package: str, metadata: Dict[str, Any]) -> None:
        name = self.get_name(package, metadata)
        version = self.get_version(package, metadata)
        if not version or version == "latest":
            spec = name
        else:
            spec = f"{name}=={version}"
        cmd = [sys.executable, "-m", "pip", "install", spec]
        print(f"[install:{package}][remote]", " ".join(cmd))
        subprocess.check_call(cmd)

    # ----------------- entry -----------------
    def run(self) -> None:
        for package in self.packages:
            path = (self.package_root / package).resolve()
            metadata = self.load_metadata(path)
            print(f"[install:{package}] loaded metadata for {package}")

            where = self.get_where(package, metadata)
            if self.strategy == "auto":
                if where is not None:
                    strategy = "local"
                else:
                    strategy = "remote"
            else:
                strategy = self.strategy
            print(f"[install:{package}] strategy = {strategy}")

            self.uninstall(package, metadata)
            if strategy == "local":
                self.local_install(package, metadata)
            else:
                self.remote_install(package, metadata)


def main(argv: list[str] | None = None) -> int:
    entrance = argparse.ArgumentParser(
        description="Install x17 lib package (local / remote / auto).",
    )
    entrance.add_argument(
        "--package",
        "-p",
        required=False,
        default=None,
        help="package directory name under ./package, e.g. 'lib-x17-cloudmeta'",
    )
    entrance.add_argument(
        "--strategy",
        "-s",
        required=False,
        choices=["auto", "local", "remote"],
        default="auto",
        help="install strategy: local / remote / auto (default: auto)",
    )
    args = entrance.parse_args(argv)
    installer = PackageInstall(
        root=Path(__file__).resolve().parent,
        package=getattr(args, "package", None),
        strategy=getattr(args, "strategy", "auto"),
    )
    installer.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
