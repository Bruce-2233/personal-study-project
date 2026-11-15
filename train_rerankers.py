"""Train shoe-type and primary-color rerankers on frozen SigLIP features."""
import argparse
import json
from itertools import product
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC

from shoe_retrieval import (
    CONTEXT_LENGTH, GALLERY, MODEL_DIR, TEST_SPLITS, base_weights_hash,
    device_for_run, encode_images, image_preprocess_hash, load_model, load_rows, load_tokenizer,
)
from shoe_reranking import (
    FIELDS, METHODS, TOP_K, fixed_queries, fuse_scores, gallery_fingerprint, load_query_config,
)
from train import relevance

SEED = 42
C_VALUES = (0.1, 1.0, 10.0)
WEIGHT_VALUES = (0.0, 0.1, 0.25)


def split_train_rows(rows):
    fit, val = train_test_split(
        np.arange(len(rows)), test_size=191, random_state=SEED,
        stratify=[row["color_primary"] for row in rows],
    )
    for field in FIELDS:
        classes = {row[field] for row in rows}
        if any({rows[i][field] for i in split} != classes for split in (fit, val)):
            raise ValueError(f"Training/validation split does not cover all classes for {field}")
    return np.sort(fit), np.sort(val)


def classifier(method, c):
    if method == "logistic_regression":
        return LogisticRegression(C=c, class_weight="balanced", solver="lbfgs", max_iter=3000)
    return SVC(C=c, kernel="linear", class_weight="balanced", probability=True, random_state=SEED)


def choose_classifiers(method, features, rows, fit, val):
    models, parameters = {}, {}
    for field in FIELDS:
        targets = np.array([row[field] for row in rows])
        best_f1 = -1.0
        for c in C_VALUES:
            candidate = classifier(method, c).fit(features[fit], targets[fit])
            score = f1_score(targets[val], candidate.predict(features[val]), average="macro",
                             labels=candidate.classes_, zero_division=0)
            if score > best_f1:  # C_VALUES is ordered from smallest to largest.
                models[field] = candidate
                parameters[field] = {"C": c, "validation_macro_f1": float(score)}
                best_f1 = score
    return models, parameters


def predict(models, vectors):
    return {field: (model.classes_.tolist(), model.predict_proba(vectors))
            for field, model in models.items()}


def choose_weights(queries, similarities, val_rows, predictions):
    judged = []
    for q, similarity in zip(queries, similarities):
        # train.relevance uses tuples for requirements that match array contents.
        conditions = {key: tuple(value) if isinstance(value, list) else value
                      for key, value in q["conditions"].items()}
        relevant = np.array([relevance(row, conditions) for row in val_rows])
        if relevant.any():
            judged.append((conditions, similarity, relevant))
    if not judged:
        raise ValueError("No fixed query has relevant validation images")

    def hits(weights):
        total = 0
        for conditions, similarity, relevant in judged:
            scores = fuse_scores(similarity, conditions, predictions, weights)
            top = np.argsort(-scores, kind="stable")[:TOP_K]
            total += np.count_nonzero(relevant[top])
        return total

    candidates = product(WEIGHT_VALUES, repeat=2)
    best = min(candidates, key=lambda weights: (-hits(weights), sum(weights), *weights))
    return best, hits(best) / (len(judged) * TOP_K), len(judged)


def train(args):
    rows = load_rows({"train"})
    fit, val = split_train_rows(rows)
    ids = [row["sample_id"] for row in rows]
    base_hash = base_weights_hash()
    preprocess_hash = image_preprocess_hash()
    with np.load(GALLERY, allow_pickle=False) as gallery:
        test_ids = gallery["sample_ids"].tolist()
        test_vectors = gallery["vectors"]
        if (gallery["base_hash"].item() != base_hash or "preprocess_hash" not in gallery
                or gallery["preprocess_hash"].item() != preprocess_hash
                or len(test_ids) != len(set(test_ids))
                or set(test_ids) != {r["sample_id"] for r in load_rows(TEST_SPLITS)}
                or set(test_ids).intersection(ids)):
            raise ValueError("Incompatible test gallery. Run create_index.py before training.")
    queries = fixed_queries(load_query_config())
    device = device_for_run()
    print(f"Extracting features on {device} for {len(rows)} training images", flush=True)
    model, preprocess = load_model(device)
    features = encode_images(model, preprocess, rows, args.batch_size, device).numpy()
    tokens = load_tokenizer()([q["text"] for q in queries], context_length=CONTEXT_LENGTH).to(device)
    with torch.inference_mode():
        queries_vectors = F.normalize(model.encode_text(tokens).float(), dim=-1).cpu().numpy()
    similarities = queries_vectors @ features[val].T
    del model
    fingerprints = dict(base_hash=base_hash, preprocess_hash=preprocess_hash,
                        gallery_hash=gallery_fingerprint(test_vectors, test_ids))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for method in METHODS:
        models, parameters = choose_classifiers(method, features, rows, fit, val)
        weights, score, n_queries = choose_weights(
            queries, similarities, [rows[i] for i in val], predict(models, features[val]),
        )
        print(f"{method}: validation P@8={score:.4f}; C settings={parameters}; weights={weights}", flush=True)
        for field in FIELDS:
            models[field] = classifier(method, parameters[field]["C"]).fit(
                features, [row[field] for row in rows],
            )
        table = {}
        for field, (classes, probabilities) in predict(models, test_vectors).items():
            table[field + "_classes"] = classes
            table[field + "_probabilities"] = probabilities
        metadata = dict(
            **fingerprints, method=method, seed=SEED, split_unit="image",
            fit_ids=[ids[i] for i in fit], validation_ids=[ids[i] for i in val],
            weights=dict(zip(FIELDS, weights)), parameters=parameters,
            validation_p_at_8=score, validation_queries=n_queries,
        )
        path = args.output_dir / f"{method}.npz"
        temporary = path.with_suffix(".tmp")
        with temporary.open("wb") as stream:
            np.savez_compressed(stream, **table, sample_ids=test_ids, metadata=json.dumps(metadata))
        temporary.replace(path)
        print(f"Saved {path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--output-dir", type=Path, default=MODEL_DIR)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    train(args)


if __name__ == "__main__":
    main()
