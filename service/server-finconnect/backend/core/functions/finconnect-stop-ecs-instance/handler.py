import json
import logging
import os
import time

from alibabacloud_ecs20140526 import models as EcsModels

# Alicloud ECS SDK
from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_tea_openapi import models as OpenApiModels
from alibabacloud_tea_util import models as UtilModels


def _describe_instance(
    ecs_client: EcsClient,
    instance_name: str,
    region_id: str,
) -> object:
    try:
        response = ecs_client.describe_instances_with_options(
            request=EcsModels.DescribeInstancesRequest(
                instance_name=instance_name,
                region_id=region_id,
            ),
            runtime=UtilModels.RuntimeOptions(autoretry=True),
        )
        instances = response.body.instances.instance
        if not instances:
            raise RuntimeError(f"No instance found '{instance_name}'")
        return instances[0]
    except Exception as e:
        raise RuntimeError(f"Fail to describe instance '{instance_name}': {e}") from e


def main(event, context):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()
    logger.info("FC Function started OK.")

    # ----------------------------
    # Retrive session variables
    # ----------------------------
    region_id = os.environ.get("REGION_ID")
    server_name = os.environ.get("SERVER_NAME")

    # Retrive context credentials
    creds = context.credentials
    config = OpenApiModels.Config(
        access_key_id=creds.access_key_id,
        access_key_secret=creds.access_key_secret,
        security_token=creds.security_token,
        region_id=region_id,
    )

    # ----------------------------
    # Build Alicloud clients
    # - ECS:
    # ----------------------------
    ecs: EcsClient = EcsClient(config)
    logger.info(f"ECS client built OK: region={region_id}")

    # ------------------------------------------------------
    # Parse Payload
    # ------------------------------------------------------
    try:
        event_value = json.loads(event.decode("utf-8"))
        payload = event_value.get("payload", {})
        logger.info(f"Payload recieved OK: {json.dumps(payload, indent=2)}")
        if not isinstance(payload, dict):
            payload = json.loads(payload)

        # Runtime params
        timeout = int(payload.get("timeout", 900))
        interval = int(payload.get("interval", 10))
        logger.info("Payload read OK")
    except Exception as e:
        raise RuntimeError(f"Error parsing payload: {e}") from e

    # ------------------------------------------------------
    # Look up instance by name
    # ------------------------------------------------------
    try:
        instance = _describe_instance(
            ecs_client=ecs,
            instance_name=server_name,
            region_id=region_id,
        )
        instance_id = instance.instance_id
        instance_status = instance.status
        logger.info(f"Instance ({instance_id}) found OK: status={instance_status}")
    except Exception as e:
        raise RuntimeError(f"Failed to find instance by name '{server_name}': {e}") from e

    if instance_status.lower() == "stopped":
        logger.info(f"Instance already stopped, SKIP: {instance_id}")
        return {
            "status": "ok",
            "instance_id": instance_id,
            "message": f"Instance {instance_id} already stopped",
        }

    # ------------------------------------------------------
    # Start instance
    # ------------------------------------------------------
    try:
        ecs.stop_instance_with_options(
            request=EcsModels.StopInstanceRequest(
                instance_id=instance_id,
            ),
            runtime=UtilModels.RuntimeOptions(autoretry=True),
        )
        logger.info(f"StartInstance sent OK: {instance_id}")
    except Exception as e:
        raise RuntimeError(f"Failed to start '{instance_id}': {e}") from e

    # ------------------------------------------------------
    # Wait instance
    # ------------------------------------------------------
    for iternum in range(timeout // interval):
        elapsed = (iternum + 1) * interval
        instance = _describe_instance(
            ecs_client=ecs,
            instance_name=server_name,
            region_id=region_id,
        )
        status = instance.status
        logger.info(f"Waiting Instance {instance_id}, iter={iternum + 1} elapsed={elapsed}s")
        if status.lower() != "stopped":
            logger.info(f"Instance {instance_id} not stopped. status={status}")
            time.sleep(interval)
        else:
            logger.info(f"Instance {instance_id} stopped, status={status}")
            break

    return {
        "status": "ok",
        "instance_id": instance_id,
        "message": f"Instance {instance_id} stopped OK",
    }


# main(event=json.dumps({
#     "payload": {
#         "timeout": 900,
#         "interval": 10,
#     }
# }).encode('utf-8'), context=None)
