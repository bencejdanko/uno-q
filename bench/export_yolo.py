"""Export YOLO11n to ExecuTorch (XNNPACK fp32 + int8 PTQ) and ONNX, and check parity vs PyTorch.

Usage: python export_yolo.py [--sizes 320 640] [--out models]
"""

import argparse
import copy
from pathlib import Path

import numpy as np
import torch
from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
from executorch.backends.xnnpack.quantizer.xnnpack_quantizer import (
    XNNPACKQuantizer,
    get_symmetric_quantization_config,
)
from executorch.exir import to_edge_transform_and_lower
from executorch.runtime import Runtime
from PIL import Image
from torchao.quantization.pt2e.quantize_pt2e import convert_pt2e, prepare_pt2e
from ultralytics import YOLO
from ultralytics.utils import ASSETS


def load_model(weights: str) -> torch.nn.Module:
    model = YOLO(weights).model.eval().float().fuse()
    head = model.model[-1]
    head.export = True  # raw (1, 4 + classes, anchors) output, no NMS or dict outputs
    head.format = "executorch"
    for p in model.parameters():
        p.requires_grad_(False)
    return model


def letterbox(path: Path, size: int) -> torch.Tensor:
    img = Image.open(path).convert("RGB")
    scale = size / max(img.size)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.BILINEAR)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return torch.from_numpy(np.asarray(canvas)).permute(2, 0, 1)[None].float() / 255


def calibration_images(size: int) -> list[torch.Tensor]:
    # Small sanity set bundled with ultralytics; use frames from the robot camera for real calibration.
    return [letterbox(p, size) for p in sorted(Path(ASSETS).glob("*.jpg"))]


def to_pte(module: torch.nn.Module, example: torch.Tensor, path: Path) -> None:
    exported = torch.export.export(module, (example,), strict=False)
    program = to_edge_transform_and_lower(exported, partitioner=[XnnpackPartitioner()]).to_executorch()
    path.write_bytes(program.buffer)


def quantize_int8(model: torch.nn.Module, images: list[torch.Tensor]) -> torch.nn.Module:
    quantizer = XNNPACKQuantizer().set_global(get_symmetric_quantization_config(is_per_channel=True))
    graph = torch.export.export(copy.deepcopy(model), (images[0],), strict=False).module()
    prepared = prepare_pt2e(graph, quantizer)
    for img in images:
        prepared(img)
    return convert_pt2e(prepared)


def parity(path: Path, x: torch.Tensor, ref: torch.Tensor) -> str:
    method = Runtime.get().load_program(path.read_bytes()).load_method("forward")
    out = method.execute([x])[0]
    boxes_err = (out[:, :4] - ref[:, :4]).abs().max().item()
    score_err = (out[:, 4:] - ref[:, 4:]).abs().max().item()
    top_ref = ref[0, 4:].amax(0).topk(10).indices
    top_out = out[0, 4:].amax(0).topk(10).indices
    overlap = len(set(top_ref.tolist()) & set(top_out.tolist()))
    return f"max|Δbox|={boxes_err:.2f}px max|Δscore|={score_err:.3f} top10-anchor overlap={overlap}/10"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="yolo11n.pt")
    ap.add_argument("--sizes", type=int, nargs="+", default=[320, 640])
    ap.add_argument("--out", type=Path, default=Path("models"))
    args = ap.parse_args()
    args.out.mkdir(exist_ok=True)

    model = load_model(args.weights)
    for size in args.sizes:
        images = calibration_images(size)
        x = images[0]
        with torch.no_grad():
            ref = model(x)
            ref = ref[0] if isinstance(ref, (tuple, list)) else ref

        fp32 = args.out / f"yolo11n_{size}_xnnpack_fp32.pte"
        to_pte(model, x, fp32)
        print(f"{fp32.name}: {fp32.stat().st_size / 1e6:.1f} MB, {parity(fp32, x, ref)}")

        int8 = args.out / f"yolo11n_{size}_xnnpack_int8.pte"
        to_pte(quantize_int8(model, images), x, int8)
        print(f"{int8.name}: {int8.stat().st_size / 1e6:.1f} MB, {parity(int8, x, ref)}")

        onnx = Path(YOLO(args.weights).export(format="onnx", imgsz=size, simplify=True, verbose=False))
        onnx = onnx.rename(args.out / f"yolo11n_{size}.onnx")
        print(f"{onnx.name}: {onnx.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
