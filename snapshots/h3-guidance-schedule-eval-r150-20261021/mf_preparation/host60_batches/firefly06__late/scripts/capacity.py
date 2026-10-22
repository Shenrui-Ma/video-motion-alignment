from capacity_v1 import snapshot,oom_delta
from capacity_v1 import assess as original_assess
def assess(value,mode):
 assert mode in ('entry','running')
 return original_assess(value,12 if mode=='entry' else 8)
