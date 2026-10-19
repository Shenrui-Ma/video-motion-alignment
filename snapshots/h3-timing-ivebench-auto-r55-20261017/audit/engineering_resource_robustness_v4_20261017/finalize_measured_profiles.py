"""Bind measured GPU evidence after root approval; CPU only, no service launch."""
import argparse,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from observer_import import t

def put(path,value):
 temporary=path.with_suffix(path.suffix+'.tmp')
 with temporary.open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(temporary,path)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root-approved-certificate',type=Path,required=True);args=parser.parse_args()
 t.require(ROOT==t.REMOTE_ROOT and not (ROOT/'deploy_manifest.json').exists(),'only unsealed actual remote root can finalize profiles')
 t.bindings(external=True)
 gate_path=ROOT/'audit/known_endpoint_90_gate.json';gate=t.read_json(gate_path)
 t.require(gate['schema']=='r55-full90-decoder-gate-v1' and gate['passed'] is True and gate['NFE']==0 and gate['model_forward_calls']==0 and all(gate['checks'].values()),'successful actual full90 gate required')
 t.require(gate['protocol_sha256']==t.PROTOCOL_SHA,'gate scientific protocol differs')
 for rel,digest in gate['source_sha256'].items():t.require(t.sha(ROOT/rel)==digest,'gate source changed: '+rel)
 t.require(t.sha(Path(gate['decode_file']))==gate['decode_sha256'],'actual decoder result changed')
 d=gate['decode'];t.require(d['status']=='complete' and d['decoded_shape']==[90,736,1312,3],'full90 decode output differs')
 cert=t.read_json(args.root_approved_certificate)
 t.require(args.root_approved_certificate.resolve()==ROOT/'audit/resource_admission.json','certificate must be the formal root admission path')
 t.require(cert['schema']=='r55-root-two-GPU-resource-admission-v1' and cert['root_approved'] is True and cert['main_gpu_uuid']==t.MAIN_UUID and cert['decoder_gpu_uuid']==t.DECODER_UUID,'root main certificate identity/approval differs')
 t.require(cert['protocol_sha256']==t.PROTOCOL_SHA and cert['decoder_gate_sha256']==t.sha(gate_path) and cert['kernel_gate_sha256']==t.sha(ROOT/'audit/gpu_dynamic_union_gate.json'),'root certificate evidence differs')
 t.require(cert['main_margin_bytes']>=1024**3 and cert['main_estimated_peak_bytes']>=cert['main_native_peak_reserved_bytes']+cert['routing_increment_bound_bytes']+cert['main_margin_bytes'],'main capacity margin differs')
 t.require(cert['main_estimated_peak_bytes']<=cert['main_total_memory_bytes'],'main capacity unsupported')
 t.require(len(cert['evidence'])>=2,'actual capacity evidence missing')
 for row in cert['evidence']:t.require(t.sha(Path(row['file']))==row['sha256'],'capacity evidence changed')
 dp=ROOT/'configs/decoder_memory_profile.json';mp=ROOT/'configs/main_memory_profile.json';bp=ROOT/'configs/observer_bindings.json'
 decoder=t.read_json(dp);main_profile=t.read_json(mp);t.require(decoder['status']==main_profile['status']=='PENDING','profiles already finalized')
 peak=d['max_memory_reserved_bytes'];t.require(type(peak) is int and peak>0,'invalid decoder allocation measurement')
 t.require(peak+decoder['safety_margin_bytes']<=cert['decoder_total_memory_bytes'],'decoder capacity unsupported')
 archive=ROOT/'audit/engineering_resource_robustness_v4_20261017/pending_profiles_before_final';archive.mkdir(exist_ok=False)
 for p in (dp,mp,bp):shutil.copyfile(p,archive/p.name)
 de=ROOT/'configs/decoder_memory_evidence/full90_gate.json';me=ROOT/'configs/main_memory_evidence/resource_admission.json'
 for source,destination in ((gate_path,de),(args.root_approved_certificate,me)):
  destination.parent.mkdir(parents=True,exist_ok=True)
  with destination.open('xb') as f:f.write(source.read_bytes());f.flush();os.fsync(f.fileno())
 decoder.update(status='MEASURED',evidence_file=str(de.relative_to(ROOT)),evidence_sha256=t.sha(de),peak_reserved_bytes=peak,required_free_bytes=peak+decoder['safety_margin_bytes'])
 main_profile.update(status='MEASURED_BOUND',evidence_file=str(me.relative_to(ROOT)),evidence_sha256=t.sha(me),required_free_bytes=cert['main_estimated_peak_bytes'])
 put(dp,decoder);put(mp,main_profile)
 bindings=t.read_json(bp)
 for rel in bindings['local_files']:bindings['local_files'][rel]=t.sha(ROOT/rel)
 for p in (de,me):bindings['local_files'][str(p.relative_to(ROOT))]=t.sha(p)
 put(bp,bindings)
 from prelaunch_gates import check
 from preflight import check as preflight
 from build_manifest import validate_final_profiles
 actual=check(ROOT);profiles=validate_final_profiles(ROOT);meta=preflight(ROOT,metadata_only=True)
 report={'status':'MEASURED_PROFILES_BOUND','protocol_sha256':t.PROTOCOL_SHA,'gates':actual,'profiles':profiles,'metadata_preflight_pass':meta['pass'],'bootstrap_binding_retained_at':gate['bootstrap_bindings'],'final_observer_bindings_sha256':t.sha(bp),'GPU_launch_performed':False}
 t.write_new(ROOT/'audit/engineering_resource_robustness_v4_20261017/MEASURED_PROFILES_BOUND.json',report)
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
