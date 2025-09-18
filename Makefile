run-e2e-tests-interactive:
	cd e2e_tests && ./run_interactive.sh

run-e2e-tests-prompt:
	cd e2e_tests && ./run_prompt.sh

run-all-e2e-tests: \
		run-e2e-tests-interactive \
		run-e2e-tests-prompt
	@echo "[PASS] All e2e tests passed"


run-indexer-test-project-analyzer:
	# cargo run --bin project_analyzer -- --path rust/tests/fixtures --repo-id test/repo --out rust/tests/fixtures/vectors.json
	cargo run --bin project_analyzer -- --path rust/tests/fixtures --repo-id test/repo | jq > rust/tests/fixtures/vectors.json


run-indexer-test-build-index:
	python -m python.src.bin.build --input ./rust/tests/fixtures/vectors.json

run-indexer-test-retrieval:
	python -m python.src.bin.retrieval "Point struct" --limit 5 --brief

run-all-indexer-tests: \
		run-indexer-test-project-analyzer \
		run-indexer-test-build-index \
		run-indexer-test-retrieval
	@echo "[PASS] All indexer tests passed"


generate-complexity-report:
	mkdir -p rust/tests/reports
	cargo run --bin complexity_cli -- dir --path rust/tests/samples --export rust/tests/reports/complexity_report.json
