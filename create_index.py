"""Build the shared FAISS gallery vectors from the combined test split."""
import argparse
from pathlib import Path

import numpy as np

from shoe_retrieval import (
    GALLERY, ROOT, TEST_SPLITS, base_weights_hash, device_for_run,
    encode_images, image_path, load_model, load_rows,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--output", type=Path, default=GALLERY)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    rows = load_rows(TEST_SPLITS)
    paths = [image_path(row).relative_to(ROOT).as_posix() for row in rows]
    weights_hash = base_weights_hash()
    device = device_for_run()
    model, preprocess = load_model(device)
    vectors = encode_images(model, preprocess, rows, args.batch_size, device)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    with temporary.open("wb") as stream:
        np.savez(stream, vectors=vectors.numpy(), paths=paths,
                 sample_ids=[row["sample_id"] for row in rows], base_hash=weights_hash)
    temporary.replace(args.output)
    print(f"Saved {len(rows)} test images to {args.output}")


if __name__ == "__main__":
    main()
