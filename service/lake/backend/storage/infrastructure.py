from __future__ import annotations

from pulumi import ComponentResource, ResourceOptions
from pulumi_alicloud import oss
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream


class OssStorage(ComponentResource):
    """
    阿里云 OSS 存储基础设施组件

    管理以下资源：
    - infralake bucket: 存储湖仓基础设施相关数据（如日志、监控等）
    - datalake bucket: 存储湖仓业务数据（如原始数据、处理后数据等）

    架构说明：
    - 两个独立的 bucket，职责分离

    """

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
        self.infralake = oss.Bucket(
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
        self.datalake = oss.Bucket(
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

        # Register outputs
        self.register_outputs_bookmark = {
            "oss/bucket/infralake/name": self.infralake.bucket,
            "oss/bucket/infralake/id": self.infralake.id,
            "oss/bucket/datalake/name": self.datalake.bucket,
            "oss/bucket/datalake/id": self.datalake.id,
        }
        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(
            message="OSS storage outputs registered",
            level="INFO",
            context={
                "outputs": list(self.register_outputs_bookmark.keys()),
                "count": len(self.register_outputs_bookmark),
            },
        )
