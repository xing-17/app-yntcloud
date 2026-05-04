from __future__ import annotations

from pulumi import ComponentResource, ResourceOptions
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream

from backend.core.infrastructure import CoreFCInfra
from backend.schedule.infrastructure import ScheduleInfra
from backend.server.infrastructure import ECSInfra


class Backend(ComponentResource):
    """
    finconnect服务器基础设施后端组件

    管理以下资源：
    - ECS Instance: 新建按量付费实例（ecs.u1-c1m2.3xlarge）
    - 函数计算基础设施（finconnect-remote-run）

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
        self.register_outputs_bookmark = {}
        logstream.log(message="Initializing backend component")

        self.ecsinfra = ECSInfra(
            name="instances",
            overlay=overlay,
            logstream=logstream,
            opts=ResourceOptions(parent=self),
        )
        self.register_outputs_bookmark.update(self.ecsinfra.register_outputs_bookmark)
        logstream.log(message="ECS backend initialization OK")

        self.core = CoreFCInfra(
            name="corefc",
            overlay=overlay,
            logstream=logstream,
            opts=ResourceOptions(parent=self),
        )
        self.register_outputs_bookmark.update(self.core.register_outputs_bookmark)
        logstream.log(message="Core backend initialization complete")

        self.schedule = ScheduleInfra(
            name="schedule",
            overlay=overlay,
            logstream=logstream,
            opts=ResourceOptions(
                parent=self,
                depends_on=[
                    self.core,
                    self.ecsinfra,
                ],
            ),
        )
        self.register_outputs_bookmark.update(self.schedule.register_outputs_bookmark)
        logstream.log(message="Schedule backend initialization complete")

        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(
            message="Backend outputs registered",
            context={
                "outputs": list(self.register_outputs_bookmark.keys()),
                "count": len(self.register_outputs_bookmark),
            },
        )
