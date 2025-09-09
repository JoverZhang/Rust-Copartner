run-e2e-tests-interactive:
	cd e2e_tests && ./run_interactive.sh

run-e2e-tests-prompt:
	cd e2e_tests && ./run_prompt.sh

run-e2e-tests: run-e2e-tests-interactive run-e2e-tests-prompt

generate-complexity-report:
	mkdir -p rust/tests/reports
	cargo run --bin complexity_cli -- dir --path rust/tests/samples --export rust/tests/reports/complexity_report.json
