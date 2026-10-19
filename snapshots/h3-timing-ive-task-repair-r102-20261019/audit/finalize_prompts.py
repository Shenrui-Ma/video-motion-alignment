from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def put(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
# Use only the official retention markers; added content is described directly.
p=R/'design/short_0126_P1_candidate.txt';t=p.read_text();t=t.replace('<Subject 3> is a newly added cat sitting on the bed next to the man.\n','');t=t.replace('<Subject 3> (appears in [Shot 1]): newly_added - place a naturally proportioned cat sitting on the bed beside the man, grounded on the bedding and consistently present in the shot. The man continues his original stretch independently.\n','');p.write_text(t)
p=R/'design/short_0092_P1_candidate.txt';t=p.read_text().replace('<Subject 2> is all visible plants in the room in <Video 1>, including the foliage, flowers and small potted plants in the foreground and background. These plants are the objects to remove.','<Subject 2> is the original room in <Video 1>, including its window, desk, shelves, furnishings and visible foreground and background plants. Only the plants are the objects to remove.').replace('<Subject 3> is the original room, window, desk, shelves, furnishings and the black filming camera on its tripod in <Video 1>.','<Subject 3> is the black filming camera on its tripod in the foreground of <Video 1>.').replace('<Subject 2> (appears in [Shot 1]): partially_preserved - remove every visible plant, including leaves, stems and flowers, from the foreground and background. Restore the local background surfaces behind them in the perspective, color and lighting of the original room.','<Subject 2> (appears in [Shot 1]): partially_preserved - retain the original room layout, window, desk, shelves, furnishings and non-plant objects. Remove every visible plant, including leaves, stems and flowers, from the foreground and background. Restore the local background surfaces behind them in the perspective, color and lighting of the original room.').replace('<Subject 3> (appears in [Shot 1]): fully_preserved - preserve the original room layout, window, desk, shelves, furnishings, filming camera and tripod, and all non-plant objects.','<Subject 3> (appears in [Shot 1]): fully_preserved - preserve the filming camera and tripod, including their appearance, position, orientation and foreground occlusion.');p.write_text(t)
s=read(R/'configs/scientific_contract.json');proposal=read(R/'design/PROPOSAL.json')
for row in proposal['items']:
 sid=row['source_id'];p=R/'configs/prompts'/(sid+'.txt');p.write_bytes((R/'design'/(sid+'_P1_candidate.txt')).read_bytes());row['prompt_sha256']=sha(p);s['prompt_sha256'][sid]=sha(p)
 for c in s['cases']:
  if c['source_id']==sid:c['prompt']=p.read_text();c['prompt_sha256']=sha(p)
put(R/'design/PROPOSAL.json',proposal);s['root_proposal_sha256']=sha(R/'design/PROPOSAL.json');put(R/'configs/scientific_contract.json',s)
import sys;sys.path.insert(0,str(R/'scripts'));import r102_contract as co
for c in s['cases']:put(R/'configs/graphs'/(c['run_id']+'.json'),co.expected_graph(R,c))
print('prompts frozen draft refreshed')
