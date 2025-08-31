#!/usr/bin/env python3
"""
权重模式单测
"""

import json, os
import pytest
from src.evaluation.weights_loader import load_weights
from src.evaluation.exceptions import WeightsSchemaError

def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w") as f: json.dump(data, f)

def test_alias_and_normalization(tmp_path):
    p = tmp_path/"weights.json"
    write(p, {"weights":{"rules_score":0.3,"logic_rigor":0.3,"question_quality":0.2,"reasoning_completeness":0.1,"natural_interaction":0.1}})
    w = load_weights(str(p))
    assert abs(sum(w.values())-1.0)<1e-9
    assert "rules" in w and w["rules"]>0

def test_missing_keys_raises(tmp_path):
    p = tmp_path/"weights.json"
    write(p, {"rules":1.0})
    with pytest.raises(WeightsSchemaError):
        load_weights(str(p))

def test_all_zero_raises(tmp_path):
    p = tmp_path/"weights.json"
    write(p, {"logic_rigor":0.0,"question_quality":0.0,"reasoning_completeness":0.0,"natural_interaction":0.0,"rules":0.0})
    with pytest.raises(WeightsSchemaError):
        load_weights(str(p))

def test_deprecation_warning(tmp_path):
    import warnings
    p = tmp_path/"weights.json"
    write(p, {"rules_score":0.3,"logic_rigor":0.3,"question_quality":0.2,"reasoning_completeness":0.1,"natural_interaction":0.1})
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        warnings.filterwarnings("ignore", category=ResourceWarning)  # Ignore resource warnings
        load_weights(str(p))
        # Find the deprecation warning
        deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
        assert len(deprecation_warnings) > 0
        assert "deprecated" in str(deprecation_warnings[0].message)
