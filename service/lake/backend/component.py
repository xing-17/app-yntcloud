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
        logstream.log(message="Initializing storage backend")

        # Create OSS storage infrastructure
        self.storage = OssStorage(
            name="storage",
            overlay=overlay,
            logstream=logstream,
            opts=ResourceOptions(parent=self),
        )
        logstream.log(
            message="Storage backend initialization complete",
            level="INFO",
        )

        # Register all outputs once
        self.register_outputs_bookmark = {
            "oss/bucket/infralake/name": self.storage.infralake.bucket,
            "oss/bucket/infralake/id": self.storage.infralake.id,
            "oss/bucket/datalake/name": self.storage.datalake.bucket,
            "oss/bucket/datalake/id": self.storage.datalake.id,
        }
        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(
            message="Backend outputs registered",
            level="INFO",
            context=self.register_outputs_bookmark,
        )
