from __future__ import annotations

from pathlib import Path

import pulumi
from backend.component import Backend
from xcloudmeta.centre import Centre, Overlay
from xlog import ColorTree, LogStream

# Initialize logging stream
current = Path(__file__).parent.name
stream = LogStream(
    name=current,
    level="INFO",
    format=ColorTree(),
    verbose=True,
)
stream.log(f"Starting Pulumi deployment for service: {current}")

# Initialize Pulumi config
config = pulumi.Config()

# Initialize centre
centre = Centre(root="../../")

# Get Pulumi stack name
# Expected format: <platform_name>-<environ_code>-<service_name>-stack
# Example: ynt-cloud-prod-lake-stack
stack_name = pulumi.get_stack()
stream.log(f"Pulumi stack: {stack_name}")

try:
    # Try to retrieve from Pulumi config first
    platform_name = config.get("platform")
    environ_name = config.get("environ")
    service_name = config.get("service")

    if not platform_name or not environ_name or not service_name:
        # Parse from stack name to extract platform, environ, and service
        # Stack name format: {platform_name}-{environ_code}-{service_name}-stack
        # Example: ynt-cloud-prod-lake-stack
        # Remove '-stack' suffix
        if not stack_name.endswith("-stack"):
            raise ValueError(
                f"Invalid stack name format: {stack_name}. Expected format: <plt>-<env>-<svc>-stack"
            )

        stack_base = stack_name[:-6]  # Remove '-stack'

        # Try to match platform name from the beginning
        platform = None
        for plat in centre.list_platform():
            plat_name = plat.get_name()
            if stack_base.startswith(plat_name + "-"):
                platform = plat
                platform_name = plat_name
                # Remove platform name and following dash
                remaining = stack_base[len(plat_name) + 1 :]
                break

        if not platform:
            raise ValueError(
                f"Could not identify platform from stack name: {stack_name}. "
                f"Available platforms: {[p.name for p in centre.list_platform()]}"
            )

        # Try to match service name from the end of remaining string
        service = None
        service_name = None
        for svc in centre.list_service():
            svc_name = svc.get_name()
            if remaining.endswith("-" + svc_name):
                service = svc
                service_name = svc_name
                # Remove service name and preceding dash
                environ_code = remaining[: -len(svc_name) - 1]
                break

        if not service:
            # Fallback: use current directory as service name
            # Assume remaining is: {environ_code}-{service_name}
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

        # Verify service matches current directory
        if service_name != current:
            stream.log(
                message=f"Warning: Stack service '{service_name}' != directory '{current}'",
                level="WARNING",
            )

        # Find environ by code
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
        # Config provided, get modules by name
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

    # Create overlay
    overlay: Overlay = centre.overlay(
        platform=platform.name,
        environ=environ.name,
        service=current,
    )
    overlay.validate()

    # Verify stack name matches expected format
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

    # Create backend resources using stack ID from overlay
    backend = Backend(
        name=overlay.get_stack_id(),
        overlay=overlay,
        logstream=stream,
    )

    # Export stack outputs
    pulumi.export("stack_id", overlay.get_stack_id())
    pulumi.export("platform_name", platform_name)
    pulumi.export("platform_code", platform.get_code())
    pulumi.export("environ_name", environ_name)
    pulumi.export("environ_code", environ.get_code())
    pulumi.export("service_name", current)
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
