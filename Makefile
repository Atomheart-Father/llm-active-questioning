.PHONY: preflight run resume test failpack

preflight:
	python -m src.config.verify --config configs/train_local.yaml

run:
	python -m ops.make_min_data || true
	python -m src.core.launch --config configs/train_local.yaml | tee -a logs/train.log

resume:
	python -m src.core.launch --config configs/train_local.yaml --resume checkpoints/local/latest | tee -a logs/train.log

test:
	pytest -q

failpack:
	tar -czf reports/FAIL_$(shell date +%Y%m%d_%H%M%S).tgz logs reports configs || true
