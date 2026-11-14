from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

import faiss
import numpy as np
import torch
import torch.nn.functional as F
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Also support the existing "python docker/app.py" entry point.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shoe_retrieval import (
    CHECKPOINT, CONTEXT_LENGTH, GALLERY, ROOT, base_weights_hash,
    DATASET, TEST_SPLITS, device_for_run, load_model, load_rows, load_tokenizer,
)

TOP_K = 8
SYNTHETIC_LEATHER = re.compile(r"\bsynthetic[\s-]+leather\b", re.IGNORECASE)


def load_resources(gallery_path=GALLERY, checkpoint_path=CHECKPOINT):
    device = device_for_run()
    weights_hash = base_weights_hash()
    with np.load(gallery_path, allow_pickle=False) as gallery:
        vectors = np.ascontiguousarray(gallery["vectors"], dtype=np.float32)
        paths = gallery["paths"].tolist()
        sample_ids = gallery["sample_ids"].tolist()
        if gallery["base_hash"].item() != weights_hash:
            raise ValueError("Gallery uses different base weights. Rebuild with create_index.py")
    if (vectors.ndim != 2 or len(vectors) != len(paths) or len(paths) != len(sample_ids)
            or len(set(sample_ids)) != len(sample_ids) or not np.isfinite(vectors).all()):
        raise ValueError("Invalid gallery. Rebuild with create_index.py")
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    # The gallery already contains image embeddings, so the web process needs
    # only the two text towers.
    model, _ = load_model("cpu")
    baseline = model.text
    finetuned = None
    if checkpoint_path.is_file():
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        if checkpoint["base_hash"] != weights_hash:
            raise ValueError("Fine-tuned checkpoint uses different base weights")
        finetuned = deepcopy(baseline)
        state = finetuned.state_dict()
        updates = checkpoint["text_updates"]
        if not updates or any(not k.startswith("text.") or k[5:] not in state for k in updates):
            raise ValueError("Checkpoint contains invalid text parameters")
        for name, value in updates.items():
            state[name[5:]] = value
        finetuned.load_state_dict(state)
        finetuned.to(device).eval()
    del model
    return baseline.to(device).eval(), finetuned, load_tokenizer(), index, paths, sample_ids, device


LABEL_FIELDS = ("shoe_type", "color_primary", "material_primary",
                "colors_present", "materials_present")
EVALUATION_DIR = DATASET.parent / "retrieval_evaluation_merged"


def query_key(text):
    return " ".join(SYNTHETIC_LEATHER.sub("leather-like", text).casefold().split()).rstrip(".").strip()


def load_judgments(sample_ids):
    rows = load_rows(TEST_SPLITS)
    labels = {row["sample_id"]: {field: row[field] for field in LABEL_FIELDS} for row in rows}
    config = json.loads((EVALUATION_DIR / "queries.json").read_text(encoding="utf-8-sig"))
    gallery_ids = set(sample_ids)
    if (gallery_ids != labels.keys() or len(gallery_ids) != config["gallery_size"]
            or hashlib.sha256(DATASET.read_bytes()).hexdigest() != config["dataset_sha256"]):
        return labels, {}

    eligible = {row["query_id"]: row for row in config["queries"]
                if row["relevant_count"] >= TOP_K}
    relevant = {qid: set() for qid in eligible}
    with (EVALUATION_DIR / "qrels.txt").open(encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                qid, _, sample_id, grade = line.split()
                if qid in relevant and int(grade) > 0:
                    relevant[qid].add(sample_id)
    judgments = {
        query_key(row["text"]): relevant[qid]
        for qid, row in eligible.items()
        if len(relevant[qid]) == row["relevant_count"] and relevant[qid] <= gallery_ids
    }
    return labels, judgments


def create_app(resources=None):
    app = Flask(__name__, static_folder=str(ROOT / "frontend"), static_url_path="/static")
    CORS(app)
    baseline, finetuned, tokenizer, index, paths, sample_ids, device = resources or load_resources()

    labels, judgments = load_judgments(sample_ids)

    @app.get("/")
    def home():
        return app.send_static_file("index.html")

    @app.get("/script.js")
    def script():
        return app.send_static_file("script.js")

    @app.get("/style.css")
    def stylesheet():
        return app.send_static_file("style.css")

    @app.get("/shoes_images/<path:filename>")
    def image(filename):
        # Expose only image files from the indexed gallery.
        if f"shoes_images/{filename}" not in paths:
            return "", 404
        return send_from_directory(ROOT / "shoes_images", filename)

    def search(tower, tokens, relevant):
        if not index.ntotal:
            return {"similarity": [], "imagePaths": [], "sampleIds": [],
                    "labels": [], "isRelevant": [], "p_at_8": None, "relevant_count": None}
        with torch.inference_mode():
            embedding = F.normalize(tower(tokens).float(), dim=-1)
        vector = np.ascontiguousarray(embedding.cpu().numpy())
        scores, ids = index.search(vector, min(TOP_K, index.ntotal))
        result_ids = [sample_ids[i] for i in ids[0]]
        flags = [sample_id in relevant if relevant is not None else None for sample_id in result_ids]
        hits = (sum(flags)
                if relevant is not None and len(result_ids) == TOP_K else None)
        return {
            "labels": [labels.get(sample_id) for sample_id in result_ids],
            "isRelevant": flags,
            "p_at_8": hits / TOP_K if hits is not None else None,
            "relevant_count": hits,
            "similarity": scores[0].tolist(),
            "imagePaths": [paths[i] for i in ids[0]],
            "sampleIds": result_ids,
        }

    @app.post("/lookup")
    def lookup():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get("text"), str):
            return jsonify(error="Provide a JSON object with a text string."), 400
        text = data["text"].strip()
        if not text or len(text) > 2000:
            return jsonify(error="Text must contain 1 to 2000 characters."), 400
        text = SYNTHETIC_LEATHER.sub("leather-like", text)
        tokens = tokenizer(text, context_length=CONTEXT_LENGTH).to(device)
        relevant = judgments.get(query_key(text))
        original = search(baseline, tokens, relevant)
        updated = search(finetuned, tokens, relevant) if finetuned is not None else None
        return jsonify(
            **original, baseline=original, finetuned=updated,
            finetuned_status="ready" if updated is not None else "checkpoint_missing",
        )

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)
