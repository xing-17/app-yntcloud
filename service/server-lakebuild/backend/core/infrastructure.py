from __future__ import annotations

import json
from pathlib import Path

from pulumi import (
    ComponentResource,
    Output,
    ResourceOptions,
    StackReference,
)
from pulumi_alicloud import ram
from pulumi_alicloud.fc import (
    V3FunctionLogConfigArgs,
    V3FunctionVpcConfigArgs,
)
from pulumi_alicloud.log import (
    Project,
    Store,
)
from xcloudmeta.centre import Overlay
from xcloudmeta.centre.namespace import Namespace
from xlog.stream.stream import LogStream

from backend.core.corebuild import CoreBuildInfra
from backend.core.layerbuild import LayerBuildInfra


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

        # ------------------------------------------------------
        # Reference storage stack
        # - GET: infralake bucket_name
        # ------------------------------------------------------
        stack_lake_ref_ns = stack_ref_ns.get("storage")
        stack_lake_name = stack_lake_ref_ns.get("name")
        stack_lake = StackReference(
            "stackref-lake",
            stack_name=stack_lake_name,
            opts=ResourceOptions(parent=self),
        )
        infralake_bucket_name: Output[str] = stack_lake.get_output("oss/bucket/infralake/name")
        logstream.log(message="Storage Attributes resolved OK")

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
                            "Principal": {
                                "Service": [
                                    "fc.aliyuncs.com",
                                ]
                            },
                        }
                    ],
                    "Version": "1",
                }
            ),
        )
        # ecs manage permissions for functions
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
        # oos read permissions for secrets
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
        kms_manage_policy_doc = {
            "Statement": [
                {
                    "Action": [
                        "kms:GetSecretValue",
                        "Kms:Decrypt",
                    ],
                    "Effect": "Allow",
                    "Resource": "*",
                }
            ],
            "Version": "1",
        }
        kms_manage_policy = ram.Policy(
            resource_name=f"{service_name}-fc-kms-manage-policy",
            policy_name=f"{service_name}-fc-kms-manage-policy",
            description=f"Custom policy for FC functions to manage KMS decryption in {service_name}",
            policy_document=json.dumps(kms_manage_policy_doc),
        )
        self.kms_manage_attachment = ram.RolePolicyAttachment(
            resource_name=f"{service_name}-fc-kms-manage-attachment",
            role_name=self.role.role_name,
            policy_name=kms_manage_policy.policy_name,
            policy_type=kms_manage_policy.type,
            opts=ResourceOptions(parent=self),
        )

        # oss read and write permissions
        oss_manage_policy_document = infralake_bucket_name.apply(
            lambda bucket: json.dumps(
                {
                    "Statement": [
                        {
                            "Action": [
                                "oss:GetObject",
                                "oss:PutObject",
                                "oss:ListBucket",
                            ],
                            "Effect": "Allow",
                            "Resource": [
                                f"acs:oss:*:*:{bucket}",
                                f"acs:oss:*:*:{bucket}/*",
                            ],
                        }
                    ],
                    "Version": "1",
                }
            )
        )
        oss_manage_policy = ram.Policy(
            resource_name=f"{service_name}-fc-oss-manage-policy",
            policy_name=f"{service_name}-fc-oss-manage-policy",
            description=f"Custom policy for FC functions to manage OSS objects in {service_name}",
            policy_document=oss_manage_policy_document,
        )
        self.oss_manage_attachment = ram.RolePolicyAttachment(
            resource_name=f"{service_name}-fc-oss-manage-attachment",
            role_name=self.role.role_name,
            policy_name=oss_manage_policy.policy_name,
            policy_type=oss_manage_policy.type,
            opts=ResourceOptions(parent=self),
        )
        self.register_outputs_bookmark = {
            f"ram/role/{role_name}/arn": self.role.arn,
            f"ram/role/{role_name}/name": self.role.role_name,
        }

        # ------------------------------------
        # FC Layers creation
        # ------------------------------------
        layers_ns: Namespace = ns.get("service.core.layer")
        layers_upload_prefix: str = f"infras/{service_name}/fc/layers"
        self.layers_registry = {}
        self.layers_arn_registry = {}

        for layer_key in layers_ns.keys():
            layer_config_ns = layers_ns.get(layer_key)
            layer_name = layer_config_ns.get("name")
            layer_infra = LayerBuildInfra(
                name=layer_name,
                description=layer_config_ns.get("description"),
                runtime=layer_config_ns.get("runtime"),
                python_version=layer_config_ns.get("python_version"),
                requirements=layer_config_ns.get("requirements"),
                timeout_minutes=5,
                oss_bucket=infralake_bucket_name,
                oss_prefix=layers_upload_prefix,
                logstream=logstream,
                opts=ResourceOptions(parent=self),
            )
            layer = layer_infra.layer
            self.layers_registry[layer_name] = layer
            self.layers_arn_registry[layer_name] = layer.layer_version_arn
            self.register_outputs_bookmark.update(
                layer_infra.register_outputs_bookmark,
            )
            logstream.log(message=f"Layer {layer_name} [{layer_infra.size_mb:.2f} MB] defined OK")

        # -------------------------------------
        # Create FC Project and Logstore
        # -------------------------------------
        self.project_name = f"{service_name}-fc-logproject"
        self.store_name = f"{service_name}-fc-logstore"
        self.project = Project(
            resource_name=self.project_name,
            project_name=self.project_name,
            description=f"Log project for {service_name} FC functions",
            opts=ResourceOptions(parent=self),
        )
        self.store = Store(
            resource_name=self.store_name,
            project_name=self.project.project_name,
            logstore_name=self.store_name,
            opts=ResourceOptions(parent=self.project),
        )
        logstream.log(message=f"Log Project and Store for {service_name} FC defined OK")

        # ------------------------------------
        # FC Functions creation
        # ------------------------------------
        functions_ns: Namespace = ns.get("service.fc.function")
        functions_upload_prefix: str = f"infras/{service_name}/fc/functions"
        self.fc_registry = {}

        for function_key in functions_ns.keys():
            function_ns = functions_ns.get(function_key)
            function_name = function_ns.get("name")
            source = Path(__file__).parent / "functions" / function_name
            function = CoreBuildInfra(
                name=function_name,
                source=source,
                oss_bucket=infralake_bucket_name,
                oss_prefix=functions_upload_prefix,
                role=self.role,
                runtime=function_ns.get("runtime"),
                handler=function_ns.get("handler"),
                memory=function_ns.get("memory"),
                timeout=function_ns.get("timeout"),
                description=function_ns.get("description"),
                includes=function_ns.get("includes"),
                excludes=function_ns.get("excludes"),
                env_vars=function_ns.get("env_vars", Namespace()).to_dict(),
                internet_access=function_ns.get("internet_access"),
                layers=function_ns.get("layers"),
                layers_arn_registry=self.layers_arn_registry,
                timeout_minutes=5,
                logstream=logstream,
                opts=ResourceOptions(
                    parent=self,
                    depends_on=[
                        self.role,
                        self.ecs_manage_attachment,
                        self.oos_manage_attachment,
                        self.oss_manage_attachment,
                        self.kms_manage_attachment,
                        self.project,
                        self.store,
                        *self.layers_registry.values(),
                    ],
                ),
                vpc_config=V3FunctionVpcConfigArgs(
                    security_group_id=security_group_id,
                    vpc_id=vpc_id,
                    vswitch_ids=[vswitch_id],
                ),
                log_config=V3FunctionLogConfigArgs(
                    enable_instance_metrics=True,
                    enable_request_metrics=True,
                    project=self.project.project_name,
                    logstore=self.store.logstore_name,
                ),
            )
            self.fc_registry[function_name] = function
            self.register_outputs_bookmark.update(
                function.register_outputs_bookmark,
            )
            logstream.log(message=f"FC {function_name} defined OK")

        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(f"{len(self.fc_registry)} FC functions defined OK")
