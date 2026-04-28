from __future__ import annotations

from pulumi import ComponentResource, ResourceOptions
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream

from backend.storage.infrastructure import OssStorage


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
        logstream.log(message="Initializing backend component")

        # Create OSS storage infrastructure
        self.storage = OssStorage(
            name="storage",
            overlay=overlay,
            logstream=logstream,
            opts=ResourceOptions(parent=self),
        )
        logstream.log(message="Storage backend initialization OK")

        # Register all outputs once
        self.register_outputs_bookmark = {
            **self.storage.register_outputs_bookmark,
        }
        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(
            message="Backend outputs registered",
            context={
                "outputs": list(self.register_outputs_bookmark.keys()),
                "count": len(self.register_outputs_bookmark),
            },
        )
