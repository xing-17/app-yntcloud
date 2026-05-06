from __future__ import annotations

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
from pulumi_alicloud import ram
from pulumi_alicloud.fc import (
    V3Function,
    V3FunctionArgs,
    V3FunctionCodeArgs,
)
from pulumi_alicloud.oss import BucketObject
from xlog import LogStream

# t = "acs:fc:cn-hangzhou:official:layers/Python312-Aliyun-SDK/versions/1"


class CoreBuildInfra(ComponentResource):
    """
    函数计算基础设施组件:

    管理以下资源：
    - alicloud.fc3.Function: 从本地代码构建并部署函数计算函数

    """

    default_runtime = "python3.12"
    default_handler = "handler.main"
    default_memory = 512
    default_timeout = 900  # 15 minutes
    default_includes = ["**/*"]  # ✅ 改为打包所有文件
    default_excludes = [
        "__pycache__/*",
        "**/__pycache__/*",
        "*.pyc",
        "*.pyo",
        "*.dist-info/*",
        "*.egg-info/*",
        "**/*.dist-info",
        "**/*.egg-info",
        "**/tests",  # ← 测试文件
        "**/test",
        "**/*.so.dSYM",  # ← 调试符号
        "**/examples",  # ← 示例代码
        "**/*.md",  # ← 文档
        "**/*.txt",  # ← 除了必要的配置文件
        "**/LICENSE*",
        "**/NOTICE*",
    ]

    def __init__(
        self,
        name: str,
        source: Path,
        oss_bucket: str,
        oss_prefix: str,
        role: ram.Role,
        logstream: LogStream,
        # Optional parameters with defaults
        runtime: str = None,
        python_version: str = None,
        memory: int = 256,
        handler: str = "handler.main",
        timeout: int = 900,
        description: str = None,
        includes: list[str] = None,
        excludes: list[str] = None,
        env_vars: dict[str, str] = None,
        internet_access: bool = False,
        layers: list[str] = None,
        layers_arn_registry: dict[str, str] = None,
        timeout_minutes: int = 5,
        opts: ResourceOptions | None = None,
        **kwargs,
    ):
        super().__init__(
            f"custom:alicloud:fc:{name}",
            name,
            None,
            opts,
        )
        self.name = name
        self.source = source
        self.oss_bucket = oss_bucket
        self.oss_prefix = oss_prefix
        self.runtime = runtime or self.default_runtime
        self.python_version = python_version or self.runtime.replace("python", "")
        self.handler = handler or self.default_handler
        self.memory = int(memory or self.default_memory)
        self.timeout = int(timeout or self.default_timeout)
        self.description = description or f"{name} function"
        self.includes = includes or self.default_includes
        self.excludes = excludes or self.default_excludes
        self.env_vars = env_vars or {}
        self.internet_access = internet_access or False
        self.timeout_minutes = timeout_minutes or 5

        # layers = layers or []
        self.layers_arn_registry = layers_arn_registry or {}
        self.layers = self._resolve_layers(layers)

        if not source.exists() or not source.is_dir():
            raise ValueError(f"FC function at '{source}' does not exist.")

        if shutil.which("docker") is None:
            raise RuntimeError("Docker is required to build FC function.")

        # Prepare requirements file path
        self.reqs_file = source / "requirements.txt"
        self.reqs_file_exists = self.reqs_file.exists()
        # self._image = f"python:{self.python_version}-slim"
        self._image = f"python:{self.python_version}-slim-bullseye"

        # Prepare build directory
        self.artifact_dir = Path(__file__).parent / "artifacts"
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.zip_dir = self.artifact_dir / f"{self.name}.zip"
        self.zip_dir.unlink(missing_ok=True)

        # ------------------------------------------------------
        # Build function code package
        # ------------------------------------------------------
        with tempfile.TemporaryDirectory() as build_dir:
            # install dependencies if requirements.txt exists
            if self.reqs_file_exists:
                cmd = [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "-v",
                    f"{self.reqs_file.absolute()}:/tmp/requirements.txt:ro",
                    "-v",
                    f"{build_dir}:/tmp/output",
                    self._image,
                    "pip",
                    "install",
                    "-r",
                    "/tmp/requirements.txt",
                    "-t",
                    "/tmp/output",
                    "--no-compile",
                    "--no-cache-dir",
                ]
                try:
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    cmd = " ".join(cmd)
                    raise RuntimeError(f"Docker build failed. Command: {cmd}") from e

            # Copy source code to build directory
            candidates: set[Path] = set()
            for pattern in self.includes:
                candidates.update(source.glob(pattern))
            excluded: set[Path] = set()
            for pattern in self.excludes:
                excluded.update(source.glob(pattern))
            files = sorted(f for f in candidates if f.is_file() and f not in excluded)
            for f in files:
                dest = Path(build_dir) / f.relative_to(source)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)

            # Create zip file for the function code
            with zipfile.ZipFile(
                self.zip_dir,
                "w",
                zipfile.ZIP_DEFLATED,
            ) as zf:
                for f in Path(build_dir).rglob("*"):
                    if f.is_file():
                        zf.write(f, arcname=f.relative_to(build_dir))

            logstream.log(message=f"Function code for '{name}' built OK")

        # ------------------------------------------------------
        # Upload FC Function zip on OSS
        # ------------------------------------------------------
        upload_bucket = self.oss_bucket
        upload_prefix = f"{self.oss_prefix}/{self.name}/{self.zip_dir.name}"
        self.object_upload = BucketObject(
            resource_name=f"{self.name}-zip",
            bucket=upload_bucket,
            key=upload_prefix,
            source=str(self.zip_dir),
            opts=ResourceOptions(
                parent=self,
                custom_timeouts=CustomTimeouts(
                    create=f"{self.timeout_minutes}m",
                    update=f"{self.timeout_minutes}m",
                    delete=f"{self.timeout_minutes}m",
                ),
            ),
        )

        # ------------------------------------------------------------------
        # FC Function
        # ------------------------------------------------------------------
        self.function = V3Function(
            resource_name=name,
            args=V3FunctionArgs(
                function_name=name,
                role=role.arn,
                description=description,
                runtime=runtime,
                handler=handler,
                memory_size=memory,
                timeout=timeout,
                layers=self.layers,
                code=V3FunctionCodeArgs(
                    oss_bucket_name=upload_bucket,
                    oss_object_name=upload_prefix,
                ),
                environment_variables=env_vars,
                **kwargs,
            ),
            opts=ResourceOptions(
                parent=self,
                depends_on=[self.object_upload],
            ),
        )

        self.register_outputs_bookmark = {
            f"fc/function/{name}/name": self.function.function_name,
            f"fc/function/{name}/arn": self.function.function_arn,
        }
        self.register_outputs(self.register_outputs_bookmark)

    def _resolve_layers(
        self,
        layers: list[str],
    ) -> list[str]:
        result = []
        if not layers:
            return result
        for layer in layers:
            if layer in self.layers_arn_registry:
                resolved = self.layers_arn_registry[layer]
                result.append(resolved)
            elif layer.startswith("acs:fc:"):
                result.append(layer)
            else:
                raise ValueError(f"Layer reference '{layer}' is not valid.")
        return result
