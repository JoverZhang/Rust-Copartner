run-e2e-tests-interactive:
	cd e2e_tests && ./run_interactive.sh

run-e2e-tests-prompt:
	cd e2e_tests && ./run_prompt.sh

run-e2e-tests: run-e2e-tests-interactive run-e2e-tests-prompt

generate-complexity-report:
	mkdir -p rust/tests/reports
	cargo run --bin complexity_cli -- dir --path rust/tests/samples --export rust/tests/reports/complexity_report.json

run-rust-project-analyzer-test:
	cargo run --bin project_analyzer -- path rust/tests/samples --repo_id test/repo --out rust/tests/reports/project_analyzer_test.json
