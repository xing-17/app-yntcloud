from __future__ import annotations

import json

import pulumi
import pulumi_alicloud as alicloud
from pulumi import ComponentResource, ResourceOptions
from pulumi.output import Output
from pulumi_alicloud import ecs
from pulumi_alicloud import oos
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream

from backend.instances.finconnect.infrastructure import FinConnectInfra
from backend.instances.finconnect.deployment import FinConnectDeployment


class InstancesInfra(ComponentResource):
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
        
        # --------------------------------------------------------------------------
        # Reference network stack
        stack_ref_ns = service_ns.get("reference.stack")
        stack_network_ref_ns = stack_ref_ns.get("network")
        stack_network_name = stack_network_ref_ns.get("name")
        stack_network = pulumi.StackReference(
            f"stackref-network",
            stack_name=stack_network_name,
            opts=ResourceOptions(parent=self),
        )
        logstream.log(
            level="INFO",
            message=f"REF stack OK -> network: {stack_network_name}",
        )
        # Fetch reference values from network stack
        vpc_id: pulumi.Output[str] = stack_network.get_output("vpc/id")
        vswitch_id: pulumi.Output[str] = stack_network.get_output("vswitch/id")
        security_group_id: pulumi.Output[str] = stack_network.get_output("security_group/id")
        logstream.log(
            level="INFO",
            message="Resources resolved OK.",
        )
        
        # ------------------------------------------------------
        # FinConnect Instance
        # ------------------------------------------------------
        # Load OOS secret for instance access keys
        instance_name = "app-finconnect"
        secret_name = f"ecs/server/{instance_name}/keys"
        secret_lookup_result: oos.GetSecretParametersResult = oos.get_secret_parameters(
            secret_parameter_name=secret_name,
            with_decryption=True,
            enable_details=True,
        )
        parameters = secret_lookup_result.parameters
        if len(parameters) == 0:
            message = f"OOS secret not found: {secret_name}"
            logstream.log(level="ERROR", message=message)
            raise RuntimeError(message)
        
        secret: oos.SecretParameter = parameters[0]
        secret_payload = json.loads(secret.value)
        logstream.log(message=f"OOS secret loaded OK: {secret_name}")
        
        self.finconnect = FinConnectInfra(
            name="finconnect",
            overlay=overlay,
            logstream=logstream,
            opts=ResourceOptions(parent=self),
            vpc_id=vpc_id,
            vswitch_id=vswitch_id,
            security_group_id=security_group_id,
            secret=secret_payload,
        )
        
        self.finconnect_deployment = FinConnectDeployment(
            name="finconnect-deployment",
            overlay=overlay,
            logstream=logstream,
            opts=ResourceOptions(parent=self),
            instance=self.finconnect.instance,
            secret=secret_payload,
        )
        
        # 注册所有输出
        self.register_outputs_bookmark = {
            "instance/finconnect/id": self.finconnect.instance.id,
            "instance/finconnect/name": self.finconnect.instance.instance_name,
            "instance/finconnect/type": self.finconnect.instance.instance_type,
            "instance/finconnect/public_ip": self.finconnect.instance.public_ip,
            "instance/finconnect/private_ip": self.finconnect.instance.private_ip,
            "network/vpc_id": vpc_id,
            "network/vswitch_id": vswitch_id,
            "network/security_group_id": security_group_id,
        }
        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(
            message="Server infrastructure outputs registered",
            level="INFO",
        )
