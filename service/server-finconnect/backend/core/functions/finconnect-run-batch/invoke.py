import json
import os
from pathlib import Path

from alibabacloud_fc20230330 import models as FCModels
from alibabacloud_fc20230330.client import Client as FCClient
from alibabacloud_tea_openapi import models as OpenApiModels

access_key_id = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID")
access_key_secret = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
region_id = os.environ.get("REGION_ID")
endpoint = f"fcv3.{region_id}.aliyuncs.com"
function_name = Path(__file__).parent.name
event = {
    "payload": {
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
        "use_cache": True,
        "date_offset": 0,
        "conn_type": "private",
        "wait": True,
    }
}
read_timeout_minutes = 15 * 60 * 1000  # 15 minutes
conn_timeout_minutes = 15 * 60 * 1000  # 15 minutes

config = OpenApiModels.Config(
    access_key_id=access_key_id,
    access_key_secret=access_key_secret,
    region_id=region_id,
    endpoint=endpoint,
    read_timeout=read_timeout_minutes,
    connect_timeout=conn_timeout_minutes,
)
client = FCClient(config)
try:
    response: FCModels.InvokeFunctionResponse = client.invoke_function(
        function_name=function_name,
        request=FCModels.InvokeFunctionRequest(
            qualifier="LATEST",
            body=bytes(json.dumps(event), encoding="utf-8"),
        ),
    )
    code = response.status_code
    body = response.to_map()["body"]
    data = json.load(body)
    print(code)
    print(data)  # Function output
except Exception as e:
    print(e)
