PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
ENV_FILE ?= .env

# Read APP_HOST / APP_PORT from .env (do not `include` .env —
# bcrypt hashes contain `$` and break Make).
APP_HOST := $(shell sed -n 's/^APP_HOST=//p' $(ENV_FILE) 2>/dev/null)
APP_PORT := $(shell sed -n 's/^APP_PORT=//p' $(ENV_FILE) 2>/dev/null)
APP_HOST := $(if $(APP_HOST),$(APP_HOST),127.0.0.1)
APP_PORT := $(if $(APP_PORT),$(APP_PORT),8000)

.PHONY: venv install refresh doctor clean-wheelhouse clean-venv \
	reinstall run migrate

venv:
	$(PYTHON) -m venv $(VENV)

install: upgrade-pip
	pipi

offline-install: upgrade-pip
	$(VENV)/bin/python -m pip install --no-index \
		--find-links $$HOME/.local/pip/wheelhouse \
		-r requirements.txt

upgrade-pip:
	$(VENV)/bin/python -m pip install --upgrade pip wheel \
		"setuptools>=40.8.0,<82" --timeout 120

refresh:
	pipi-refresh

doctor:
	pipi-doctor

clean-wheelhouse:
	pipi-clean

clean-venv:
	rm -rf $(VENV)

reinstall: clean-venv venv install

migrate:
	$(VENV_PYTHON) -m alembic upgrade head

run: migrate
	@echo "Starting on http://$(APP_HOST):$(APP_PORT) (from $(ENV_FILE))"
	$(VENV_PYTHON) -m uvicorn app.main:app \
		--reload --host $(APP_HOST) --port $(APP_PORT)
