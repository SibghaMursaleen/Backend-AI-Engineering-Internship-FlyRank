import os
import json
import sys
from fastapi.testclient import TestClient

# Ensure workspace is in Python path so imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import app
from src.config import settings

def run_evaluations():
    # Load cases
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cases_path = os.path.join(base_dir, "cases.json")
    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    client = TestClient(app)
    
    print("=" * 60)
    print("           AI JOB NORMALIZER EVALUATION RUNNER")
    print("=" * 60)
    print(f"Mode: {'STUB MODE (Deterministic Mock)' if settings.llm_stub else 'REAL LLM MODE (OpenRouter)'}")
    print(f"Model configured: {settings.openrouter_model}")
    print(f"LLM Enabled: {settings.llm_enabled}")
    print("=" * 60)

    passed_count = 0
    total_count = len(cases)

    for i, case in enumerate(cases, 1):
        label = case["label"]
        input_text = case["input"]
        expected = case["expected"]

        response = client.post("/normalize", json={"text": input_text})
        status_code = response.status_code

        if status_code != 200:
            print(f"[{i}/{total_count}] Label: {label} | Input: '{input_text}'")
            print(f"      Result: FAILED (HTTP Status {status_code})")
            print(f"      Detail: {response.text}")
            print("-" * 60)
            continue

        data = response.json()
        actual_title = data["canonical_title"]
        actual_level = data["level"]
        actual_confidence = data["confidence"]
        actual_reason = data["reason"]

        expected_titles = expected["canonical_title"]
        expected_levels = expected["level"]

        title_match = actual_title in expected_titles
        level_match = actual_level in expected_levels

        if title_match and level_match:
            result = "PASSED"
            passed_count += 1
        else:
            result = "FAILED"

        print(f"[{i}/{total_count}] Label: {label} | Input: '{input_text}'")
        print(f"      Expected Title: {expected_titles} | Actual: '{actual_title}' ({'MATCH' if title_match else 'MISMATCH'})")
        print(f"      Expected Level: {expected_levels} | Actual: '{actual_level}' ({'MATCH' if level_match else 'MISMATCH'})")
        print(f"      Confidence: {actual_confidence:.2f} | Reason: '{actual_reason}'")
        print(f"      Status: {result}")
        print("-" * 60)

    score_pct = (passed_count / total_count) * 100
    print("SUMMARY")
    print(f"  Total Cases: {total_count}")
    print(f"  Passed     : {passed_count}")
    print(f"  Failed     : {total_count - passed_count}")
    print(f"  Accuracy   : {score_pct:.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    run_evaluations()
