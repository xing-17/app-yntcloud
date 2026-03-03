# Storage Service - YNT Cloud

OSS 存储基础设施服务，使用 Pulumi 管理阿里云 OSS buckets。

## 架构

```
storage/
├── __main__.py              # Pulumi 入口点
├── Pulumi.yaml              # Pulumi 项目配置
├── service.toml             # 服务配置
└── backend/
    ├── component.py         # 主组件
    └── oss/
        └── infrastructure.py # OSS Bucket 实现
```

## 配置

服务通过 `service.toml` 定义 OSS buckets：

```toml
[service.resources.oss.bucket.datalake]
name = "{{ ref(environ.name) }}-datalake"
acl = "private"
storage_class = "Standard"
versioning = false
tags = { ResourceLevel = "Environ", ResourceType = "Bucket", Purpose = "DataLake" }

[service.resources.oss.bucket.infralake]
name = "{{ ref(environ.name) }}-infralake"
acl = "private"
storage_class = "Standard"
versioning = false
tags = { ResourceLevel = "Environ", ResourceType = "Bucket", Purpose = "InfraLake" }
```

## 使用方法

### 1. 初始化 Pulumi Stack

```bash
cd service/storage

# 创建新的 stack（命名格式：<platform>-<environ>）
pulumi stack init ynt-cloud-ynt-trading-prod

# 或者选择已存在的 stack
pulumi stack select ynt-cloud-ynt-trading-prod
```

### 2. 配置阿里云凭证

```bash
# 设置阿里云 Access Key
pulumi config set alicloud:accessKey <YOUR_ACCESS_KEY> --secret
pulumi config set alicloud:secretKey <YOUR_SECRET_KEY> --secret
pulumi config set alicloud:region cn-shanghai

# 或者设置 platform 和 environ（可选）
pulumi config set platform ynt-cloud
pulumi config set environ ynt-trading-prod
```

### 3. 预览和部署

```bash
# 预览将要创建的资源
pulumi preview

# 执行部署
pulumi up

# 查看已创建的资源
pulumi stack output
```

### 4. 销毁资源

```bash
# 销毁所有资源
pulumi destroy
```

## 创建的资源

本服务将创建以下 OSS buckets：

1. **ynt-trading-prod-datalake**
   - ACL: private
   - 存储类型: Standard
   - 用途: 数据湖存储

2. **ynt-trading-prod-infralake**
   - ACL: private
   - 存储类型: Standard
   - 用途: 基础设施数据存储

## 依赖

- Python >= 3.11
- pulumi >= 3.0.0
- pulumi-alicloud >= 3.0.0
- xcloudmeta (Centre/Overlay 配置管理)
- xlog (日志管理)

## 状态管理

Pulumi 状态默认存储在本地 `~/.pulumi/stacks/`。

建议配置远程后端（使用阿里云 OSS）：

```bash
# 登录到阿里云 OSS backend
pulumi login oss://ynt-pulumi-state
```

## 参考

- [Pulumi Alicloud Provider](https://www.pulumi.com/registry/packages/alicloud/)
- [阿里云 OSS 文档](https://www.alibabacloud.com/help/oss/)
