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
            qualifier="LATEST", body=bytes("{}", encoding="utf-8")
        ),
    )
    code = response.status_code
    body = response.to_map()["body"]
    data = json.load(body)
    print(code)
    print(data)  # Function output
except Exception as e:
    print(e)
