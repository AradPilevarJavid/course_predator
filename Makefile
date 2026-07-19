# what comes after the command isn't a real file on the disk.
.PHONY: run-server run-client test lint format /

run-server:
	python run_server.py

run-client:
	python run_client.py

test:
	python -m pytest

lint:
	python -m ruff check .

format:
	python -m black .
