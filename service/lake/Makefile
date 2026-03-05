# Makefile for Pulumi Deployment
SERVICE_NAME := $(shell grep '^name' service.toml | head -1 | cut -d '"' -f2)
SERVICE_ALIAS := $(shell grep '^alias' service.toml | head -1 | cut -d '"' -f2)
SERVICE_VERS := $(shell grep '^version' service.toml | head -1 | cut -d '"' -f2)
SERVICE_FULL_NAME := $(SERVICE_NAME)@$(SERVICE_ALIAS)
CONDA_ENV := app-yntcloud
PLATFORM_NAME := ynt-cloud

# Default environment (can be overridden: make deploy ENV=prod)
ENV ?= prod

# Stack naming: <platform_name>-<environ_code>-<service_name>-stack
# Example: ynt-cloud-prod-lake-stack
STACK := $(PLATFORM_NAME)-$(ENV)-$(SERVICE_NAME)-stack

# Colors for output
COLOR_RESET := \033[0m
COLOR_GREEN := \033[32m
COLOR_YELLOW := \033[33m
COLOR_BLUE := \033[34m
COLOR_RED := \033[31m

.PHONY: \
	help \
	login \
	list \
	init \
	deploy \
	destroy \
	preview \
	show \
	config \
	refresh \
	clean

# Default target
help:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Pulumi$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_GREEN)Basic Usage:$(COLOR_RESET)"
	@echo "  make <command> ENV=<env>    - Run command for specified environment"
	@echo "  make <command>              - Run command for default environment ($(ENV))"
	@echo ""
	@echo "$(COLOR_GREEN)Environments:$(COLOR_RESET)"
	@echo "  ENV=prod                    - Production environment"
	@echo "  ENV=test                    - Testing environment"
	@echo "  ENV=dev                     - Development environment"
	@echo ""
	@echo "$(COLOR_GREEN)Stack Info:$(COLOR_RESET)"
	@echo "  Current stack: $(STACK)"
	@echo "  Format: <platform_name>-<environ_code>-<service_name>-stack"
	@echo ""
	@echo "$(COLOR_GREEN)Common Commands:$(COLOR_RESET)"
	@echo "  make login                  - Login to Pulumi (local backend)"
	@echo "  make list                   - List all stacks"
	@echo "  make init [ENV=prod]        - Initialize stack"
	@echo "  make deploy [ENV=prod]      - Deploy infrastructure"
	@echo "  make preview [ENV=prod]     - Preview changes"
	@echo "  make show [ENV=prod]        - Show stack status and outputs"
	@echo "  make config [ENV=prod]      - Show stack configuration"
	@echo "  make refresh [ENV=prod]     - Refresh stack state"
	@echo "  make destroy [ENV=prod]     - Destroy infrastructure"
	@echo "  make clean                  - Clean local cache"
	@echo ""
	@echo "$(COLOR_GREEN)Quick Shortcuts:$(COLOR_RESET)"
	@echo "  make deploy-prod            - Deploy to production"
	@echo "  make deploy-dev             - Deploy to development"
	@echo "  make show-prod              - Show production status"
	@echo "  make show-dev               - Show development status"
	@echo ""

# List all stacks
list:
	@echo "$(COLOR_BLUE)Available stacks:$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack ls

# Login to Pulumi
login:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Login local backend ...$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi login --local
	@echo "$(COLOR_GREEN)$(SERVICE_FULL_NAME) - ✅ Login OK$(COLOR_RESET)"

# Initialize stack
init: login
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Initializing $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack init $(STACK) 2>/dev/null || \
		echo "$(COLOR_YELLOW)Stack $(STACK) already exists$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack select $(STACK)
	@echo "$(COLOR_GREEN)$(SERVICE_FULL_NAME) - ✅ $(STACK) ready$(COLOR_RESET)"

# Deploy to environment
deploy:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Deploying: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi up --yes
	@echo "$(COLOR_GREEN)$(SERVICE_FULL_NAME) - ✅ $(STACK) deployed OK $(COLOR_RESET)"
	@$(MAKE) output ENV=$(ENV)

# Destroy resources
destroy:
	@echo "$(COLOR_RED)$(SERVICE_FULL_NAME) - Destroying $(STACK) [ENV=$(ENV)] ⚠️ $(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Press Ctrl+C to cancel, or Enter to continue...$(COLOR_RESET)"
	@read confirm
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi destroy --yes
	@echo "$(COLOR_GREEN)$(SERVICE_FULL_NAME) - ✅ $(STACK) destroyed OK $(COLOR_RESET)"

# Preview changes
preview:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Preview: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi preview

# Show stack status
show:
	@echo "$(COLOR_BLUE)Stack status: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack --show-ids
	@echo ""
	@echo "$(COLOR_GREEN)Stack outputs:$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack output

# Export outputs to YAML file
output:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Exporting outputs: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack select $(STACK)
	@echo "Outputs:" > Outputs.yaml
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack output --json 2>/dev/null | python3 -c "import sys, json, yaml; data = json.load(sys.stdin); [print(f'  {k}: \"{v}\"' if isinstance(v, str) else f'  {k}: {v}') for k, v in sorted(data.items())]" >> Outputs.yaml 2>/dev/null || true
	@echo "$(COLOR_GREEN)$(SERVICE_FULL_NAME) - ✅ Outputs exported to Outputs.yaml$(COLOR_RESET)"

# Show configuration
config:
	@echo "$(COLOR_BLUE)Configuration: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi config

# Refresh stack state
refresh:
	@echo "$(COLOR_BLUE)Refreshing stack: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && conda run -n $(CONDA_ENV) pulumi refresh --yes
	@echo "$(COLOR_GREEN)✅ $(STACK) state refreshed OK $(COLOR_RESET)"

# Clean local cache
clean:
	@echo "$(COLOR_BLUE)Cleaning ... $(COLOR_RESET)"
	@rm -rf .pulumi/
	@rm -rf __pycache__/
	@rm -rf backend/__pycache__/
	@rm -rf backend/storage/__pycache__/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(COLOR_GREEN)✅ Cleaning OK $(COLOR_RESET)"

# linting and testing targets can be added here as needed
lint:
	@echo "$(COLOR_BLUE)Linting ... $(COLOR_RESET)"
	@conda run -n $(CONDA_ENV) ruff format .
	@conda run -n $(CONDA_ENV) ruff check . --fix
	@conda run -n $(CONDA_ENV) ruff check .
	@echo "$(COLOR_GREEN)✅ Linting OK $(COLOR_RESET)"
