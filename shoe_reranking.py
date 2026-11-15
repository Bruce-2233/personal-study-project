"""Shared scoring rules and prediction tables for the attribute rerankers."""
import hashlib
import json

import numpy as np

from shoe_retrieval import DATASET

TOP_K = 8
FIELDS = ("shoe_type", "color_primary")
METHODS = ("logistic_regression", "linear_svm")
EVALUATION_DIR = DATASET.parent / "retrieval_evaluation_merged"


def load_query_config():
    return json.loads((EVALUATION_DIR / "queries.json").read_text(encoding="utf-8-sig"))


def fixed_queries(config):
    return [query for query in config["queries"] if query["relevant_count"] >= TOP_K]


def gallery_fingerprint(vectors, sample_ids):
    digest = hashlib.sha256(json.dumps(sample_ids).encode("utf-8"))
    digest.update(np.ascontiguousarray(vectors, dtype="<f4").tobytes())
    return digest.hexdigest()


def fuse_scores(similarity, conditions, predictions, weights):
    scores = np.array(similarity, dtype=np.float64, copy=True)
    for field, weight in zip(FIELDS, weights):
        target = conditions.get(field)
        if target is not None and weight:
            classes, probabilities = predictions[field]
            scores += weight * probabilities[:, classes.index(target)]
    return scores


def load_predictions(path, sample_ids, fingerprints):
    with np.load(path, allow_pickle=False) as table:
        metadata = json.loads(table["metadata"].item())
        ids = table["sample_ids"].tolist()
        if not isinstance(metadata, dict) or not isinstance(ids, list):
            raise ValueError("Invalid prediction table metadata or sample IDs")
        if any(metadata.get(key) != value for key, value in fingerprints.items()):
            raise ValueError("Prediction table fingerprint mismatch")
        if (not all(isinstance(sample_id, str) for sample_id in ids)
                or len(ids) != len(set(ids)) or set(ids) != set(sample_ids)):
            raise ValueError("Prediction table sample IDs do not match the gallery")
        positions = {sample_id: i for i, sample_id in enumerate(ids)}
        order = [positions[sample_id] for sample_id in sample_ids]
        predictions = {}
        for field in FIELDS:
            classes = table[field + "_classes"].tolist()
            probs = table[field + "_probabilities"]
            if (not classes or len(set(classes)) != len(classes)
                    or probs.shape != (len(ids), len(classes))
                    or not np.isfinite(probs).all()
                    or not ((probs >= 0) & (probs <= 1)).all()):
                raise ValueError(f"Invalid probabilities for {field}")
            predictions[field] = (classes, probs[order])
        weights = [metadata["weights"][field] for field in FIELDS]
        if any(weight not in (0, 0.1, 0.25) for weight in weights):
            raise ValueError("Invalid reranking weights")
    return predictions, weights
