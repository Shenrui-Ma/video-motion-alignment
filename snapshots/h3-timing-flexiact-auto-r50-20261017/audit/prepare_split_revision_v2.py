"""One-time administrative migration, after preserved producer_v1 seal."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[1];S=R.parent/'h3-timing-ivebench-auto-r55-20261017'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
old=read(R/'audit/revisions/producer_v1/deploy_manifest.json')
assert sha(R/'deploy_manifest.json')=='4f1b4fbf3a30ea5baa27e9cd4feff3ac163628a61c66db14f5eb525a5c66e3f0'
assert all(sha(R/n)==v['sha256'] for n,v in old['files'].items())
e=R/'configs/engineering_v2';e.mkdir(exist_ok=False)
for src,dst in [('configs/protocol.json','previous_protocol.json'),('audit/gpu_dynamic_union_gate.json','previous_kernel_gate.json'),('audit/known_endpoint_158_gate.json','previous_decoder_gate.json'),('audit/root_allocator_profile_158.json','allocator_profile_158.json')]:shutil.copy2(R/src,e/dst)
protocol=read(R/'configs/protocol.json');resources=protocol['resources'];resources.update(decoder_uuid='GPU-REDACTED',single_gpu_isolated_decoder=False,decoder_idle_min_free_MiB=45000,decoder_idle_max_used_MiB=1024)
resources.pop('parent_free_min_MiB')
write(R/'configs/protocol.json',protocol);shutil.copy2(R/'configs/protocol.json',R/'PROTOCOL.json');digest=sha(R/'configs/protocol.json')
p=R/'extensions/H3AutomaticWindowRouter/transport.py';text=p.read_text();source=(S/'extensions/H3AutomaticWindowRouter/transport.py').read_text();a=source.index('def validate_separate_decoder(');b=source.index('\ndef validate_response(',a)
a0=text.index('def validate_co_resident(');b0=text.index('\ndef validate_response(',a0);text=text[:a0]+source[a:b]+text[b0:]
text=text.replace("PROTOCOL_SHA='9eabab0ea6ad9533711ac640a13ba0bfaacd806c1792516c2b8d289165760e5d'",'PROTOCOL_SHA='+repr(digest)).replace("DECODER_UUID='GPU-REDACTED'","DECODER_UUID='GPU-REDACTED'")
p.write_text(text)
for name in ['run_observer.py','gpu_release_gate.py']:
 shutil.copy2(S/'scripts'/name,R/'scripts'/name)
p=R/'scripts/decode_live_child.py';text=p.read_text().replace('t.co_resident_admission','t.separate_decoder_admission');source=(S/'scripts/decode_live_child.py').read_text();a=source.index('def assert_idle_gpu(');b=source.index('\ndef load_snapshot(',a);a0=text.index('def assert_idle_gpu(');b0=text.index('\ndef load_snapshot(',a0);p.write_text(text[:a0]+source[a:b]+text[b0:])
p=R/'scripts/known_endpoint_decode_bridge.py';text=p.read_text().replace('import sys,os,time','import sys,os,time,json').replace("    directory=Path(os.environ['R50_DECODER_APPROVAL_DIRECTORY'])","    parent=json.loads(sys.argv[sys.argv.index('--parent-json')+1])\n    t.install_lifetime_guard(parent)\n    directory=Path(os.environ['R50_DECODER_APPROVAL_DIRECTORY'])").replace('live.t.co_resident_admission','live.t.separate_decoder_admission');p.write_text(text)
p=R/'scripts/service.py';text=p.read_text();needle="    for row in processes:\n        if row['gpu_uuid'] == GPU:\n";assert needle in text;text=text.replace(needle,"    for row in processes:\n        if row['gpu_uuid'] == t.DECODER_UUID:\n            raise RuntimeError('R50 isolated decoder GPU has active compute')\n        if row['gpu_uuid'] != GPU and proc_uid(row['pid']) == os.getuid():\n            raise RuntimeError('R50 reserves both owned GPU slots for main model and isolated decoder')\n        if row['gpu_uuid'] == GPU:\n",1);p.write_text(text)
p=R/'scripts/known_endpoint_158_gate.py';text=p.read_text().replace("known_endpoint_158';","known_endpoint_158_split_v2';").replace('known_endpoint_158/native019.pt','known_endpoint_158_split_v2/native019.pt').replace("'scope':'Exact live decoder, full158 shape and standalone peak; root separately evaluates co-residence. No original RGB equality claim.'","'scope':'Exact live decoder on dedicated GPU2, full158 shape and standalone peak; compares to prior same-endpoint GPU3 decode.'")
text=text.replace("        checks={'complete':", "        previous=t.read_json(ROOT/'configs/engineering_v2/previous_decoder_gate.json')['decode']\n        checks={'revision1_RGB_exact':decoded['preencode_rgb24_frame_sha256']==previous['preencode_rgb24_frame_sha256'],\n                'revision1_tensor_exact':decoded['decoded_tensor_sha256']==previous['decoded_tensor_sha256'],\n                'dedicated_GPU2':admission['uuid']==t.DECODER_UUID and t.DECODER_UUID!=t.MAIN_UUID,\n                'complete':")
p.write_text(text)
write(R/'FREEZE.json',{'schema':'r50-production-science-freeze-v2-resource-placement','files':{'PROTOCOL.json':digest,'configs/protocol.json':digest},'prior_manifest_sha256':sha(R/'audit/revisions/producer_v1/deploy_manifest.json'),'science_change':'none; protocol resources only'})
p=R/'README.txt';p.write_text(p.read_text().rstrip()+'\n\nEngineering revision v2: GPU3 holds the unchanged main model; GPU2 executes fresh isolated full158 VAE decoders. Both owned GPU slots are reserved. The 12 GiB co-resident gate was not supported by actual allocator measurements; dedicated decoder admission requires >=45000 MiB free, <=1024 MiB used, zero utilization and no compute process. Numerical policy, packed layouts and all R49 parent data remain unchanged.\n')
print(json.dumps({'protocol_sha256':digest,'prepared':True}))
