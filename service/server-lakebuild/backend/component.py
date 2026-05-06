from __future__ import annotations

from pulumi import ComponentResource, ResourceOptions
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream

from backend.core.infrastructure import CoreFCInfra
from backend.server.infrastructure import ECSInfra


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

        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(
            message="Backend outputs registered",
            context={
                "outputs": list(self.register_outputs_bookmark.keys()),
                "count": len(self.register_outputs_bookmark),
            },
        )
