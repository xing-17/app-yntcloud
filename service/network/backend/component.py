from __future__ import annotations

from pulumi import ComponentResource, ResourceOptions
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream

from backend.networking.infrastructure import NetworkInfrastructure


class Backend(ComponentResource):
    """
    网络基础设施后端组件
    
    管理以下资源：
    - VPC 网络基础设施（VPC、VSwitch、Security Group）
    """

    def __init__(
        self,
        name: str,
        overlay: Overlay,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
    ):
        super().__init__(
            "custom:alicloud:Backend",
            name,
            None,
            opts,
        )
        self.overlay = overlay
        self.logstream = logstream
        logstream.log(
            message="Initializing network backend",
            level="INFO",
        )

        # 创建网络基础设施
        self.network = NetworkInfrastructure(
            name="network",
            overlay=overlay,
            logstream=logstream,
            opts=ResourceOptions(parent=self),
        )
        logstream.log(
            message="Network backend initialization complete",
            level="INFO",
        )

        # 注册所有输出
        self.register_outputs_bookmark = self.network.register_outputs_bookmark.copy()
        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(
            message="Backend outputs registered",
            level="INFO",
        )
