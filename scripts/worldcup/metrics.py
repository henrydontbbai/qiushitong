from __future__ import annotations

import math
from typing import Iterable, Mapping

OUTCOMES = ("home_win", "draw", "away_win")


def _validated_probabilities(probabilities: Mapping[str, float]) -> dict[str, float]:
    values = {key: float(probabilities.get(key, 0.0)) for key in OUTCOMES}
    if any(value < 0 or value > 1 for value in values.values()):
        raise ValueError("概率必须在 0 到 1 之间")
    total = sum(values.values())
    if total <= 0:
        raise ValueError("概率合计必须大于 0")
    return {key: value / total for key, value in values.items()}


def _validate_outcome(actual_result: str) -> str:
    if actual_result not in OUTCOMES:
        raise ValueError("真实结果必须是 home_win、draw 或 away_win")
    return actual_result


def brier_score(probabilities: Mapping[str, float], actual_result: str) -> float:
    probs = _validated_probabilities(probabilities)
    actual = _validate_outcome(actual_result)
    return sum((probs[key] - (1.0 if key == actual else 0.0)) ** 2 for key in OUTCOMES)


def log_loss(probabilities: Mapping[str, float], actual_result: str, epsilon: float = 1e-15) -> float:
    probs = _validated_probabilities(probabilities)
    actual = _validate_outcome(actual_result)
    probability = min(max(probs[actual], epsilon), 1.0)
    return -math.log(probability)


def ranked_probability_score(probabilities: Mapping[str, float], actual_result: str) -> float:
    probs = _validated_probabilities(probabilities)
    actual = _validate_outcome(actual_result)
    cumulative_prediction = 0.0
    cumulative_actual = 0.0
    total = 0.0
    for key in OUTCOMES[:-1]:
        cumulative_prediction += probs[key]
        cumulative_actual += 1.0 if key == actual else 0.0
        total += (cumulative_prediction - cumulative_actual) ** 2
    return total / (len(OUTCOMES) - 1)


def expected_calibration_error(samples: Iterable[Mapping], bucket_count: int = 10) -> dict:
    if bucket_count <= 0:
        raise ValueError("bucket_count 必须大于 0")
    buckets = [
        {"bucket": idx + 1, "lower": idx / bucket_count, "upper": (idx + 1) / bucket_count, "count": 0, "confidence_sum": 0.0, "accuracy_sum": 0.0}
        for idx in range(bucket_count)
    ]
    total = 0
    for sample in samples:
        probs = _validated_probabilities(sample.get("probabilities", {}))
        actual = _validate_outcome(str(sample.get("actual_result")))
        predicted = max(OUTCOMES, key=lambda key: probs[key])
        confidence = probs[predicted]
        bucket_index = min(bucket_count - 1, int(confidence * bucket_count))
        bucket = buckets[bucket_index]
        bucket["count"] += 1
        bucket["confidence_sum"] += confidence
        bucket["accuracy_sum"] += 1.0 if predicted == actual else 0.0
        total += 1

    ece = 0.0
    output_buckets = []
    for bucket in buckets:
        count = bucket["count"]
        avg_confidence = bucket["confidence_sum"] / count if count else 0.0
        accuracy = bucket["accuracy_sum"] / count if count else 0.0
        if total:
            ece += (count / total) * abs(accuracy - avg_confidence)
        output_buckets.append({
            "bucket": bucket["bucket"],
            "range": [round(bucket["lower"], 4), round(bucket["upper"], 4)],
            "count": count,
            "avg_confidence": round(avg_confidence, 6),
            "accuracy": round(accuracy, 6),
            "gap": round(abs(accuracy - avg_confidence), 6),
        })
    return {
        "bucket_count": bucket_count,
        "sample_count": total,
        "ece": round(ece, 6),
        "buckets": output_buckets,
    }
