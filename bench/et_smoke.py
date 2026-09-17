import sys, torch
from executorch.runtime import Runtime
m = Runtime.get().load_program(open(sys.argv[1], 'rb').read()).load_method('forward')
out = m.execute([torch.rand(1, 3, 320, 320)])
print('OK', [tuple(o.shape) for o in out])
