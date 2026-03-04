# Makefile for Pulumi Deployment
SERVICE_NAME := network
SERVICE_ALIAS := 驿传
SERVICE_FULL_NAME := $(SERVICE_NAME)@$(SERVICE_ALIAS)
PLATFORM_NAME := ynt-cloud

# Default environment (can be overridden: make deploy ENV=prod)
ENV ?= prod

# Stack naming: <platform_name>-<environ_code>-<service_name>-stack
# Example: ynt-cloud-prod-network-stack
STACK := $(PLATFORM_NAME)-$(ENV)-$(SERVICE_NAME)-stack

# Aliyun configuration
REGION := cn-shanghai

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
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack ls

# Login to Pulumi
login:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Login local backend ...$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi login --local
	@echo "$(COLOR_GREEN)$(SERVICE_FULL_NAME) - ✅ Login OK$(COLOR_RESET)"

# Initialize stack
init: login
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Initializing $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack init $(STACK) 2>/dev/null || \
		echo "$(COLOR_YELLOW)Stack $(STACK) already exists$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack select $(STACK)
	@echo "$(COLOR_GREEN)$(SERVICE_FULL_NAME) - ✅ $(STACK) ready$(COLOR_RESET)"

# Deploy to environment
deploy:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Deploying: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi up --yes
	@echo "$(COLOR_GREEN)$(SERVICE_FULL_NAME) - ✅ $(STACK) deployed OK $(COLOR_RESET)"
	@$(MAKE) output ENV=$(ENV)

# Destroy resources
destroy:
	@echo "$(COLOR_RED)$(SERVICE_FULL_NAME) - WARNING: Destroying $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@echo "$(COLOR_RED)This will delete all network infrastructure!$(COLOR_RESET)"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ]
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi destroy --yes
	@echo "$(COLOR_YELLOW)$(SERVICE_FULL_NAME) - Stack destroyed$(COLOR_RESET)"

# Preview changes
preview:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Preview: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi preview

# Show stack status
show:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Status: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack output

# Export outputs to YAML file
output:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Exporting outputs: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack select $(STACK)
	@echo "Outputs:" > Outputs.yaml
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack output --json 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); [print(f'  {k}: \"{v}\"' if isinstance(v, str) else f'  {k}: {v}') for k, v in sorted(data.items())]" >> Outputs.yaml 2>/dev/null || true
	@echo "$(COLOR_GREEN)$(SERVICE_FULL_NAME) - ✅ Outputs exported to Outputs.yaml$(COLOR_RESET)"

# Show stack configuration
config:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Config: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi config

# Refresh stack state
refresh:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Refresh: $(STACK) [ENV=$(ENV)]$(COLOR_RESET)"
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi stack select $(STACK)
	@export PULUMI_CONFIG_PASSPHRASE="" && pulumi refresh --yes

# Clean local cache
clean:
	@echo "$(COLOR_BLUE)$(SERVICE_FULL_NAME) - Cleaning...$(COLOR_RESET)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "$(COLOR_GREEN)$(SERVICE_FULL_NAME) - ✅ Cleaned$(COLOR_RESET)"

# Quick shortcuts
deploy-prod:
	@$(MAKE) deploy ENV=prod

deploy-dev:
	@$(MAKE) deploy ENV=dev

show-prod:
	@$(MAKE) show ENV=prod

show-dev:
	@$(MAKE) show ENV=dev

preview-prod:
	@$(MAKE) preview ENV=prod

preview-dev:
	@$(MAKE) preview ENV=dev
