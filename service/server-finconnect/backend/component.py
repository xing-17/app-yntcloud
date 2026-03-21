from __future__ import annotations

from pulumi import ComponentResource, ResourceOptions
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream

from backend.instances.infrastructure import InstancesInfra


class Backend(ComponentResource):
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
        logstream.log(level="INFO", message="Initializing backend component")
        
        self.instances = InstancesInfra(
            name="instances",
            overlay=overlay,
            logstream=logstream,
            opts=ResourceOptions(parent=self),
        )
        logstream.log(
            message="Server backend initialization complete",
            level="INFO",
        )
        
        # 注册所有输出
        self.register_outputs_bookmark = self.instances.register_outputs_bookmark.copy()
        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(
            message="Backend outputs registered",
            level="INFO",
        )


    