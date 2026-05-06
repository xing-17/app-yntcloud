from __future__ import annotations

from pulumi import ComponentResource, ResourceOptions
from pulumi_alicloud import ecs, vpc
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream


class NetworkInfra(ComponentResource):
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
            "custom:alicloud:NetworkInfra",
            name,
            None,
            opts=opts,
        )
        self.overlay = overlay
        self.logstream = logstream

        # 获取配置命名空间
        ns = overlay.get_namespace()
        environ_name = ns.get("environ.name")
        network_ns = ns.get("environ.resources.network")

        # ==================== VPC ====================
        # 创建 VPC - 虚拟私有云
        vpc_ns = network_ns.get("vpc")
        vpc_name = vpc_ns.get("name")
        vpc_cidr = vpc_ns.get("cidr")
        self.vpc = vpc.Network(
            resource_name=vpc_name,
            vpc_name=vpc_name,
            cidr_block=vpc_cidr,
            description=f"VPC for {environ_name}",
            tags=vpc_ns.get("tags").to_dict(),
            opts=ResourceOptions(parent=self),
        )
        logstream.log(message=f"VPC Network {vpc_name} created OK ({vpc_cidr})")

        # ==================== VSwitch ====================
        # 创建 VSwitch - 交换机（等同于 AWS 的 Subnet）
        vswitch_ns = network_ns.get("vswitch")
        vswitch_name = vswitch_ns.get("name")
        vswitch_cidr = vswitch_ns.get("cidr")
        zone_id = vswitch_ns.get("zone_id")
        description = f"VSwitch for {environ_name} in zone {zone_id}"
        self.vswitch = vpc.Switch(
            resource_name=vswitch_name,
            vswitch_name=vswitch_name,
            vpc_id=self.vpc.id,
            cidr_block=vswitch_cidr,
            zone_id=zone_id,
            description=description,
            tags=vswitch_ns.get("tags").to_dict(),
            opts=ResourceOptions(parent=self),
        )
        logstream.log(message=f"VPC VSwitch {vswitch_name} at {zone_id} created OK.")

        # ==================== Security Groups ====================
        # 创建数据服务安全组 - 白名单策略（只允许可信来源访问）
        sg_ns = network_ns.get("security_group")
        sg_name = sg_ns.get("name")
        self.security_group = ecs.SecurityGroup(
            resource_name=sg_name,
            security_group_name=sg_name,
            description="Security group with whitelist policy - allows trusted sources only",
            vpc_id=self.vpc.id,
            tags=sg_ns.get("tags").to_dict(),
            opts=ResourceOptions(parent=self),
        )

        # ==================== 入站规则 - 白名单策略 ====================
        # Priority 1（最高优先级）- 允许悉尼 IP 访问所有端口
        self.sg_rule_allow_trusted_ip = ecs.SecurityGroupRule(
            resource_name=f"{sg_name}-allow-trusted-ip",
            type="ingress",
            ip_protocol="all",
            nic_type="intranet",
            policy="accept",
            port_range="-1/-1",
            priority=1,
            security_group_id=self.security_group.id,
            cidr_ip="203.166.239.21/32",
            description="Allow trusted IP to access all ports",
            opts=ResourceOptions(parent=self.security_group),
        )
        # Priority 1 - 允许 VPC 内网全互通（涵盖了所有 VSwitch）
        self.sg_rule_allow_vpc = ecs.SecurityGroupRule(
            resource_name=f"{sg_name}-allow-vpc",
            type="ingress",
            ip_protocol="all",
            nic_type="intranet",
            policy="accept",
            port_range="-1/-1",
            priority=1,
            security_group_id=self.security_group.id,
            cidr_ip=vpc_cidr,
            description="Allow VPC internal network to access all ports",
            opts=ResourceOptions(parent=self.security_group),
        )

        # ==================== 出站规则 - 允许所有出站 ====================
        self.sg_rule_egress = ecs.SecurityGroupRule(
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
        logstream.log(message=f"Security group {sg_name} created OK")

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
            "security_group/name": self.security_group.security_group_name,
        }
        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(message="Outputs registered OK")
