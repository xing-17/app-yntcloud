from __future__ import annotations

import pulumi_alicloud as alicloud
from pulumi import ComponentResource, ResourceOptions
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream


class NetworkInfrastructure(ComponentResource):
    """
    阿里云 VPC 网络基础设施组件
    
    创建以下资源：
    - VPC: 虚拟私有云
    - VSwitch: 交换机（子网）
    - Security Group: 安全组
    
    架构说明：
    - 极简设计，单 VPC + 单 VSwitch
    - 不创建 NAT Gateway 和 EIP（成本优化）
    - 安全组开放所有流量（适用于数据采集场景）
    """

    def __init__(
        self,
        name: str,
        overlay: Overlay,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
    ):
        super().__init__(
            "custom:alicloud:NetworkInfrastructure",
            name,
            None,
            opts,
        )
        self.overlay = overlay
        self.logstream = logstream

        ns = overlay.get_namespace()
        network_ns = ns.get("environ.resources.network")

        # ==================== VPC ====================
        # 创建 VPC - 虚拟私有云
        vpc_ns = network_ns.get("vpc")
        vpc_name = vpc_ns.get("name")
        vpc_cidr = vpc_ns.get("cidr")
        
        self.vpc = alicloud.vpc.Network(
            resource_name=vpc_name,
            vpc_name=vpc_name,
            cidr_block=vpc_cidr,
            description=f"VPC for {overlay.get_namespace().get('environ.name')}",
            tags=vpc_ns.get("tags").to_dict(),
            opts=ResourceOptions(parent=self),
        )
        logstream.log(
            message=f"VPC created: {vpc_name} ({vpc_cidr})",
            level="INFO",
        )

        # ==================== VSwitch ====================
        # 创建 VSwitch - 交换机（等同于 AWS 的 Subnet）
        vswitch_ns = network_ns.get("vswitch")
        vswitch_name = vswitch_ns.get("name")
        vswitch_cidr = vswitch_ns.get("cidr")
        zone_id = vswitch_ns.get("zone_id")
        
        self.vswitch = alicloud.vpc.Switch(
            resource_name=vswitch_name,
            vswitch_name=vswitch_name,
            vpc_id=self.vpc.id,
            cidr_block=vswitch_cidr,
            zone_id=zone_id,
            description=f"VSwitch for {overlay.get_namespace().get('environ.name')}",
            tags=vswitch_ns.get("tags").to_dict(),
            opts=ResourceOptions(parent=self),
        )
        logstream.log(
            message=f"VSwitch created: {vswitch_name} ({vswitch_cidr}) in zone {zone_id}",
            level="INFO",
        )

        # ==================== Security Groups ====================
        # 创建数据服务安全组 - 开放所有流量（适用于数据采集、爬虫等场景）
        sg_ns = network_ns.get("security_group")
        sg_name = sg_ns.get("name")
        self.security_group = alicloud.ecs.SecurityGroup(
            resource_name=sg_name,
            name=sg_name,
            description="Security group for data services - allows all traffic",
            vpc_id=self.vpc.id,
            tags=sg_ns.get("tags").to_dict(),
            opts=ResourceOptions(parent=self),
        )
        
        # 入站规则：允许所有流量
        self.sg_rule_ingress = alicloud.ecs.SecurityGroupRule(
            resource_name=f"{sg_name}-ingress-all",
            type="ingress",
            ip_protocol="all",
            nic_type="intranet",
            policy="accept",
            port_range="-1/-1",
            priority=1,
            security_group_id=self.security_group.id,
            cidr_ip="0.0.0.0/0",
            description="Allow all inbound traffic",
            opts=ResourceOptions(parent=self.security_group),
        )
        
        # 出站规则：允许所有流量
        self.sg_rule_egress = alicloud.ecs.SecurityGroupRule(
            resource_name=f"{sg_name}-egress-all",
            type="egress",
            ip_protocol="all",
            nic_type="intranet",
            policy="accept",
            port_range="-1/-1",
            priority=1,
            security_group_id=self.security_group.id,
            cidr_ip="0.0.0.0/0",
            description="Allow all outbound traffic",
            opts=ResourceOptions(parent=self.security_group),
        )
        
        logstream.log(
            message=f"Security Group created: {sg_name} (allows all traffic)",
            level="INFO",
        )

        # 注册所有输出
        self.register_outputs_bookmark = {
            # VPC 输出
            "vpc/id": self.vpc.id,
            "vpc/name": self.vpc.vpc_name,
            "vpc/cidr": self.vpc.cidr_block,
            # VSwitch 输出
            "vswitch/id": self.vswitch.id,
            "vswitch/name": self.vswitch.vswitch_name,
            "vswitch/cidr": self.vswitch.cidr_block,
            "vswitch/zone_id": self.vswitch.zone_id,
            # Security Group 输出
            "security_group/id": self.security_group.id,
            "security_group/name": self.security_group.name,
        }
        self.register_outputs(self.register_outputs_bookmark)
        
        logstream.log(
            message="Network infrastructure outputs registered",
            level="INFO",
        )
