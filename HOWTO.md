# 在其他 Service 中引用 Network Service 的输出

本文档展示如何在其他 Pulumi service 中引用 network service 导出的 VPC、VSwitch、Security Group 等资源。

## 📋 可用的网络资源输出

network service 已导出以下资源（stack: `ynt-cloud-prod-network-stack`）：

```json
{
    "vpc/id": "vpc-uf6c8as76poqp3kqde3jm",
    "vpc/name": "ynt-trading-prod-main",
    "vpc/cidr": "10.0.0.0/16",
    
    "vswitch/id": "vsw-uf6f6umdv71iam4hasxsz",
    "vswitch/name": "main",
    "vswitch/cidr": "10.0.1.0/24",
    "vswitch/zone_id": "cn-shanghai-l",
    
    "security_group/id": "sg-uf6h25bq6fvi3zmgsia9",
    "security_group/name": "data-service-group"
}
```

---

## 🔗 方法 1: 使用 Pulumi StackReference（推荐）

### 在新 Service 中引用网络资源

**示例：创建一个使用 VPC 的 ECS 实例**

```python
# 在你的新 service 的 __main__.py 或 infrastructure.py 中

from __future__ import annotations

import pulumi
import pulumi_alicloud as alicloud
from pulumi import StackReference

# ==================== 引用 Network Stack ====================
# 获取 network service 的 stack reference
network_stack = StackReference("ynt-cloud-prod-network-stack")

# 读取网络资源 ID
vpc_id = network_stack.get_output("vpc/id")
vswitch_id = network_stack.get_output("vswitch/id")
security_group_id = network_stack.get_output("security_group/id")

# ==================== 使用网络资源创建 ECS ====================
# 创建 ECS 实例（自动使用上面的 VPC）
ecs_instance = alicloud.ecs.Instance(
    resource_name="data-collector",
    instance_name="data-collector",
    
    # 使用 network service 的输出
    vswitch_id=vswitch_id,                    # ✅ 使用导出的 VSwitch ID
    security_groups=[security_group_id],      # ✅ 使用导出的 Security Group ID
    
    # 实例配置
    instance_type="ecs.t5-lc1m1.small",       # 突发性能型（低成本）
    image_id="ubuntu_22_04_x64_20G_alibase_20231221.vhd",
    
    # 网络配置
    internet_charge_type="PayByTraffic",      # 按流量计费
    internet_max_bandwidth_out=100,            # 100Mbps 带宽
    
    # 磁盘配置
    system_disk_category="cloud_efficiency",
    system_disk_size=40,
    
    # 付费类型
    instance_charge_type="PostPaid",           # 按量付费
)

# 导出 ECS 的公网 IP
pulumi.export("ecs/public_ip", ecs_instance.public_ip)
pulumi.export("ecs/private_ip", ecs_instance.private_ip)
```

---

## 🔗 方法 2: 在组件类中引用

**示例：在 ComponentResource 中使用**

```python
from __future__ import annotations

import pulumi
import pulumi_alicloud as alicloud
from pulumi import ComponentResource, ResourceOptions, StackReference
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream


class ComputeInfrastructure(ComponentResource):
    """计算基础设施组件 - 自动引用 network service"""

    def __init__(
        self,
        name: str,
        overlay: Overlay,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
    ):
        super().__init__(
            "custom:alicloud:ComputeInfrastructure",
            name,
            None,
            opts,
        )
        
        # ==================== 引用 Network Stack ====================
        # 获取当前环境的 network stack 名称
        stack_id = overlay.get_stack_id()  # 例如: ynt-cloud-prod-compute-stack
        # 构建 network stack 名称
        network_stack_name = stack_id.replace("compute", "network")
        
        logstream.log(
            message=f"Referencing network stack: {network_stack_name}",
            level="INFO",
        )
        
        # 创建 StackReference
        self.network_stack = StackReference(network_stack_name)
        
        # 读取网络资源
        self.vpc_id = self.network_stack.get_output("vpc/id")
        self.vswitch_id = self.network_stack.get_output("vswitch/id")
        self.security_group_id = self.network_stack.get_output("security_group/id")
        
        logstream.log(
            message="Network resources loaded from stack reference",
            level="INFO",
        )
        
        # ==================== 创建资源 ====================
        # 现在可以使用这些网络资源创建 ECS、RDS 等
        self.ecs = alicloud.ecs.Instance(
            resource_name="my-instance",
            vswitch_id=self.vswitch_id,
            security_groups=[self.security_group_id],
            # ... 其他配置
            opts=ResourceOptions(parent=self),
        )
```

---

## 🔗 方法 3: 动态构建 Stack 名称

**根据环境自动引用对应的 network stack**

```python
import pulumi
from pulumi import StackReference

# 获取当前 stack 信息
current_stack = pulumi.get_stack()  # 例如: ynt-cloud-prod-compute-stack

# 解析出环境信息
# 从 "ynt-cloud-prod-compute-stack" 提取 "ynt-cloud-prod"
parts = current_stack.rsplit("-", 2)  # ['ynt-cloud-prod', 'compute', 'stack']
env_prefix = parts[0]  # 'ynt-cloud-prod'

# 构建 network stack 名称
network_stack_name = f"{env_prefix}-network-stack"

# 引用 network stack
network_stack = StackReference(network_stack_name)

# 使用资源
vpc_id = network_stack.get_output("vpc/id")
vswitch_id = network_stack.get_output("vswitch/id")
security_group_id = network_stack.get_output("security_group/id")
```

---
