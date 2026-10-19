"""CPU boundary checks for the approved short tracker memory policy."""
import copy, importlib.util, json, sys
from pathlib import Path
root=Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('short_mf_capacity',root/'scripts/mf_capacity.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
G=2**30
v={'uid':1004,'host_available_bytes':32*G,'ancestors':[{'path':'/user.slice','current_bytes':100*G,'high_bytes':100*G,'max_bytes':112*G,'stat':{'file':21*G,'shmem':G,'active_file':10*G,'inactive_file':10*G,'file_mapped':G,'file_dirty':G,'file_writeback':0},'pressure':{'some':{'avg10':5.0},'full':{'avg10':5.0}}}]}
# Clean unmapped cache=18 GiB, retaining 6 leaves 12 GiB adjusted headroom.
cases=[]
def test(name,q,raw,passed):
 try:out=m.assess(q,raw);actual=True
 except (AssertionError,KeyError,StopIteration):actual=False
 assert actual==passed,(name,actual,passed)
 cases.append({'name':name,'passed':True})
def change(path,val):
 q=copy.deepcopy(v);x=q
 for k in path[:-1]:x=x[k]
 x[path[-1]]=val;return q
row=['ancestors',0]
test('exact preload boundaries',v,12,True)
test('raw max one byte short',change(row+['current_bytes'],100*G+1),12,False)
test('adjusted high one byte short',change(row+['stat','file_mapped'],G+1),12,False)
test('host one byte short',change(['host_available_bytes'],32*G-1),12,False)
test('pressure over five',change(row+['pressure','some','avg10'],5.001),12,False)
test('runtime elevated pressure recorded',change(row+['pressure','some','avg10'],9.0),8,True)
test('nonfinite pressure',change(row+['pressure','full','avg10'],float('nan')),12,False)
test('wrong UID',change(['uid'],1005),12,False)
test('changed limit',change(row+['high_bytes'],101*G),12,False)
for key in ['file','shmem','active_file','inactive_file','file_mapped','file_dirty','file_writeback']:
 test('negative '+key,change(row+['stat',key],-1),12,False)
 q=copy.deepcopy(v);del q['ancestors'][0]['stat'][key];test('missing '+key,q,12,False)
q=copy.deepcopy(v);q['ancestors'][0]['current_bytes']=104*G;q['ancestors'][0]['stat'].update(file=25*G,active_file=14*G)
test('runtime raw eight exact',q,8,True)
q['ancestors'][0]['current_bytes']+=1;test('runtime raw below eight',q,8,False)
assert 'torch' not in sys.modules
print(json.dumps({'passed':True,'test_count':len(cases),'tests':cases,'CUDA_started':False}))
