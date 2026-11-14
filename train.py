"""Fine-tune the last SigLIP text block and projection on annotated shoes."""
import argparse
import random
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

from shoe_retrieval import (
    CHECKPOINT, CONTEXT_LENGTH, base_weights_hash, device_for_run,
    encode_images, load_model, load_rows, load_tokenizer,
)

SHOES = dict(Boots="boots", Flats="flat shoes", Heels="high-heeled shoes",
             Sandals="sandals", Sneakers="sneakers")
COLORS = {"Grey": "gray", "Metallic": "metallic-colored", "Multi": "multicolored"}
MATERIALS = dict(Canvas="canvas", Knit="knit", Leather="leather-like", Mesh="mesh",
                 Mixed="mixed-material", Patent="patent-finish", Rubber="rubber-like",
                 Suede="suede-like")


def caption_options(row):
    shoe = {"shoe_type": row["shoe_type"]}
    color = {"color_primary": row["color_primary"]}
    material = {"material_primary": row["material_primary"]}
    full = shoe | color | material
    for field, primary in (("colors_present", "color_primary"),
                           ("materials_present", "material_primary")):
        extras = set(row[field]) - {row[primary]}
        if extras:
            full[field] = tuple(sorted(extras))
    color_composition = shoe | color
    if "colors_present" in full:
        color_composition["colors_present"] = full["colors_present"]
    material_composition = shoe | material
    if "materials_present" in full:
        material_composition["materials_present"] = full["materials_present"]
    return [shoe, shoe | color, shoe | material, shoe | color | material,
            color_composition, material_composition, full]


def render_caption(fields):
    words = []
    color = fields.get("color_primary")
    material = fields.get("material_primary")
    if color:
        words.append(COLORS.get(color, color.lower()))
    if material:
        words.append(MATERIALS[material])
    words.append(SHOES[fields["shoe_type"]])
    extras = [COLORS.get(c, c.lower()) + " elements" for c in fields.get("colors_present", ())]
    extras.extend(
        ("knit fabric" if m == "Knit" else MATERIALS[m]) + " elements"
        for m in fields.get("materials_present", ())
    )
    if extras:
        words.extend(("with", " and ".join(extras)))
    return " ".join(words)


def swapped_caption(fields):
    for primary, present, special in (
        ("color_primary", "colors_present", "Multi"),
        ("material_primary", "materials_present", "Mixed"),
    ):
        main = fields.get(primary)
        extras = fields.get(present, ())
        if main and main != special and extras and extras[0] != "Clear":
            return fields | {primary: extras[0], present: tuple(sorted((main, *extras[1:])))}
    return None


def relevance(row, fields):
    return all(set(value).issubset(row[key]) if isinstance(value, tuple)
               else row[key] == value for key, value in fields.items())


def train(args):
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    rows = load_rows({"train"})
    if args.limit:
        rows = rows[:args.limit]
    if len(rows) < 2:
        raise ValueError("Training needs at least two images")
    options = [caption_options(row) for row in rows]
    device = device_for_run()
    print(f"Training on {device}, {len(rows)} images", flush=True)
    weights_hash = base_weights_hash()
    model, preprocess = load_model(device)
    model.requires_grad_(False)
    # Use a normal tensor after encode_images so autograd can save it for text gradients.
    vectors = encode_images(model, preprocess, rows, args.batch_size, device).clone()
    model.visual.to("cpu")
    block = model.text.transformer.resblocks[-1]
    block.requires_grad_(True)
    projection = model.text.text_projection
    if isinstance(projection, (nn.Module, nn.Parameter)):
        projection.requires_grad_(True)
    trainable = {name: p for name, p in model.named_parameters() if p.requires_grad}
    optimizer = torch.optim.AdamW(trainable.values(), lr=args.lr)
    tokenizer = load_tokenizer()
    scale = model.logit_scale.detach().float().exp()
    bias = getattr(model, "logit_bias", None)
    if bias is not None:
        bias = bias.detach().float()

    for epoch in range(args.epochs):
        order = torch.randperm(len(rows)).tolist()
        losses = []
        for start in range(0, len(order), args.batch_size):
            indices = order[start:start + args.batch_size]
            if len(indices) < 2:
                continue
            captions = []
            seen = set()
            for idx in indices:
                chosen = random.choice(options[idx])
                # Include composition and a primary/secondary swap when applicable.
                for fields in (chosen, options[idx][-1], swapped_caption(options[idx][-1])):
                    if fields:
                        text = render_caption(fields)
                        if text not in seen:
                            seen.add(text)
                            captions.append((text, fields))
            targets = torch.tensor(
                [[relevance(rows[idx], fields) for _, fields in captions] for idx in indices],
                device=device, dtype=torch.float32,
            )
            tokens = tokenizer([text for text, _ in captions], context_length=CONTEXT_LENGTH).to(device)
            text_vectors = F.normalize(model.encode_text(tokens).float(), dim=-1)
            logits = scale * (vectors[indices].to(device) @ text_vectors.T)
            if bias is not None:
                logits = logits + bias
            loss = F.binary_cross_entropy_with_logits(logits, targets)
            if not torch.isfinite(loss):
                raise ValueError("Non-finite training loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
            if len(losses) % 10 == 0:
                print(f"Epoch {epoch + 1}: {len(losses)} batches, loss={loss.item():.4f}", flush=True)
        print(f"Epoch {epoch + 1}/{args.epochs}: loss={sum(losses) / len(losses):.4f}", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    torch.save({
        "base_hash": weights_hash,
        "text_updates": {name: p.detach().cpu() for name, p in trainable.items()},
        "train_size": len(rows), "epochs": args.epochs, "seed": args.seed,
        "batch_size": args.batch_size, "learning_rate": args.lr, "smoke": bool(args.limit),
    }, temporary)
    temporary.replace(args.output)
    print(f"Saved {sum(p.numel() for p in trainable.values()):,} trainable parameters to {args.output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=0, help="Run a small smoke test")
    parser.add_argument("--output", type=Path, default=CHECKPOINT)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 2 or not 0 < args.lr < 1 or args.limit < 0:
        parser.error("Require epochs >= 1, batch size >= 2, 0 < lr < 1, and limit >= 0")
    if args.limit and args.output.resolve() == CHECKPOINT:
        parser.error("Smoke tests require a separate --output checkpoint")
    train(args)


if __name__ == "__main__":
    main()
