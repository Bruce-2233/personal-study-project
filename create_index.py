"""Build the shared root-level index in bounded batches."""
from pathlib import Path
import json
import argparse
import numpy as np
import faiss
import open_clip
from PIL import Image
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    paths = sorted(p for p in (ROOT / "images").rglob("*")
                   if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and p.is_file())
    if not paths:
        raise SystemExit("No images found in images/")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-16-SigLIP-512",
        pretrained=str(ROOT / "model" / "open_clip_pytorch_model.bin"),
    )
    model = model.to(device).eval()
    index = None
    with torch.inference_mode():
        for start in range(0, len(paths), args.batch_size):
            batch = []
            for path in paths[start:start + args.batch_size]:
                with Image.open(path) as image:
                    batch.append(preprocess(image.convert("RGB")))
            embeddings = F.normalize(model.encode_image(torch.stack(batch).to(device)), p=2, dim=-1)
            vectors = np.ascontiguousarray(embeddings.float().cpu().numpy())
            if index is None:
                index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            print(f"Encoded {index.ntotal}/{len(paths)} images")
    # Do not replace existing artifacts until all images have encoded successfully.
    faiss.write_index(index, str(ROOT / "index.faiss"))
    with (ROOT / "mapping.json").open("w", encoding="utf-8") as stream:
        json.dump([p.relative_to(ROOT).as_posix() for p in paths], stream, ensure_ascii=False)
    print("Saved index.faiss and mapping.json")


if __name__ == "__main__":
    main()
