from __future__ import annotations

from pathlib import Path

import pulumi
from backend.component import Backend
from xcloudmeta.centre import Centre, Overlay
from xlog import ColorTree, LogStream

# Initialize logging stream
stream = LogStream(
    name="lake",
    level="INFO",
    format=ColorTree(),
    verbose=True,
)

current = Path(__file__).parent.name
stream.log(f"Starting Pulumi deployment for service: {current}")

# Initialize Pulumi config
config = pulumi.Config()

# Initialize centre
centre = Centre(root="../../")

# Get Pulumi stack name
# Expected format: <platform>-<environ_code>-<service>
# Example: ynt-cloud-prod-lake
stack_name = pulumi.get_stack()
stream.log(f"Pulumi stack: {stack_name}")

try:
    # Try to retrieve from Pulumi config first
    platform_name = config.get("platform")
    environ_name = config.get("environ")

    if not platform_name or not environ_name:
        # Parse from stack name: ynt-cloud-prod-lake
        # Parts: [ynt, cloud, prod, lake]
        parts = stack_name.split("-")

        if len(parts) != 4:
            raise ValueError(
                f"Invalid stack name format: {stack_name}. "
                f"Expected: <platform>-<environ_code>-<service> (e.g., ynt-cloud-prod-lake)"
            )

        # Parse: ynt-cloud-prod-lake
        platform_name = f"{parts[0]}-{parts[1]}"  # ynt-cloud
        environ_code = parts[2]  # prod
        service_name = parts[3]  # lake

        # Verify service name matches current directory
        if service_name != current:
            stream.log(
                message=f"Warning: Stack service '{service_name}' != directory '{current}'",
                level="WARNING",
            )

        # Map environ_code to full environ name
        # e.g., "prod" -> "ynt-trading-prod"
        environ_code_map = {
            "prod": "ynt-trading-prod",
            "dev": "ynt-trading-dev",
            "staging": "ynt-trading-staging",
        }

        environ_name = environ_code_map.get(environ_code)
        if not environ_name:
            raise ValueError(
                f"Unknown environ code '{environ_code}'. Available: {list(environ_code_map.keys())}"
            )

    stream.log(
        message="Resolved configuration",
        context={
            "platform": platform_name,
            "environ": environ_name,
            "service": current,
        },
    )

    # Get platform and environ from centre
    platform = centre.get_platform(platform_name)
    environ = centre.get_environ(environ_name)

    # Create overlay
    overlay: Overlay = centre.overlay(
        platform=platform.name,
        environ=environ.name,
        service=current,
    )
    overlay.validate()

    stream.log(
        message="Overlay built successfully",
        context={
            "account": environ.get_account(),
            "region": environ.get_region(),
        },
    )
    stream.log(
        message="Show overlay:",
        level="DEBUG",
        context=overlay.describe(),
    )

    # Create backend resources
    backend = Backend(
        name=overlay.get_stack_id(),
        overlay=overlay,
        logstream=stream,
    )

    # Export stack outputs
    pulumi.export("platform", platform_name)
    pulumi.export("environ", environ_name)
    pulumi.export("service", current)
    pulumi.export("region", environ.get_region())
    pulumi.export("account", environ.get_account())

    # Export bucket information - ADD MORE INFO AS NEEDED
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
