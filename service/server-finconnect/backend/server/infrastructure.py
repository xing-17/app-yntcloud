from __future__ import annotations

import json

import pulumi
from pulumi import ComponentResource, ResourceOptions
from pulumi_alicloud import ecs, oos
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream


class ECSInfra(ComponentResource):
    """
    FinConnect服务器基础设施组件

    管理以下资源：
    - ECS Instance: 从现有instance导入并管理
    - 关联network service的VPC和Security Group

    """

    def __init__(
        self,
        name: str,
        overlay: Overlay,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
    ):
        super().__init__(
            "custom:alicloud:InstancesInfra",
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
        # - GET: secret: dict
        # ------------------------------------------------------
        instance_name = "app-finconnect"
        secret_name = f"ecs/server/{instance_name}/keys"
        try:
            lookup_result: oos.GetSecretParametersResult = oos.get_secret_parameters(
                secret_parameter_name=secret_name,
                with_decryption=True,
                enable_details=True,
            )
            parameter: oos.SecretParameter = lookup_result.parameters[0]
            secret: dict = json.loads(parameter.value)
            ssh_key_name = secret["ssh_key_name"]
            logstream.log(message=f"OOS secret loaded OK: {secret_name}")
        except Exception as e:
            raise RuntimeError(f"Failed to load OOS secret '{secret_name}': {e}") from e

        # ------------------------------------------------------
        # Create FinConnect infrastructure on existing instance
        # - GET/IMPORT: ECS instance by ID
        # ------------------------------------------------------
        instance_ns = ns.get("service.ecs.instance.app-finconnect")
        self.instance_id = instance_ns.get("instance_id")
        self.instance_type = instance_ns.get("instance_type")
        try:
            lookup_result: ecs.GetInstancesResult = ecs.get_instances(
                ids=[self.instance_id],
            )
            loaded_instance: ecs.GetInstancesResult = lookup_result.instances[0]
        except Exception as e:
            raise RuntimeError(f"Failed to load ECS instance '{self.instance_id}': {e}") from e

        try:
            # 尝试查询现有的pulumi资源
            imported = pulumi.runtime.is_dry_run()
            import_id = self.instance_id if not imported else None
        except Exception:
            import_id = self.instance_id

        self.instance = ecs.Instance(
            resource_name=f"{instance_name}",
            instance_name=instance_name,
            instance_type=loaded_instance.instance_type,
            security_groups=[security_group_id],
            vpc_id=vpc_id,
            vswitch_id=vswitch_id,
            image_id=loaded_instance.image_id,
            key_name=ssh_key_name,
            tags=ns.get("tags").to_dict(),
            opts=ResourceOptions(
                parent=self,
                import_=import_id,
            ),
        )

        # ------------------------------------------------------
        # Create FinConnect EIP if needed
        # ------------------------------------------------------
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
            logstream.log(message=f"EIP created and bound OK: {instance_name}")

        # 注册所有输出
        if eip_ns:
            public_ip = self.eip.ip_address
            eip_id = self.eip.id
        else:
            public_ip = self.instance.public_ip
            eip_id = None

        self.register_outputs_bookmark = {
            "ecs/instance/finconnect/id": self.instance.id,
            "ecs/instance/finconnect/name": self.instance.instance_name,
            "ecs/instance/finconnect/type": self.instance.instance_type,
            "ecs/instance/finconnect/public_ip": public_ip,
            "ecs/instance/finconnect/eip_id": eip_id,
            "ecs/instance/finconnect/private_ip": self.instance.private_ip,
            "ecs/instance/finconnect/ssh_key_name": ssh_key_name,
            "ref/vpc/network/vpc_id": vpc_id,
            "ref/vpc/network/vswitch_id": vswitch_id,
            "ref/vpc/network/security_group_id": security_group_id,
        }
        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(message="Server infrastructure outputs registered")
