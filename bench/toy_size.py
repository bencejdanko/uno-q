import sys, torch
from executorch.extension.pybindings.portable_lib import _load_for_executorch_from_buffer
from executorch.exir import to_edge_transform_and_lower
s = int(sys.argv[1]); x = torch.rand(1,3,s,s)
toy = torch.nn.Sequential(torch.nn.Conv2d(3,16,3,2,1), torch.nn.SiLU()).eval()
buf = to_edge_transform_and_lower(torch.export.export(toy,(x,))).to_executorch().buffer
out = _load_for_executorch_from_buffer(buf).forward([x])[0]
print(f"size {s}: OK", flush=True)
