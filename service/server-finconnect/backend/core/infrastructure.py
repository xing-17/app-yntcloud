from __future__ import annotations

import json
from pathlib import Path

from pulumi import ComponentResource, Output, ResourceOptions, StackReference
from pulumi_alicloud import ram
from pulumi_alicloud.fc import V3FunctionVpcConfigArgs
from xcloudmeta.centre import Overlay
from xcloudmeta.centre.namespace import Namespace
from xlog.stream.stream import LogStream

from backend.core.corebuild import CoreBuildInfra


class CoreFCInfra(ComponentResource):
    """
    函数计算基础设施组件: finconnect-remote-run

    管理以下资源：
    - alicloud.fc3.Function: finconnect-remote-run

    """

    def __init__(
        self,
        name: str,
        overlay: Overlay,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
    ):
        super().__init__(
            "custom:alicloud:CoreFCInfra",
            name,
            None,
            opts,
        )
        self.overlay = overlay
        self.logstream = logstream

        ns = overlay.get_namespace()
        service_name = ns.get("service.name")
        functions_ns: Namespace = ns.get("service.fc.function")

        # ------------------------------------------------------
        # Reference network stack
        # - GET: vpc_id
        # - GET: vswitch_id
        # - GET: security_group_id
        # ------------------------------------------------------
        service_ns = ns.get("service")
        stack_ref_ns = service_ns.get("reference.stack")
        stack_network_ref_ns = stack_ref_ns.get("network")
        stack_network_name = stack_network_ref_ns.get("name")
        stack_network = StackReference(
            "stackref-network",
            stack_name=stack_network_name,
            opts=ResourceOptions(parent=self),
        )
        vpc_id: Output[str] = stack_network.get_output("vpc/id")
        vswitch_id: Output[str] = stack_network.get_output("vswitch/id")
        security_group_id: Output[str] = stack_network.get_output("security_group/id")
        logstream.log(message="Network Attributes resolved OK")

        # ------------------------------------
        # RAM Role creation for FC functions
        # ------------------------------------
        role_name = f"{service_name}-fc-role"
        self.role = ram.Role(
            resource_name=role_name,
            role_name=role_name,
            description=f"RAM role for FC functions in {service_name}",
            assume_role_policy_document=json.dumps(
                {
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Effect": "Allow",
                            "Principal": {"Service": ["fc.aliyuncs.com"]},
                        }
                    ],
                    "Version": "1",
                }
            ),
        )
        ecs_manage_policy_doc = {
            "Statement": [
                {
                    "Action": [
                        "Ecs:DescribeInstances",
                        "Ecs:StartInstance",
                        "Ecs:StopInstance",
                        "Ecs:RunCommand",
                        "Ecs:ListCommands",
                        "Ecs:GetCommandInvocation",
                    ],
                    "Effect": "Allow",
                    "Resource": "*",
                }
            ],
            "Version": "1",
        }
        ecs_manage_policy = ram.Policy(
            resource_name=f"{service_name}-fc-ecs-manage-policy",
            policy_name=f"{service_name}-fc-ecs-manage-policy",
            description=f"Custom policy for FC functions to manage ECS instances in {service_name}",
            policy_document=json.dumps(ecs_manage_policy_doc),
        )
        self.ecs_manage_attachment = ram.RolePolicyAttachment(
            resource_name=f"{service_name}-fc-ecs-manage-attachment",
            role_name=self.role.role_name,
            policy_name=ecs_manage_policy.policy_name,
            policy_type=ecs_manage_policy.type,
            opts=ResourceOptions(parent=self),
        )

        oos_manage_policy_doc = {
            "Statement": [
                {
                    "Action": [
                        "oos:GetSecretParameter",
                        "oos:GetSecretParameters",
                    ],
                    "Effect": "Allow",
                    "Resource": "*",
                }
            ],
            "Version": "1",
        }
        oos_manage_policy = ram.Policy(
            resource_name=f"{service_name}-fc-oos-manage-policy",
            policy_name=f"{service_name}-fc-oos-manage-policy",
            description=f"Custom policy for FC functions to manage OOS secrets in {service_name}",
            policy_document=json.dumps(oos_manage_policy_doc),
        )
        self.oos_manage_attachment = ram.RolePolicyAttachment(
            resource_name=f"{service_name}-fc-oos-manage-attachment",
            role_name=self.role.role_name,
            policy_name=oos_manage_policy.policy_name,
            policy_type=oos_manage_policy.type,
            opts=ResourceOptions(parent=self),
        )

        # ------------------------------------
        # FC Functions creation
        # ------------------------------------
        self.fc_registry = {}
        self.register_outputs_bookmark = {
            f"ram/role/{role_name}/arn": self.role.arn,
            f"ram/role/{role_name}/name": self.role.role_name,
        }

        for function_name in functions_ns.keys():
            source = Path(__file__).parent / "functions" / function_name
            unit = CoreBuildInfra(
                function_name=function_name,
                source=source,
                role=self.role,
                ns=functions_ns.get(function_name),
                opts=ResourceOptions(parent=self),
                vpc_config=V3FunctionVpcConfigArgs(
                    security_group_id=security_group_id,
                    vpc_id=vpc_id,
                    vswitch_ids=[vswitch_id],
                ),
                internet_access=True,
            )
            self.fc_registry[function_name] = unit
            self.register_outputs_bookmark.update(
                unit.register_outputs_bookmark,
            )
            logstream.log(message=f"FC {function_name} defined OK")

        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(f"{len(self.fc_registry)} FC functions defined OK")
