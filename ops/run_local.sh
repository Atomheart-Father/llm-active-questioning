#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
python -m src.config.verify --config configs/train_local.yaml
python -m ops.make_min_data || true
python -m src.core.launch --config configs/train_local.yaml 2>&1 | tee -a logs/train.log
