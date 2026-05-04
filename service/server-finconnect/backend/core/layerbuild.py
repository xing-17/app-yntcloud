from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from pulumi import (
    ComponentResource,
    CustomTimeouts,
    ResourceOptions,
)
from pulumi_alicloud.fc import V3LayerVersion, V3LayerVersionCodeArgs
from pulumi_alicloud.oss import BucketObject
from xlog.stream.stream import LogStream


class LayerBuildInfra(ComponentResource):
    def __init__(
        self,
        name: str,
        description: str,
        runtime: str,
        python_version: str,
        requirements: list,
        timeout_minutes: int,
        oss_bucket: str,
        oss_prefix: str,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
    ):
        super().__init__(
            f"custom:alicloud:fc:layer:{name}",
            name,
            None,
            opts,
        )
        self.logstream = logstream
        self.timeout_minutes = timeout_minutes or 5
        self.runtime = runtime or "python3.12"
        self.python_version = python_version or self.runtime.replace("python", "")
        # self._image = f"python:{self.python_version}-slim"
        self._image = f"python:{self.python_version}-slim-bullseye"
        self.description = description or f"FC layer {name}"

        # Validate requirements
        if not requirements:
            raise ValueError(f"FC Layer '{name}' must have requirements.")

        self.reqs: list = requirements
        reqs_str = "\n".join(sorted(self.reqs))
        reqs_hash = hashlib.md5(reqs_str.encode("utf-8")).hexdigest()[:8]

        if shutil.which("docker") is None:
            raise RuntimeError("Docker is required to build FC layer dependencies.")

        # Prepare build directory as ./build/layers/{name}/
        self.build_dir = Path(__file__).parent / "layers" / name
        self.build_dir.mkdir(parents=True, exist_ok=True)

        # Define zip path as ./build/layers/{hash}.zip
        self.file_name = f"{name}-{reqs_hash}.zip"
        self.zip_path = self.build_dir / self.file_name
        self.zip_size = 0
        self.upload_bucket = oss_bucket
        self.upload_prefix = f"{oss_prefix}/{name}/{self.file_name}"

        # Build layer zip if not exists, else reuse existing zip
        if not self.zip_path.exists():
            with tempfile.TemporaryDirectory() as tmp_dir:
                deps_dir = Path(tmp_dir) / "python"
                deps_dir.mkdir()
                reqs_file = Path(tmp_dir) / "requirements.txt"
                reqs_file.write_text("\n".join(self.reqs))

                # Install dependencies using Docker (Linux environment)
                cmd = [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "-v",
                    f"{reqs_file.absolute()}:/tmp/requirements.txt:ro",
                    "-v",
                    f"{deps_dir.absolute()}:/tmp/output",
                    self._image,
                    "pip",
                    "install",
                    "-r",
                    "/tmp/requirements.txt",
                    "-t",
                    "/tmp/output",
                    "--no-compile",
                    "--no-cache-dir",
                    "--quiet",
                ]
                try:
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(
                        f"Docker build failed\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}"
                    ) from e

                # Create zip file for the layer
                with zipfile.ZipFile(
                    self.zip_path,
                    "w",
                    zipfile.ZIP_DEFLATED,
                ) as zf:
                    for f in deps_dir.rglob("*"):
                        if f.is_file():
                            zf.write(f, arcname=f.relative_to(tmp_dir))

                self.size_mb = self.zip_path.stat().st_size / 1024 / 1024
                self.logstream.log(message=f"Layer '{name}' build OK, size: {self.size_mb:.2f} MB")
        else:
            self.size_mb = self.zip_path.stat().st_size / 1024 / 1024
            self.logstream.log(message=f"Layer '{name}' already built, size: {self.size_mb:.2f} MB")

        # Upload zip to OSS (if not exists)
        self.object_upload = BucketObject(
            resource_name=f"{name}-zip",
            bucket=self.upload_bucket,
            key=self.upload_prefix,
            source=str(self.zip_path),
            opts=ResourceOptions(
                parent=self,
                custom_timeouts=CustomTimeouts(
                    create=f"{self.timeout_minutes}m",
                    update=f"{self.timeout_minutes}m",
                    delete=f"{self.timeout_minutes}m",
                ),
            ),
        )

        # Build FC Layer using the uploaded zip
        self.layer = V3LayerVersion(
            resource_name=name,
            layer_name=name,
            description=description,
            compatible_runtimes=[runtime],
            code=V3LayerVersionCodeArgs(
                oss_bucket_name=self.upload_bucket,
                oss_object_name=self.upload_prefix,
            ),
            opts=ResourceOptions(
                parent=self,
                custom_timeouts=CustomTimeouts(
                    create=f"{self.timeout_minutes}m",
                    update=f"{self.timeout_minutes}m",
                    delete=f"{self.timeout_minutes}m",
                ),
                depends_on=[self.object_upload],
                ignore_changes=["public", "acl"],
            ),
        )
        self.size_mb = Path(self.zip_path).stat().st_size / 1024 / 1024
        self.register_outputs_bookmark = {
            f"oss/layer/{name}/bucket": self.upload_bucket,
            f"oss/layer/{name}/key": self.upload_prefix,
            f"fc/layer/{name}/arn": self.layer.layer_version_arn,
            f"fc/layer/{name}/name": self.layer.layer_name,
            f"fc/layer/{name}/version": self.layer.version,
        }
        self.register_outputs(self.register_outputs_bookmark)
