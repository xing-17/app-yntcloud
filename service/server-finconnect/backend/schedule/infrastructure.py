from __future__ import annotations

import json

from pulumi import ComponentResource, ResourceOptions
from pulumi_alicloud import ram
from pulumi_alicloud.fc import V3Trigger
from xcloudmeta.centre import Overlay
from xcloudmeta.centre.namespace import Namespace
from xlog.stream.stream import LogStream


class ScheduleInfra(ComponentResource):
    """
    定时任务基础设施组件: finconnect-schedule

    管理以下资源：
    - 定时任务相关资源

    """

    def __init__(
        self,
        name: str,
        overlay: Overlay,
        logstream: LogStream,
        opts: ResourceOptions | None = None,
    ):
        super().__init__(
            "custom:alicloud:ScheduleInfra",
            name,
            None,
            opts,
        )
        self.overlay = overlay
        self.logstream = logstream

        ns = overlay.get_namespace()
        service_name = ns.get("service.name")
        schedule_ns: Namespace = ns.get("service.fc.schedule")

        trigger_role_name = f"{service_name}-trigger-role"
        self.trigger_role = ram.Role(
            resource_name=trigger_role_name,
            role_name=trigger_role_name,
            description="Role for timer triggers to invoke FC functions",
            assume_role_policy_document=json.dumps(
                {
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Effect": "Allow",
                            "Principal": {
                                "Service": [
                                    "fc.aliyuncs.com",
                                    # "acs.aliyuncs.com",
                                ]
                            },
                        }
                    ],
                    "Version": "1",
                }
            ),
        )

        # 授予调用函数的权限
        trigger_policy = ram.Policy(
            resource_name=f"{service_name}-trigger-policy",
            policy_name=f"{service_name}-trigger-policy",
            description="Allow triggers to invoke FC functions",
            policy_document=json.dumps(
                {
                    "Statement": [
                        {
                            "Action": [
                                "fc:InvokeFunction",
                            ],
                            "Effect": "Allow",
                            "Resource": "*",
                        }
                    ],
                    "Version": "1",
                }
            ),
        )

        full_extract_weekdays_ns = schedule_ns.get("finconnect-full-extract-weekdays")
        full_extract_weekdays_enabled = full_extract_weekdays_ns.get("enabled")
        full_extract_weekdays_name = full_extract_weekdays_ns.get("name")
        full_extract_weekdays_cron = full_extract_weekdays_ns.get("cron")
        full_extract_weekdays_function = full_extract_weekdays_ns.get("function_name")
        self.full_extract_weekdays_trigger = V3Trigger(
            resource_name=full_extract_weekdays_name,
            trigger_name=full_extract_weekdays_name,
            qualifier="LATEST",
            function_name=full_extract_weekdays_function,
            trigger_type="timer",
            invocation_role=self.trigger_role.arn,
            trigger_config=json.dumps(
                {
                    "cronExpression": full_extract_weekdays_cron,
                    "enable": full_extract_weekdays_enabled,
                    "payload": json.dumps(
                        {
                            "sources": [
                                "tushare_stock_companies",
                                "tushare_stock_profiles",
                                "tushare_index_profiles",
                                "tushare_stock_adjfactor",
                                "tushare_stock_ipo",
                                "tushare_stock_premarket",
                                "tushare_stock_pricerange",
                                "tushare_stock_sectiondayline",
                                "tushare_stock_sectionmonthline",
                                "tushare_stock_sectionweekline",
                                "tushare_stock_st",
                                "tushare_stock_st_detail",
                                "tushare_stock_suspend",
                                "tushare_stock_techfactor",
                                "tushare_stock_capflow",
                                "tushare_stock_capflowconceptdc",
                                "tushare_stock_capflowconceptths",
                                "tushare_stock_capflowdc",
                                "tushare_stock_capflowths",
                                "tushare_stock_capflowindustryths",
                                "tushare_stock_capflowmarketdc",
                                "tushare_stock_compcashflow",
                                "tushare_stock_compdisclosuredate",
                                "tushare_stock_compexpress",
                                "tushare_stock_compfinindex",
                                "tushare_stock_compforecast",
                                "tushare_stock_compincome",
                                "tushare_stock_compliability",
                                "tushare_stock_compprofit",
                                "tushare_index_maincomposition",
                                "tushare_index_mainsectiondayline",
                            ],
                            "provider": "tushare",
                            "output_names": ["oss-main"],
                            "params": {},
                            "wait": True,
                            "offset": 0,
                        }
                    ),
                }
            ),
            opts=ResourceOptions(
                parent=self,
                depends_on=[self.trigger_role, trigger_policy],
            ),
        )
        logstream.log(message=f"Schedule {full_extract_weekdays_name} created OK")

        premarket_extract_weekdays_ns = schedule_ns.get("finconnect-premarket-extract-weekdays")
        premarket_extract_weekdays_enabled = premarket_extract_weekdays_ns.get("enabled")
        premarket_extract_weekdays_name = premarket_extract_weekdays_ns.get("name")
        premarket_extract_weekdays_cron = premarket_extract_weekdays_ns.get("cron")
        premarket_extract_weekdays_function = premarket_extract_weekdays_ns.get("function_name")
        self.premarket_extract_weekdays_trigger = V3Trigger(
            resource_name=premarket_extract_weekdays_name,
            trigger_name=premarket_extract_weekdays_name,
            qualifier="LATEST",
            function_name=premarket_extract_weekdays_function,
            trigger_type="timer",
            invocation_role=self.trigger_role.arn,
            trigger_config=json.dumps(
                {
                    "cronExpression": premarket_extract_weekdays_cron,
                    "enable": premarket_extract_weekdays_enabled,
                    "payload": json.dumps(
                        {
                            "sources": [
                                "tushare_stock_premarket",
                            ],
                            "provider": "tushare",
                            "output_names": ["oss-main"],
                            "params": {},
                            "wait": True,
                            "offset": 0,
                        }
                    ),
                }
            ),
            opts=ResourceOptions(
                parent=self,
                depends_on=[self.trigger_role, trigger_policy],
            ),
        )
        logstream.log(message=f"Schedule {full_extract_weekdays_name} created OK")

        self.register_outputs_bookmark = {}
        self.register_outputs(self.register_outputs_bookmark)
        logstream.log(message="Schedule backend initialization complete")
