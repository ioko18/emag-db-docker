.PHONY: qc ci

qc:
	@bash scripts/quick_check.sh

ci:
	@API_WAIT_RETRIES=120 API_WAIT_SLEEP_SECS=2 bash scripts/quick_check.sh
