from pathlib import Path
import json
import numpy as np
import faiss
import open_clip
import torch
import torch.nn.functional as F
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "model"
TOP_K = 20


def load_resources():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, _ = open_clip.create_model_and_transforms(
        "ViT-B-16-SigLIP-512",
        pretrained=str(MODEL_DIR / "open_clip_pytorch_model.bin"),
    )
    model = model.to(device).eval()
    tokenizer = open_clip.tokenizer.HFTokenizer(str(MODEL_DIR), clean="canonicalize")
    index = faiss.read_index(str(ROOT / "index.faiss"))
    with (ROOT / "mapping.json").open(encoding="utf-8") as stream:
        mapping = json.load(stream)
    if not isinstance(mapping, list) or len(mapping) != index.ntotal:
        raise ValueError("Index and mapping do not match; run python create_index.py")
    if index.metric_type != faiss.METRIC_INNER_PRODUCT:
        raise ValueError("Expected an inner-product index; rebuild the index")
    return model, tokenizer, index, mapping, device


def create_app(resources=None):
    app = Flask(__name__, static_folder=str(ROOT / "frontend"), static_url_path="/static")
    CORS(app)
    # Loaded once, rather than on every search. Injectable for API verification.
    model, tokenizer, index, mapping, device = resources or load_resources()

    @app.get("/")
    def home():
        return app.send_static_file("index.html")

    @app.get("/script.js")
    def script():
        return app.send_static_file("script.js")

    @app.get("/style.css")
    def stylesheet():
        return app.send_static_file("style.css")

    @app.get("/images/<path:filename>")
    def image(filename):
        return send_from_directory(ROOT / "images", filename)

    @app.post("/lookup")
    def lookup():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get("text"), str):
            return jsonify(error="Provide a JSON object with a text string."), 400
        text = data["text"].strip()
        if not text or len(text) > 2000:
            return jsonify(error="Text must contain 1 to 2000 characters."), 400
        if index.ntotal == 0:
            return jsonify(similarity=[], imagePaths=[])
        tokens = tokenizer(text, context_length=64).to(device)
        with torch.inference_mode():
            embedding = F.normalize(model.encode_text(tokens), p=2, dim=-1)
        query = np.ascontiguousarray(embedding.float().cpu().numpy())
        if query.shape[1] != index.d:
            raise ValueError("Model and index dimensions differ; rebuild the index")
        scores, ids = index.search(query, min(TOP_K, index.ntotal))
        return jsonify(
            similarity=scores[0].tolist(),
            imagePaths=[mapping[int(item)].replace("\\", "/") for item in ids[0]],
        )

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)
