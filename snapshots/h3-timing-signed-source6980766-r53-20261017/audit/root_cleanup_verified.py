"""Release the exact R53 service only after its completed archive is verified."""
from pathlib import Path
import argparse,hashlib,json,os,sys
R=Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017')
RUN='r53_source6980766_seed2026101701_signed_auto'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main(expected_sha):
    protocol=read(R/'configs/protocol.json');run=protocol['cases'][0]['run_id']
    assert len(protocol['cases'])==1 and '6980766' in run
    arc=R/'analysis/postrun/captured'/run
    gate=arc/'RUN_GATE.json';assert sha(gate)==expected_sha
    record=read(gate);owner=read(R/'processes/service.json')
    assert record['passed'] is True and record['owner']==owner and record['runtime']['status']=='pass'
    assert record['manifest_sha256']==sha(R/'deploy_manifest.json')
    assert record['file_inventory_sha256']==sha(arc/'FILE_INVENTORY.json')
    assert owner['pid']==63582 and owner['identity']['uid']==os.getuid()==1016 and owner['identity']['start_ticks']=='2625625538'
    proc=Path('/proc/63582')
    if proc.exists():assert sha(proc/'cmdline')=='044785b36f8bea04b6e64bcebbbbf67b6bfd08a76ccd6e28f8a5841fbaf996d4'
    sys.path[:0]=[str(R/'scripts'),'/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps']
    import service
    queue=service.queue_at(service.PORT)
    assert not queue['queue_running'] and not queue['queue_pending']
    service.stop(expected_record=owner)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-gate-sha',required=True);main(p.parse_args().run_gate_sha)
