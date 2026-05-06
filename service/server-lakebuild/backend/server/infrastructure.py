from __future__ import annotations

import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_alicloud import ecs
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream


class ECSInfra(ComponentResource):
    """
    LakeBuild ECS实例基础设施

    创建按量付费ECS实例：
    - 规格：ecs.u1-c1m2.3xlarge（通用算力型u1，12vCPU 24GiB）
    - 可用区：cn-shanghai-2
    - 系统盘：ESSD（大小可通过service.toml调整）
    - 镜像：Alibaba Cloud Linux（最新稳定版）
    - 公网IP：自动分配
    - 登录方式：SSH密钥对
    """

    def __init__(
        self,
        name: str,
        overlay: Overlay,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
    ):
        super().__init__(
            "custom:alicloud:LakeBuildInfra",
            name,
            None,
            opts,
        )
        self.overlay = overlay
        self.logstream = logstream

        # Get service namespace
        ns = overlay.get_namespace()
        service_ns = ns.get("service")

        # ------------------------------------------------------
        # Reference network stack
        # - GET: vpc_id
        # - GET: vswitch_id
        # - GET: security_group_id
        # ------------------------------------------------------
        stack_ref_ns = service_ns.get("reference.stack")
        stack_network_ref_ns = stack_ref_ns.get("network")
        stack_network_name = stack_network_ref_ns.get("name")
        stack_network = pulumi.StackReference(
            "stackref-network",
            stack_name=stack_network_name,
            opts=ResourceOptions(parent=self),
        )
        vpc_id: pulumi.Output[str] = stack_network.get_output("vpc/id")
        vswitch_id: pulumi.Output[str] = stack_network.get_output("vswitch/id")
        security_group_id: pulumi.Output[str] = stack_network.get_output("security_group/id")
        logstream.log(message="Network Attributes resolved OK")

        # ------------------------------------------------------
        # Retrive existing OOS secret
        # ------------------------------------------------------
        # Get instance properties from namespace (service.toml)
        instance_ns = service_ns.get("ecs.instance.app-lakebuild")
        instance_name = instance_ns.get("instance_name")
        instance_type = instance_ns.get("instance_type")
        zone_id = instance_ns.get("zone_id")
        image_id = instance_ns.get("image_id")
        ssh_key_name = instance_ns.get("ssh_key_name")
        instance_charge_type = instance_ns.get("instance_charge_type")

        # System disk config (decoupled via service.toml)
        disk_ns = instance_ns.get("system_disk")
        disk_category = disk_ns.get("category")
        disk_size = int(disk_ns.get("size"))

        # --------------------------------------------------
        # Create ECS instance
        # --------------------------------------------------
        self.instance = ecs.Instance(
            resource_name=instance_name,
            instance_name=instance_name,
            instance_type=instance_type,
            availability_zone=zone_id,
            image_id=image_id,
            security_groups=[security_group_id],
            vpc_id=vpc_id,
            vswitch_id=vswitch_id,
            instance_charge_type=instance_charge_type,
            system_disk_category=disk_category,
            system_disk_size=disk_size,
            key_name=ssh_key_name,
            opts=ResourceOptions(
                parent=self,
                protect=True,
                retain_on_delete=True,
            ),
        )
        logstream.log(
            level="INFO",
            message=f"ECS instance created OK: {instance_name} ({instance_type})",
        )

        # --------------------------------------------------
        # EIP — Fixed public IP (survives instance stop/start)
        # --------------------------------------------------
        eip_ns = instance_ns.get("eip", None)
        if eip_ns:
            eip_bandwidth = int(eip_ns.get("bandwidth", 10))
            eip_charge_type = eip_ns.get("internet_charge_type", "PayByTraffic")
            self.eip = ecs.EipAddress(
                resource_name=f"{instance_name}-eip",
                address_name=f"{instance_name}-eip",
                bandwidth=str(eip_bandwidth),
                internet_charge_type=eip_charge_type,
                opts=ResourceOptions(parent=self),
            )
            self.eip_association = ecs.EipAssociation(
                resource_name=f"{instance_name}-eip-assoc",
                allocation_id=self.eip.id,
                instance_id=self.instance.id,
                opts=ResourceOptions(
                    parent=self,
                    depends_on=[self.instance, self.eip],
                ),
            )
            logstream.log(
                level="INFO",
                message=f"EIP created and bound OK: {instance_name}",
            )
        else:
            self.eip = None
            self.eip_association = None
            logstream.log(
                level="INFO",
                message=f"No EIP config, using ephemeral public IP: {instance_name}",
            )

        # 注册所有输出
        if eip_ns:
            public_ip = self.eip.ip_address
            eip_id = self.eip.id
        else:
            public_ip = self.instance.public_ip
            eip_id = None

        self.register_outputs_bookmark = {
            "ecs/instance/lakebuild/id": self.instance.id,
            "ecs/instance/lakebuild/name": self.instance.instance_name,
            "ecs/instance/lakebuild/type": self.instance.instance_type,
            "ecs/instance/lakebuild/public_ip": public_ip,
            "ecs/instance/lakebuild/eip_id": eip_id,
            "ecs/instance/lakebuild/private_ip": self.instance.private_ip,
            "ecs/instance/lakebuild/ssh_key_name": ssh_key_name,
            "ref/vpc/network/vpc_id": vpc_id,
            "ref/vpc/network/vswitch_id": vswitch_id,
            "ref/vpc/network/security_group_id": security_group_id,
        }
        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(message="Server infrastructure outputs registered")
