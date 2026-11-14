"""Shared model and dataset helpers for shoe retrieval."""
import hashlib
import json
from pathlib import Path

import open_clip
import torch
import torch.nn.functional as F
from PIL import Image

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "model"
WEIGHTS = MODEL_DIR / "open_clip_pytorch_model.bin"
CHECKPOINT = MODEL_DIR / "shoes_finetuned.pt"
GALLERY = MODEL_DIR / "shoe_gallery.npz"
DATASET = ROOT / "shoes_images" / "cleaned_dataset" / "dataset.jsonl"
MODEL_NAME = "ViT-B-16-SigLIP-512"
CONTEXT_LENGTH = 64
TEST_SPLITS = {"test", "validation"}


def device_for_run():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def base_weights_hash():
    with WEIGHTS.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_model(device):
    model, _, preprocess = open_clip.create_model_and_transforms(
        MODEL_NAME, pretrained=str(WEIGHTS),
    )
    return model.to(device).eval(), preprocess


def load_tokenizer():
    return open_clip.tokenizer.HFTokenizer(str(MODEL_DIR), clean="canonicalize")


def load_rows(splits):
    with DATASET.open(encoding="utf-8-sig") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    selected = [
        row for row in rows
        if row["split"] in splits and row["review_status"] == "confirmed"
    ]
    if not selected or len({r["sample_id"] for r in selected}) != len(selected):
        raise ValueError("Dataset selection is empty or has duplicate sample IDs")
    return selected


def image_path(row):
    image_root = ROOT / "shoes_images"
    path = (image_root / row["image_path"]).resolve()
    if not path.is_relative_to(image_root) or not path.is_file():
        raise ValueError(f"Invalid image path: {row['image_path']}")
    return path


@torch.inference_mode()
def encode_images(model, preprocess, rows, batch_size, device):
    batches = []
    for start in range(0, len(rows), batch_size):
        images = []
        for row in rows[start:start + batch_size]:
            with Image.open(image_path(row)) as image:
                images.append(preprocess(image.convert("RGB")))
        encoded = model.encode_image(torch.stack(images).to(device))
        batches.append(F.normalize(encoded.float(), dim=-1).cpu())
        count = min(start + batch_size, len(rows))
        if count == len(rows) or (start // batch_size + 1) % 10 == 0:
            print(f"Encoded {count}/{len(rows)} images", flush=True)
    return torch.cat(batches)
