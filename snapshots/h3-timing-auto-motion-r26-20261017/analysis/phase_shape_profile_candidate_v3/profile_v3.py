"""Private module proxy changes only v2's solve call, never frozen modules on disk."""
from bindings import V2_ROOT,load
from selector import solve,relation,compact

PRIVATE=load(V2_ROOT/'profile_v2.py','private_v2_for_v3')
ORIGINAL=PRIVATE.base
class Proxy:
    def __getattr__(self,name):return getattr(ORIGINAL,name)
    def solve(self,rows,total=141):
        selected=solve(rows,total)
        old=ORIGINAL.solve(rows,total)
        selected['selector_audit']['source_only_selected']=[compact(r) for r in old['selected']]
        selected['selector_audit']['source_only_pair_relations']=[relation(a,b) for a,b in zip(old['selected'],old['selected'][1:])]
        return selected
PRIVATE.base=Proxy()
def analyze(source,target):
    result,evidence=PRIVATE.analyze(source,target)
    result['selector']='v3 source-disjoint and robust target-envelope ordered'
    return result,evidence
