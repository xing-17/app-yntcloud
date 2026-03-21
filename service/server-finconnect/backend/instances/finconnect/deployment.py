from __future__ import annotations

import hashlib
import os
import json
import subprocess
from pathlib import Path
import pulumi
import yaml


from pulumi import ComponentResource, ResourceOptions
from pulumi.output import Output
from pulumi_alicloud import ecs
from pulumi_alicloud import oos
from pulumi_command import local, remote
from xcloudmeta.centre import Overlay
from xlog.stream.stream import LogStream


class FinConnectDeployment(ComponentResource):

    def __init__(
        self,
        name: str,
        overlay: Overlay,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
        instance: ecs.Instance | None = None,
        secret: dict | None = None,
    ):
        super().__init__(
            "custom:alicloud:InstancesInfra",
            name,
            None,
            opts,
        )
        self.overlay = overlay
        self.logstream = logstream
        self.instance = instance
        self.secret = secret
        
        # ------------------------------------------------------
        # Auto-update source code from git repository
        _source_dir: Path = Path(__file__).parent / "source"
        _git_owner = "xing-17"
        _app_name = "app-finconnect"
        _app_dir = Path(f"{_source_dir}/{_app_name}").resolve()
        _submodule_url = f"https://github.com/{_git_owner}/{_app_name}.git"
        os.makedirs(_source_dir, exist_ok=True)
        if _app_dir.exists():
            subprocess.run(["rm", "-rf", _app_dir.as_posix()], check=True, timeout=30)
        try:
            subprocess.run(
                ["git", "clone", _submodule_url, _app_dir.as_posix()],
                cwd=_source_dir,
                check=True,
                timeout=120,
            )
            logstream.log(message=f"Submodule '{_app_name}' updated OK.")
        except Exception as e:
            message = f"Failed to update submodule '{_app_name}': {e}"
            logstream.log(level="ERROR", message=message)
            raise RuntimeError(message) from e
        
        # ------------------------------------------------------
        # Build application setting from secret
        runtime_agent_api_key = secret["runtime_agent_api_key"]
        provider_tushare_key = secret["provider_tushare_key"]
        output_oss_main_access_key_id = secret["output_oss_main_access_key_id"]
        output_oss_main_access_key_secret = secret["output_oss_main_access_key_secret"]
        output_oss_main_endpoint = secret["output_oss_main_endpoint"]
        output_oss_main_bucket = secret["output_oss_main_bucket"]
        self.setting = {
            "runtime": {
                "app_name": "app-finconnect",
                "app_alias": "玉门",
                "app_level": "INFO",
                "app_mode": "agent",
                "app_timezone": "Asia/Shanghai",
                "app_log_enabled": True,
                "app_log_format": "TEXT",
                "agent_api_key": runtime_agent_api_key,
                "agent_host": "0.0.0.0",
                "agent_port": 8000,
            },
            "providers": [
                {
                    "type": "system",
                    "name": "system",
                },
                {
                    "type": "tushare",
                    "name": "tushare",
                    "key": provider_tushare_key,
                    "ttl_seconds": 1800,
                    "ttl_margin": 60,
                    "use_cache": True,
                    "retry_max": 1,
                    "retry_wait_seconds": 30,
                    "retry_rate": 1.0,
                    "coolant_interval": 0,
                    "jitter_min_seconds": 0.1,
                    "jitter_max_seconds": 0.5,
                }
            ],
            "outputs": [
                {
                    "type": "oss",
                    "name": "oss-main",
                    "access_key_id": output_oss_main_access_key_id,
                    "access_key_secret": output_oss_main_access_key_secret,
                    "endpoint": output_oss_main_endpoint,
                    "bucket": output_oss_main_bucket,
                    "landing_prefix": "finconnect/landing/",
                    "definition_prefix": "finconnect/definition/",
                    "metadata_prefix": "finconnect/metadata/",
                    "verbose": True,
                },
                {
                    "type": "cache",
                    "verbose": True,
                }
            ],
        }
        with open(_app_dir / "setting.yaml", "w+", encoding="utf-8") as file:
            yaml.dump(
                self.setting, 
                file,
                indent=2,
                allow_unicode=True,
                encoding="utf-8",
                sort_keys=False,
            )
            logstream.log(message=f"Application setting built OK.")

        # ------------------------------------------------------
        # Install rsync on instance for code synchronization
        instance_user = secret["instance_user"]
        instance_password = secret["instance_password"]
        instance_mount_point = f"/{instance_user}/workspace"
        self.install_rsync = remote.Command(
            "install-rsync",
            connection=remote.ConnectionArgs(
                host=self.instance.public_ip,
                user=instance_user,
                password=instance_password,
            ),
            create="yum install -y rsync",
            opts=ResourceOptions(
                parent=self,
                depends_on=[self.instance],
            )
        )
        rsync_cmd = pulumi.Output.all(instance.public_ip).apply(
            lambda args: (
                f"rsync -avz --delete "
                f"--exclude '.git/' "
                f"--exclude '__pycache__/' "
                f"-e 'ssh -o StrictHostKeyChecking=no' "
                f"--rsync-path='mkdir -p {instance_mount_point} && rsync' "
                f"{_app_dir.as_posix()}/ root@{args[0]}:{instance_mount_point}/"
            )
        )
        self.code_upload = local.Command(
            "code-upload",
            create=rsync_cmd,
            update=rsync_cmd,
            opts=ResourceOptions(
                parent=self,
                depends_on=[self.install_rsync],
            ),
        )
        self.logstream.log(
            level="INFO",
            message="Code upload command resource created.",
        )
