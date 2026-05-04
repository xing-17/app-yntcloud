import json
import logging
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from alibabacloud_ecs20140526 import models as EcsModels

# Alicloud ECS SDK
from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_oos20190601 import models as OosModels

# Alicloud OOS SDK
from alibabacloud_oos20190601.client import Client as OosClient
from alibabacloud_tea_openapi import models as OpenApiModels
from alibabacloud_tea_util import models as UtilModels


def main(event, context):
    """
    FinConnect Run Batch Function

    Request schema:
    {
    "payload": {
    "sources": ["tushare_stock_companies", "tushare_stock_profiles"],
    "provider": "tushare",
    "output_names": ["oss-main"],
    "params": {},
    "use_cache": true,
    "date_offset": 0,
    "conn_type": "private",
    "wait": true
    }
    }
    """

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()
    logger.info("FC Function started OK.")

    # ----------------------------
    # Retrive session variables
    # ----------------------------
    oos_secret = os.environ.get("OOS_SECRET")
    region_id = os.environ.get("REGION_ID")
    server_name = os.environ.get("SERVER_NAME")
    timezone_area = os.environ.get("TIMEZONE_AREA", "Asia/Shanghai")

    # Retrive context credentials
    config = OpenApiModels.Config(
        access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        security_token=os.environ.get("ALIBABA_CLOUD_SECURITY_TOKEN"),
        region_id=region_id,
    )

    # ----------------------------
    # Build Alicloud clients
    # - OOS
    # - ECS:
    # ----------------------------
    oos: OosClient = OosClient(config)
    logger.info(f"OOS client built OK: region={region_id}")

    ecs: EcsClient = EcsClient(config)
    logger.info(f"ECS client built OK: region={region_id}")

    # ------------------------------------------------------
    # Load API key from OOS Secret
    # - GET: OOS secret by name
    # - GET: API key for FinConnect Server
    # - GET: API port for FinConnect Server
    # ------------------------------------------------------
    try:
        response: OosModels.GetSecretParameterResponse = oos.get_secret_parameter_with_options(
            request=OosModels.GetSecretParameterRequest(
                name=oos_secret,
                region_id=region_id,
                with_decryption=True,
            ),
            runtime=UtilModels.RuntimeOptions(autoretry=True),
        )
        secret_value: dict = json.loads(response.body.parameter.value)
        server_key = secret_value["runtime_agent_api_key"]
        server_key_mask = "***" if server_key else None
        server_api_port = secret_value["runtime_agent_api_port"]
        logger.info(f"API key retrieved OK: {server_key_mask}")
        logger.info(f"API port retrieved OK: {server_api_port}")
    except Exception as e:
        raise RuntimeError(f"OOS Secret {oos_secret} retrieve failed: {e}") from e

    # ------------------------------------------------------
    # Server Lookup
    # ------------------------------------------------------
    try:
        response: EcsModels.DescribeInstancesResponse = ecs.describe_instances_with_options(
            request=EcsModels.DescribeInstancesRequest(
                instance_name=server_name,
                region_id=region_id,
            ),
            runtime=UtilModels.RuntimeOptions(autoretry=True),
        )
        server_result = response.body.instances.instance[0]
        server_public_ip: str = server_result.public_ip_address.ip_address[0]
        logger.info(f"Server {server_name} lookup OK: public_ip={server_public_ip}")

        server_private_ip: str = server_result.vpc_attributes.private_ip_address.ip_address[0]
        logger.info(f"Server {server_name} lookup OK: private_ip={server_private_ip}")
    except Exception as e:
        raise RuntimeError(f"ECS {server_name} lookup failed: {e}") from e

    # ------------------------------------------------------
    # Parse Payload
    # ------------------------------------------------------
    try:
        event_value = json.loads(event.decode("utf-8"))
        payload = event_value.get("payload", {})
        logger.info(f"Payload recieved OK: {json.dumps(payload, indent=2)}")
        if not isinstance(payload, dict):
            payload = json.loads(payload)

        # Batch params
        sources = payload.get("sources", [])
        provider = payload.get("provider", "")
        output_names = payload.get("output_names", [])
        params = payload.get("params", {})
        use_cache = payload.get("use_cache", True)

        # Build params
        date_offset = int(payload.get("date_offset", 0))

        # Run params
        conn_type = payload.get("conn_type", "public")
        wait = payload.get("wait", False)
        timeout = int(payload.get("timeout", 21600))
        interval = int(payload.get("interval", 60))

        logger.info("Payload read OK")
    except Exception as e:
        raise RuntimeError(f"Error parsing payload: {e}") from e

    # ------------------------------------------------------
    # Build Batch and Requests payload
    # ------------------------------------------------------
    zoneinfo = ZoneInfo(timezone_area)
    now = datetime.now(zoneinfo)
    logger.info(f"Current time at {timezone_area}: {now.isoformat()} ")

    # Build server base url
    server_ip = server_public_ip if conn_type == "public" else server_private_ip
    endpoint = f"http://{server_ip}:{server_api_port}"
    logger.info(f"Server endpoint set OK: {endpoint}")

    # Api authentication
    header = {
        "X-API-Key": server_key,
        "Accept": "application/json",
    }
    session = requests.Session()
    session.headers.update(header)
    logger.info(f"API authentication header set OK: {header.keys()}")

    # Build batch request body
    if not params:
        target = now + timedelta(days=date_offset)
        date = target.strftime("%Y-%m-%d")
        params.update(
            {
                "start_date": date,
                "end_date": date,
            }
        )

    batch = {"signals": []}
    for source in sources:
        signal = {
            "provider": provider,
            "source": source,
            "output_names": output_names,
            "use_cache": use_cache,
            "params": params,
        }
        batch["signals"].append(signal)
        logger.info(f"Signal added to batch OK: {json.dumps(signal, indent=2)}")

    # ------------------------------------------------------
    # Health Check
    # - GET: /api/v2/health/check
    # ------------------------------------------------------
    health_check_path = "/api/v2/health/check"
    response: requests.Response = session.get(
        url=f"{endpoint}{health_check_path}",
        timeout=60,
    )
    if response.ok:
        logger.info(f"Server call {health_check_path} OK")
    else:
        status_code = response.status_code
        status_text = response.text
        raise RuntimeError(f"Server call {health_check_path} failed [{status_code}], {status_text}")

    # ------------------------------------------------------
    # Run Batch
    # - POST: /api/v2/fetch/submitbatch
    # ------------------------------------------------------
    batch_submit_path = "/api/v2/fetch/submitbatch"
    response: requests.Response = session.post(
        url=f"{endpoint}{batch_submit_path}",
        json=batch,
        timeout=120,
    )
    status_code = response.status_code
    if response.ok:
        result = response.json()
        batch_id = result.get("batch_id")
        logger.info(f"Batch {batch_id} submit OK")
    else:
        raise RuntimeError(f"Fail to submit batch {status_code}, {response.text}")

    # ------------------------------------------------------
    # Wait for Batch to Finish if configured
    # - GET: /api/v2/fetch/describebatch/{batch_id}
    # ------------------------------------------------------
    if wait:
        for iternum in range(timeout // interval):
            describe_batch_path = f"/api/v2/fetch/describebatch/{batch_id}"
            response = session.get(
                url=f"{endpoint}{describe_batch_path}",
                timeout=120,
            )
            if response.ok:
                result = response.json()
                metadata = result.get("batch", {})
                finished = metadata.get("finished")
                if finished is True:
                    logger.info(f"Batch {batch_id} finished OK.")
                    break
                elif finished is False:
                    logger.info(f"Batch {batch_id} not ready.")
                    logger.info(
                        f"Iteration {iternum + 1}, time elapsed = {(iternum + 1) * interval}"
                    )
                    time.sleep(interval)
                else:
                    raise RuntimeError(f"Unexpected API response: {response.text}")
            else:
                raise RuntimeError(f"Batch describe API call failed: {response.status_code}")

    return {
        "status": "ok",
        "code": 200,
        "batch_id": batch_id,
    }
