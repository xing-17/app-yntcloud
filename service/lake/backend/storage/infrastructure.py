from __future__ import annotations

import pulumi_alicloud as alicloud
from pulumi import ComponentResource, ResourceOptions
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream


class OssStorage(ComponentResource):
    def __init__(
        self,
        name: str,
        overlay: Overlay,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
    ):
        super().__init__(
            "custom:alicloud:OssStorage",
            name,
            None,
            opts,
        )
        self.overlay = overlay
        self.logstream = logstream

        # Initialize buckets dictionary
        self.buckets = {}

        ns = overlay.get_namespace()
        bucket_ns = ns.get("environ.resources.oss.bucket")

        # Creating infralake bucket
        infralake_ns = bucket_ns.get("infralake")
        infralake_name = infralake_ns.get("name")
        self.infralake = alicloud.oss.Bucket(
            resource_name=infralake_name,
            bucket=infralake_name,
            storage_class="Standard",
            tags=infralake_ns.get("tags").to_dict(),
            opts=ResourceOptions(parent=self),
        )
        self.buckets["infralake"] = self.infralake
        logstream.log(
            message=f"OSS infralake bucket created: {infralake_name}",
            level="INFO",
        )

        # Creating datalake bucket
        datalake_ns = bucket_ns.get("datalake")
        datalake_name = datalake_ns.get("name")
        self.datalake = alicloud.oss.Bucket(
            resource_name=datalake_name,
            bucket=datalake_name,
            storage_class="Standard",
            tags=datalake_ns.get("tags").to_dict(),
            opts=ResourceOptions(parent=self),
        )
        self.buckets["datalake"] = self.datalake
        logstream.log(
            message=f"OSS datalake bucket created: {datalake_name}",
            level="INFO",
        )
