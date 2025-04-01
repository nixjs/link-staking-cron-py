.PHONY: install run

install:
	@echo "Installing dependencies..."
	pip3 install -r requirements.txt

run:
	@echo "Checking if dependencies are installed..."
	@pip show web3 > /dev/null 2>&1 || (echo "Dependencies not found. Installing..." && $(MAKE) install)
	@echo "Running the script..."
	python3 src/cron.py

cron: run