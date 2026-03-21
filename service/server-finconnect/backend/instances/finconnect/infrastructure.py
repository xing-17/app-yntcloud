from __future__ import annotations

import os
import json
import subprocess
from pathlib import Path
import yaml


from pulumi import ComponentResource, ResourceOptions
from pulumi.output import Output
from pulumi_alicloud import ecs
from pulumi_alicloud import oos
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream


class FinConnectInfra(ComponentResource):
    def __init__(
        self,
        name: str,
        overlay: Overlay,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
        vpc_id: Output[str] | None = None,
        vswitch_id: Output[str] | None = None,
        security_group_id: Output[str] | None = None,
        secret: dict | None = None,
    ):
        super().__init__(
            "custom:alicloud:FinConnectInfra",
            name,
            None,
            opts,
        )
        self.overlay = overlay
        self.logstream = logstream
        
        # ==================== ECS Instance ====================
        
        # ------------------------------------------------------
        # Get service namespace 
        ns = overlay.get_namespace()
        instance_ns = ns.get(f"service.instance.app-finconnect")
        
        # Get instance properties
        self.instance_id = instance_ns.get("instance_id")
        self.instance_type = instance_ns.get("instance_type")
        instance_name = instance_ns.get("instance_name")
        resource_name = f"{instance_name}"
        
        # load existing instance information
        instance_lookup_result: ecs.GetInstancesResult = ecs.get_instances(
            ids=[self.instance_id],
        )
        instances: list[ecs.GetInstancesResult] = instance_lookup_result.instances
        if len(instances) == 0:
            self.loaded_instance = None
            logstream.log(
                level="ERROR",
                message=f"ECS instance not found: {self.instance_id}",
            )
        else:
            self.loaded_instance: ecs.GetInstancesResult = instances[0]
            logstream.log(
                level="INFO",
                message=f"ECS instance loaded OK: {self.instance_id}",
            )
        
        # ------------------------------------------------------
        # Build ECS instance 
        password = secret["instance_password"]
        self.instance = ecs.Instance(
            resource_name=resource_name,
            instance_name=instance_name,
            instance_type=self.instance_type,
            security_groups=[security_group_id],
            vpc_id=vpc_id,
            vswitch_id=vswitch_id,
            image_id=self.loaded_instance.image_id,
            password=password,
            tags=ns.get("tags").to_dict(),
            opts=ResourceOptions(
                parent=self,
                import_=self.instance_id, # 导入现有instance
            ),
        )
        logstream.log(
            level="INFO",
            message=f"ECS instance created OK.",
        )