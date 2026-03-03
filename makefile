# Makefile for 应天云 (YntCloud) Application
APP_NAME := $(shell grep '^name' pyproject.toml | head -1 | cut -d '"' -f2)
APP_ALIA := 应天
APP_VERS := $(shell grep '^version' pyproject.toml | head -1 | cut -d '"' -f2)
APP_PATH := $(abspath .)
CONDA_ENV := $(APP_NAME)
CONDA_ENV_FILE := environment.yml

.PHONY: \
	conda/install \
	conda/activate \
	conda/deactivate \
	app/help \
	app/detail \
	app/version

clean: app/clean

conda/install:
	@if ! conda env list | grep -qE "^$(CONDA_ENV)[[:space:]]"; then \
		echo "[app][$(APP_NAME)@$(APP_ALIA)] create env '$(CONDA_ENV)'"; \
		conda env create -f $(CONDA_ENV_FILE); \
	else \
		echo "[app][$(APP_NAME)@$(APP_ALIA)] update env '$(CONDA_ENV)'"; \
		conda env update -n $(CONDA_ENV) -f $(CONDA_ENV_FILE); \
	fi
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'conda' environment installed ✅ "

conda/activate:
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] activate conda by 'conda activate $(APP_NAME)'"

conda/deactivate:
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] deactivate conda by 'conda deactivate'"

pulumi/install:
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] installing 'pulumi' dependencies ..."
	@brew install pulumi
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'pulumi' dependencies installed ✅ "

pyproject/install:
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] installing 'pyproject.toml' dependencies ..."
	@conda run -n $(CONDA_ENV) python -m pip install --upgrade pip
	@conda run -n $(CONDA_ENV) sh -c 'python -m pip install ".[dev]"'
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'pyproject.toml' dependencies installed ✅ "

node/install:
	@npm install
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'node modules' installed ✅ "

node/upgrade:
	@npm update
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'node modules' upgraded ✅ "

node/uninstall:
	@rm -rf node_modules package-lock.json
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'node modules' uninstalled ✅ "

internals/install:
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] installing internal libs ..."
	@python install.py --strategy local
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] internal libs installed ✅ "

app/help:
	@echo
	@echo "$(APP_NAME) ($(APP_ALIA)) Make targets:"
	@echo "  detail            Show package name/alias"
	@echo "  version           Show current version"
	@echo "  conda/install     Create or update conda env from environment.yml"
	@echo "  conda/delete      Remove conda env named $(APP_NAME)"
	@echo "  conda/activate    Echo command to activate env"
	@echo

app/detail:
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] Name: $(APP_NAME)"
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] Alias: $(APP_ALIA)"
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] Version: $(APP_VERS)"

app/version:
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] Current version:" $(APP_VERS)

app/clean:
	@rm -rf build dist *.egg-info
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'build artifacts' cleaned ✅ "

	@rm -rf .pytest_cache
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'pytest caches' cleaned ✅ "

	@rm -rf .vendors
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'vendors caches' cleaned ✅ "

	@rm -rf .ruff_cache
	@rm -rf .benchmarks
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'ruff/benchmarks caches' cleaned ✅ "
	
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".DS_Store" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'python caches' cleaned ✅ "

	@find . -type d -name ".cdk.out" -exec rm -rf {} +
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'cdk outputs' cleaned ✅ "

app/test:
	pytest -q
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'application' tests passed ✅ "

app/lint:
	@ruff format .
	@ruff check . --fix
	@ruff check .
	@echo "[app][$(APP_NAME)@$(APP_ALIA)] 'application' lint checked ✅ "

app/init:
	@pulumi stack init --stack $(APP_NAME) --secrets-provider "passphrase" || true

