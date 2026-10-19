"""Preserve actual R65 source reports; record an explicit R66 reuse bridge."""
import argparse,shutil
from common import *

def validate_r65_report(report,binding,manifest,action,config):
 expected=source_item(action);reuse=config['reuse_r65']
 require(action in reuse['allowed_actions'],'only frozen R65 fresh41 sources may be imported')
 matches=[x for x in manifest['inputs'] if x['id']==expected['id']]
 require(len(matches)==1 and report['case']==matches[0] and report['case']['role']=='reference' and report['case']['sha256']==expected['sha256'],'R65 reference source differs')
 require(report['passed'] is True and report['manifest_sha256']==reuse['source_manifest_sha256'],'R65 actual reference report incomplete or wrong manifest')
 require(binding['frozen_numerical_tracker']['sha256']==sha(METRIC/'run_tracks.py') and binding['administrative_wrapper']['sha256']==reuse['wrapper_sha256'],'R65 tracker/wrapper differs')
 require(binding['root_registration']['consumer_freeze_sha256']==reuse['consumer_freeze_sha256'],'R65 fresh41 consumer identity differs')
 require(binding['root_registration']['input_manifest']['sha256']==report['manifest_sha256'],'R65 input admission differs')
 require(report['admission_before_cuda']['hostname']==binding['hostname'] and bool(report['admission_before_cuda']['gpu_name']),'R65 actual runtime hardware missing')
 return report

def import_r65(r65,action):
 c=verify_runtime();reuse=c['reuse_r65'];r65=Path(r65).resolve()
 require(str(r65) in [reuse['root_host41'],reuse['root_local']],'reuse requires exact R65 consumer archive')
 frozen(r65,'CONSUMER_FREEZE.json',reuse['consumer_freeze_sha256']);frozen(r65/'runtime/official_metric','RUNTIME_FREEZE.json',reuse['runtime_freeze_sha256'])
 require(sha(r65/'runtime/official_metric/SOURCE_INPUTS.json')==reuse['source_manifest_sha256'],'R65 fixed source manifest changed')
 folder=r65/'tracks/reference'/action;report=read(folder/'REPORT.json');binding=read(folder/'R65_BINDING.json')
 validate_r65_report(report,binding,read(r65/'runtime/official_metric/SOURCE_INPUTS.json'),action,c)
 require(binding['report']['sha256']==sha(folder/'REPORT.json') and report['tracks_sha256']==sha(folder/'tracks.pt'),'R65 actual tracks/report changed')
 old_item=report['case'];require(sha(r65/'runtime/official_metric'/old_item['file'])==old_item['sha256'],'R65 source bytes changed')
 dest=ROOT/'tracks/reference'/action;dest.mkdir(parents=True,exist_ok=False)
 for name in ['REPORT.json','tracks.pt','R65_BINDING.json']:shutil.copy2(folder/name,dest/name)
 prov=dest/'provenance';prov.mkdir()
 for name,path in [('SOURCE_INPUTS.json',r65/'runtime/official_metric/SOURCE_INPUTS.json'),('CONSUMER_FREEZE.json',r65/'CONSUMER_FREEZE.json'),('RUNTIME_FREEZE.json',r65/'runtime/official_metric/RUNTIME_FREEZE.json'),('track_shared.py',r65/'scripts/track_shared.py')]:shutil.copy2(path,prov/name)
 save(dest/'R66_SOURCE_REUSE.json',{'schema':'r66-explicit-r65-fresh41-source-reuse-v1','action':action,'source_sha256':source_item(action)['sha256'],'origin_root':str(r65),'origin_directory':str(folder),'report_preserved_byte_exact':True,'tracks_preserved_byte_exact':True,'files':{str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()},'runtime_hardware':report['admission_before_cuda'],'scope':'same action source reused across identities; generated reports remain pair-specific'})
 return dest

def validate_reuse(folder,action,config):
 folder=Path(folder);receipt=read(folder/'R66_SOURCE_REUSE.json');require(receipt['schema']=='r66-explicit-r65-fresh41-source-reuse-v1' and receipt['action']==action and receipt['source_sha256']==source_item(action)['sha256'],'source reuse identity differs')
 for name,digest in receipt['files'].items():require(not Path(name).is_absolute() and '..' not in Path(name).parts and sha(folder/name)==digest,'source reuse file changed')
 reuse=config['reuse_r65']
 for name,digest in [('SOURCE_INPUTS.json',reuse['source_manifest_sha256']),('CONSUMER_FREEZE.json',reuse['consumer_freeze_sha256']),('RUNTIME_FREEZE.json',reuse['runtime_freeze_sha256']),('track_shared.py',reuse['wrapper_sha256'])]:require(sha(folder/'provenance'/name)==digest,'R65 provenance changed')
 report=validate_r65_report(read(folder/'REPORT.json'),read(folder/'R65_BINDING.json'),read(folder/'provenance/SOURCE_INPUTS.json'),action,config)
 require(read(folder/'R65_BINDING.json')['report']['sha256']==sha(folder/'REPORT.json'),'original report binding differs')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--r65-root',type=Path,required=True);p.add_argument('--action',choices=('fitness','one_leg'),required=True);a=p.parse_args()
 with cpu_lock():print(import_r65(a.r65_root,a.action))
