import copy,sys,json
from pathlib import Path
r=Path(sys.argv[1]).resolve();sys.path.insert(0,str(r/'scripts'));from mf_capacity import assess
G=2**30;v={'uid':1004,'host_available_bytes':32*G,'ancestors':[{'path':'/user.slice','current_bytes':88*G,'high_bytes':100*G,'max_bytes':112*G,'pressure':{'some':{'avg10':99},'full':{'avg10':99}},'events':{'oom':0,'oom_kill':0}}]};out=[]
def test(name,q,n,expected):
 try:assess(q,n);passed=True
 except (AssertionError,KeyError,StopIteration):passed=False
 assert passed==expected,name;out.append(name)
def changed(path,val):
 q=copy.deepcopy(v);x=q
 for key in path[:-1]:x=x[key]
 x[path[-1]]=val;return q
row=['ancestors',0]
test('raw high exact12 PSI99 accepted',v,12,True)
test('raw high one byte short',changed(row+['current_bytes'],88*G+1),12,False)
test('host one byte short',changed(['host_available_bytes'],32*G-1),12,False)
test('UID wrong',changed(['uid'],1016),12,False)
test('parent limit changed',changed(row+['high_bytes'],101*G),12,False)
test('runtime raw8 exact high not gate',changed(row+['current_bytes'],104*G),8,True)
test('runtime raw8 short',changed(row+['current_bytes'],104*G+1),8,False)
test('nonfinite PSI',changed(row+['pressure','some','avg10'],float('nan')),12,False)
test('invalid OOM counter',changed(row+['events','oom'],-1),12,False)
q=copy.deepcopy(v);q['ancestors'].append(dict(copy.deepcopy(q['ancestors'][0]),path='/leaf',current_bytes=88*G,high_bytes=None,max_bytes=100*G));test('leaf rawmax12 exact',q,12,True);q['ancestors'][1]['current_bytes']+=1;test('leaf rawmax12 short',q,12,False)
assert 'torch' not in sys.modules;print(json.dumps({'passed':True,'test_count':len(out),'tests':out,'CUDA_started':False}))
