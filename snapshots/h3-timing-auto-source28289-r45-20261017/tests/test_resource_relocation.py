import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
import prelaunch_gates as g
class ResourceRelocationTests(unittest.TestCase):
 def fixture(self,d):
  root=Path(d)/'current';parent=Path(d)/'parent'
  for p in (root,parent): (p/'configs').mkdir(parents=True);(p/'audit').mkdir()
  def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
  put(root/'configs/protocol.json',{'schema':'current'});put(parent/'configs/protocol.json',{'schema':'prior'})
  put(parent/'deploy_manifest.json',{'files':{}})
  for p in (root,parent):put(p/'configs/numerical.json',{'same':1});put(p/'configs/conditioning.json',{'same':2})
  # Numerical implementation is inherited; this case needs its own 87366 gate.
  spec={'parent_root':str(parent),'parent_deploy_manifest_sha256':g.sha(parent/'deploy_manifest.json'),'parent_protocol_sha256':g.sha(parent/'configs/protocol.json'),'exact_numerical_files':{'configs/numerical.json':g.sha(root/'configs/numerical.json')},'same_source_condition_noise_artifacts':['configs/conditioning.json']}
  put(root/'configs/r27_inheritance.json',spec);put(root/'configs/kernel_inheritance.json',spec)
  condition=json.loads((R/'configs/parent_conditioning.json').read_text());put(root/'configs/parent_conditioning.json',condition)
  k={'schema':'h3-r27-kernel-gate-v1','passed':True,'NFE':0,'protocol_sha256':g.sha(root/'configs/protocol.json'),'source_sha256':{'configs/numerical.json':g.sha(root/'configs/numerical.json')},'cases':[{'actual_shape':True,'shape':[1,56,87366,128],'plan':{'seq_len':87366,'frame_rows':943,'latent_interval_half_open':[0,42],'query_interval_half_open':[47760,87366],'reference_video_segment':[7684,47290]},'passed':True,'checks':{'all':True}}]}
  put(root/'audit/gpu_dynamic_union_gate.json',k)
  for i in range(2):put(root/f'audit/evidence{i}.json',{'measured':i})
  inherited={'known_endpoint_gate_sha256':'known','inheritance_sha256':g.sha(root/'configs/r27_inheritance.json')}
  resource={'schema':'r45-root-resource-admission-v1','root_approved':True,'gpu_uuid':'GPU-REDACTED','kernel_gate_sha256':g.sha(root/'audit/gpu_dynamic_union_gate.json'),'known_endpoint_gate_sha256':'known','inheritance_sha256':inherited['inheritance_sha256'],'kernel_inheritance_sha256':g.sha(root/'configs/kernel_inheritance.json'),'protocol_sha256':g.sha(root/'configs/protocol.json'),'model_resident_measured_bytes':60*1024**3,'routing_increment_bound_bytes':2*1024**3,'decoder_peak_reserved_bytes':6*1024**3,'total_memory_bytes':80*1024**3,'estimated_combined_bytes':68*1024**3,'required_free_before_decoder_mib':12288,'scope':'single GPU isolated exec; runtime exact-parent admission remains mandatory','evidence':[{'file':str(root/f'audit/evidence{i}.json'),'sha256':g.sha(root/f'audit/evidence{i}.json')} for i in range(2)]}
  put(root/'audit/resource_admission.json',resource)
  return root,parent,resource,inherited,put
 def test_valid_scoped_inheritance_and_gpu3_resource(self):
  with tempfile.TemporaryDirectory() as d:
   r,p,v,i,put=self.fixture(d)
   with patch.object(g,'inherited_bridge',return_value=i):self.assertEqual(g.check(r)['kernel_gate_sha256'],v['kernel_gate_sha256'])
 def test_resource_wrong_gpu_protocol_or_approval_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r,p,v,i,put=self.fixture(d)
   for key,val in [('gpu_uuid','GPU-REDACTED'),('protocol_sha256','old'),('root_approved',False),('root_approved',1),('inheritance_sha256','old')]:
    bad=copy.deepcopy(v);bad[key]=val;put(r/'audit/resource_admission.json',bad)
    with patch.object(g,'inherited_bridge',return_value=i),self.assertRaises(ValueError):g.check(r)
 def test_actual_layout_cannot_be_inherited_from_short_prompt(self):
  with tempfile.TemporaryDirectory() as d:
   r,p,v,i,put=self.fixture(d);k=json.loads((r/'audit/gpu_dynamic_union_gate.json').read_text());k['cases'][0]['shape'][2]=87592;put(r/'audit/gpu_dynamic_union_gate.json',k);v['kernel_gate_sha256']=g.sha(r/'audit/gpu_dynamic_union_gate.json');put(r/'audit/resource_admission.json',v)
   with patch.object(g,'inherited_bridge',return_value=i),self.assertRaises(ValueError):g.check(r)
 def test_current_memory_or_evidence_failure_cannot_be_inherited(self):
  with tempfile.TemporaryDirectory() as d:
   r,p,v,i,put=self.fixture(d)
   bad=copy.deepcopy(v);bad['routing_increment_bound_bytes']=10*1024**3;bad['estimated_combined_bytes']=76*1024**3;put(r/'audit/resource_admission.json',bad)
   with patch.object(g,'inherited_bridge',return_value=i),self.assertRaises(ValueError):g.check(r)
   put(r/'audit/resource_admission.json',v);(r/'audit/evidence0.json').write_text('{}')
   with patch.object(g,'inherited_bridge',return_value=i),self.assertRaises(ValueError):g.check(r)
if __name__=='__main__':unittest.main()
