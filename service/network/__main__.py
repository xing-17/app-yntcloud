from __future__ import annotations

from pathlib import Path

import pulumi
from backend.component import Backend
from xcloudmeta.centre import Centre, Overlay
from xlog import ColorTree, LogStream

# 初始化日志流
stream = LogStream(
    name="network",
    level="INFO",
    format=ColorTree(),
    verbose=True,
)

current = Path(__file__).parent.name
stream.log(f"Starting Pulumi deployment for service: {current}")

# 初始化 Pulumi 配置
config = pulumi.Config()

# 初始化 centre
centre = Centre(root="../../")

# 获取 Pulumi stack 名称
# 预期格式: <platform_name>-<environ_code>-<service_name>-stack
# 示例: ynt-cloud-prod-network-stack
stack_name = pulumi.get_stack()
stream.log(f"Pulumi stack: {stack_name}")

try:
    # 尝试从 Pulumi 配置中获取
    platform_name = config.get("platform")
    environ_name = config.get("environ")
    service_name = config.get("service")

    if not platform_name or not environ_name or not service_name:
        # 从 stack 名称解析以提取 platform、environ 和 service
        # Stack 名称格式: {platform_name}-{environ_code}-{service_name}-stack
        # 示例: ynt-cloud-prod-network-stack
        # 移除 '-stack' 后缀
        if not stack_name.endswith("-stack"):
            raise ValueError(
                f"Invalid stack name format: {stack_name}. "
                f"Expected format: <plt>-<env>-<svc>-stack"
            )
        
        stack_base = stack_name[:-6]  # 移除 '-stack'
        
        # 尝试从开头匹配平台名称
        platform = None
        for plat in centre.list_platform():
            plat_name = plat.get_name()
            if stack_base.startswith(plat_name + "-"):
                platform = plat
                platform_name = plat_name
                # 移除平台名称和后面的短横线
                remaining = stack_base[len(plat_name) + 1:]
                break
        
        if not platform:
            raise ValueError(
                f"Could not identify platform from stack name: {stack_name}. "
                f"Available platforms: {[p.name for p in centre.list_platform()]}"
            )
        
        # 尝试从剩余字符串的末尾匹配服务名称
        service = None
        service_name = None
        for svc in centre.list_service():
            svc_name = svc.get_name()
            if remaining.endswith("-" + svc_name):
                service = svc
                service_name = svc_name
                # 移除服务名称和前面的短横线
                environ_code = remaining[:-len(svc_name) - 1]
                break
        
        if not service:
            # 降级处理：使用当前目录作为服务名称
            # 假设剩余的是: {environ_code}-{service_name}
            parts = remaining.split("-")
            if len(parts) >= 2:
                environ_code = "-".join(parts[:-1])
                service_name = parts[-1]
            else:
                raise ValueError(
                    f"Could not parse stack name: {stack_name}. "
                    f"Expected format: <platform_name>-<environ_code>-<service_name>-stack"
                )
            
            stream.log(
                message=f"Service '{service_name}' not found in centre, using parsed value",
                level="WARNING",
            )
        
        # 验证服务是否匹配当前目录
        if service_name != current:
            stream.log(
                message=f"Warning: Stack service '{service_name}' != directory '{current}'",
                level="WARNING",
            )
        
        # 通过代码查找环境
        environ = centre.get_environ(environ_code)
        if not environ:
            raise ValueError(
                f"Environment with code '{environ_code}' not found. "
                f"Available environs: {[(e.name, e.get_code()) for e in centre.list_environ()]}"
            )
        environ_name = environ.name
        
        stream.log(
            message="Parsed stack name",
            context={
                "platform_name": platform_name,
                "environ_code": environ_code,
                "environ_name": environ_name,
                "service_name": service_name,
            },
        )
    else:
        # 提供了配置，通过名称获取模块
        platform = centre.get_platform(platform_name)
        environ = centre.get_environ(environ_name)

    if not platform:
        raise ValueError(f"Platform '{platform_name}' not found")
    
    if not environ:
        raise ValueError(f"Environment '{environ_name}' not found")

    stream.log(
        message="Resolved configuration",
        context={
            "platform": platform_name,
            "environ": environ_name,
            "service": current,
        },
    )

    # 创建 overlay
    overlay: Overlay = centre.overlay(
        platform=platform.name,
        environ=environ.name,
        service=current,
    )
    overlay.validate()

    # 验证 stack 名称是否匹配预期格式
    expected_stack_id = overlay.get_stack_id()
    if stack_name != expected_stack_id:
        stream.log(
            message=f"Stack name mismatch: '{stack_name}' != expected '{expected_stack_id}'",
            level="WARNING",
        )

    stream.log(
        message="Overlay built successfully",
        context={
            "stack_id": overlay.get_stack_id(),
            "account": environ.get_account(),
            "region": environ.get_region(),
        },
    )
    stream.log(
        message="Show overlay:",
        level="DEBUG",
        context=overlay.describe(),
    )

    # 使用来自 overlay 的 stack ID 创建后端资源
    backend = Backend(
        name=overlay.get_stack_id(),
        overlay=overlay,
        logstream=stream,
    )

    # 导出 stack 输出
    pulumi.export("stack_id", overlay.get_stack_id())
    pulumi.export("platform_name", platform_name)
    pulumi.export("platform_code", platform.get_code())
    pulumi.export("environ_name", environ_name)
    pulumi.export("environ_code", environ.get_code())
    pulumi.export("service_name", current)
    pulumi.export("region", environ.get_region())
    pulumi.export("account", environ.get_account())

    # 导出网络信息 - 供其他服务依赖
    for key, value in backend.register_outputs_bookmark.items():
        pulumi.export(key, value)

    stream.log("Pulumi program complete ✅")

except Exception as error:
    stream.log(
        message="Deployment failed",
        level="ERROR",
        context={"error": str(error)},
    )
    raise
