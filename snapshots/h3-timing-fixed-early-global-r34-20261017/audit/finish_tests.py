from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parents[1]
p=r/'tests/test_static.py';s=p.read_text().replace(',235750)',',1980300)')
a=s.index(' def test_parent_full_processed_tree');b=s.index('class TransactionNegativeTests')
s=s[:a]+''' def test_actual_graph_and_no_fabricated_parent_tree(self):
  validate_job(RUN_ID);g=json.loads((R/'configs/graphs'/f'{RUN_ID}.json').read_text());self.assertEqual(g,expected_graph());self.assertEqual(g['50']['class_type'],'H3StaticWindowRouter');self.assertEqual(g['6']['inputs']['seed'],2026101701)
  self.assertFalse((R/'configs/parent_actual_condition_tree.json').exists())
 def test_prefix_tensor_and_metadata_corruptions(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);a=torch.zeros((1,24,42,46,82));b=torch.ones((1,32,2,235))/4;sig=[readout.tensor_signature(v) for v in (a,b)]
   record=copy.deepcopy(json.loads((R/'configs/parent_captures.json').read_text())['captures'][4]);record['video'],record['audio']=sig
   meta={k:v for k,v in record.items() if k not in ('file','capture_seconds')};old=d/'old.pt';now=d/'now.pt';value={'video':a,'audio':b,'metadata':meta};torch.save(value,old)
   row={'physical_index':4,'branch':'native','nfe_index':4,'seed':2026101701,'sigma':meta['sigma_video'],'sigma_next':meta['sigma_next_video'],'normalized_stream_signatures':sig}
   current={'video':a,'audio':b,'metadata':dict(row)};torch.save(current,now)
   expected={'index':4,'path':str(old),'file_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'metadata':record}
   self.assertTrue(actual_prefix(row,expected,now)['actual_tensor_equal'])
   for key,val in [('seed',1),('sigma_audio',.7),('schema','bad'),('audio_scale',1)]:
    bad=copy.deepcopy(value);bad['metadata'][key]=val;torch.save(bad,old);e=copy.deepcopy(expected);e['file_sha256']=hashlib.sha256(old.read_bytes()).hexdigest()
    with self.assertRaises(ValueError):actual_prefix(row,e,now)
   torch.save(value,old);expected['file_sha256']=hashlib.sha256(old.read_bytes()).hexdigest()
   for key,val in [('branch','full'),('physical_index',3),('seed',1),('nfe_index',5)]:
    bad=dict(row);bad[key]=val
    with self.assertRaises(ValueError):actual_prefix(bad,expected,now)
   bad=copy.deepcopy(current);bad['audio']=bad['audio']*4;torch.save(bad,now)
   with self.assertRaises(ValueError):actual_prefix(row,expected,now)
   torch.save(current,now);e=copy.deepcopy(expected);e['file_sha256']='wrong'
   with self.assertRaises(ValueError):actual_prefix(row,e,now)
''' +s[b:];p.write_text(s)
# Same current row metadata must be bound, not only the old record.
p=r/'extensions/H3StaticWindowRouter/pair_gate.py';s=p.read_text();needle="m=saved['metadata']";s=s.replace(needle,"t.require(all(current['metadata'][k]==row[k] for k in ('physical_index','branch','nfe_index','seed','sigma','sigma_next')),'current prefix metadata binding')\n    "+needle);p.write_text(s)
# Actual packed noise is concatenated in the original stream order, matching Comfy pack_latents.
p=r/'configs/resource_admission_template.json';v=json.loads(p.read_text());h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();v['kernel_gate_sha256']=h(r/'configs/inherited_actual87361_kernel.json');v['kernel_inheritance_sha256']=h(r/'configs/kernel_inheritance.json');p.write_text(json.dumps(v,indent=2)+'\n')
# Stage the exact producer source and four immutable design files.
s=Path('/Users/researcher/DevProjects/h3-timing-window-location-r33-20261017/audit/run_cpu_gate.py').read_text().replace('r33','r34').replace('R33','R34').replace('displaced_probe_first','global_probe_first')
s=s.replace("('scripts','extensions','tests','configs','design')","('scripts','extensions','tests','configs')")
s=s.replace("(r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json').write_text", "files.update({name:hashlib.sha256((r/name).read_bytes()).hexdigest() for name in ('PROTOCOL.json','README.txt','COMPARABILITY.txt','FREEZE.json')})\n(r/'audit'/f'cpu_stage_attempt{attempt}_manifest.json').write_text")
s=s.replace("'H3_SERVER_A:'+remote+'/'],check=True)","'H3_SERVER_A:'+remote+'/'],check=True)\nsubprocess.run(['rsync','-a',*[str(r/name) for name in ('PROTOCOL.json','README.txt','COMPARABILITY.txt','FREEZE.json')],'H3_SERVER_A:'+remote+'/'],check=True)")
(r/'audit/run_cpu_gate.py').write_text(s)
print('targeted tests prepared')
