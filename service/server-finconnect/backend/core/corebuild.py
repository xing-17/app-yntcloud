from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

from pulumi import ComponentResource, ResourceOptions
from pulumi_alicloud import ram
from pulumi_alicloud.fc import (
    V3Function,
    V3FunctionArgs,
    V3FunctionCodeArgs,
)
from xcloudmeta.centre import Namespace


class CoreBuildInfra(ComponentResource):
    """
    函数计算基础设施组件:

    管理以下资源：
    - alicloud.fc3.Function: 从本地代码构建并部署函数计算函数

    """

    default_runtime = "python3.10"
    default_handler = "handler.main"
    default_memory_size = 512
    default_timeout = 900  # 15 minutes
    default_includes = ["**/*"]  # ✅ 改为打包所有文件
    default_excludes = [
        "__pycache__/*",
        "**/__pycache__/*",
        "*.pyc",
        "*.pyo",
        "*.dist-info/*",
        "*.egg-info/*",
    ]

    def __init__(
        self,
        function_name: str,
        source: Path,
        role: ram.Role,
        ns: Namespace,
        opts: ResourceOptions | None = None,
        **kwargs,
    ):
        super().__init__(
            f"custom:alicloud:fc:{function_name}",
            function_name,
            None,
            opts,
        )
        runtime = ns.get("runtime", self.default_runtime)
        handler = ns.get("handler", self.default_handler)
        memory_size = int(ns.get("memory_size", self.default_memory_size))
        timeout = int(ns.get("timeout", self.default_timeout))
        description = ns.get("description", f"{function_name} function")
        includes = ns.get("includes", self.default_includes)
        excludes = ns.get("excludes", self.default_excludes)
        env_vars_ns: dict = ns.get("env_vars", Namespace())
        env_vars = env_vars_ns.to_dict()

        # ------------------------------------------------------
        # Build zip file from source code
        # ------------------------------------------------------
        candidates: set[Path] = set()
        for pattern in includes:
            candidates.update(source.glob(pattern))

        excluded: set[Path] = set()
        for pattern in excludes:
            excluded.update(source.glob(pattern))

        files = sorted(f for f in candidates if f.is_file() and f not in excluded)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(f, arcname=f.relative_to(source))
        zip_file = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # ------------------------------------------------------------------
        # FC Function
        # ------------------------------------------------------------------
        self.function = V3Function(
            resource_name=function_name,
            args=V3FunctionArgs(
                function_name=function_name,
                role=role.arn,
                description=description,
                runtime=runtime,
                handler=handler,
                memory_size=memory_size,
                timeout=timeout,
                code=V3FunctionCodeArgs(zip_file=zip_file),
                environment_variables=env_vars,
                **kwargs,
            ),
            opts=ResourceOptions(parent=self),
        )

        self.register_outputs_bookmark = {
            f"fc/function/{function_name}/name": self.function.function_name,
            f"fc/function/{function_name}/arn": self.function.function_arn,
        }
        self.register_outputs(self.register_outputs_bookmark)
