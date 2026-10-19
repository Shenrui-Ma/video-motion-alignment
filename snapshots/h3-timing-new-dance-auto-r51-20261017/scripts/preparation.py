"""Offline R51 template checks; no model import, network, process or GPU calls."""
import copy
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/data5/researcher/h3_runs/timing_new_dance_auto_r51_20261017'
PRIORITY = ('10264579', '6980766')


def selection_from_verdicts(verdicts):
    """Accept evidence-qualified verdicts; this function does not score observations."""
    if set(verdicts) != set(PRIORITY):
        raise ValueError('both predeclared candidate verdicts are required')
    if any(value is not None and type(value) is not bool for value in verdicts.values()):
        raise ValueError('verdict must be a strict boolean or pending null')
    for source in PRIORITY:
        if verdicts[source] is None:
            return {'status': 'WAITING_R47_FIXED_EVALUATION', 'selected_source_id': None}
        if verdicts[source]:
            return {'status': 'SELECTED_PENDING_ACTUAL_BINDINGS', 'selected_source_id': source}
    return {'status': 'NO_QUALIFYING_CASE_TEMPLATE_ONLY', 'selected_source_id': None}


def graph_preview(parent_graph, case):
    """Structured template only. Actual history must later equal the parent graph."""
    if case['source_id'] not in PRIORITY:
        raise ValueError('candidate outside predeclared set')
    if parent_graph['5']['inputs']['prompt'] != case['prompt']:
        raise ValueError('parent prompt differs')
    if parent_graph['6']['inputs']['noise_seed'] != case['seed']:
        raise ValueError('parent seed differs')
    if (parent_graph['21']['inputs']['image'],parent_graph['22']['inputs']['file']) != (case['portrait'],case['video']):
        raise ValueError('parent inputs differ')
    source = parent_graph['5']['inputs']
    if (source['width'],source['height'],source['length']) != (1312,736,141):
        raise ValueError('R51 preserves old141 geometry')
    if parent_graph['50']['class_type'] != 'H3TemporalRouter' or parent_graph['50']['inputs']['mode'] != 'native':
        raise ValueError('requires Native parent graph')
    graph = copy.deepcopy(parent_graph)
    run = 'r51_source_'+case['source_id']+'_seed'+str(case['seed'])+'_auto'
    shared = 'r51_source_'+case['source_id']+'_shared'
    for node in ('5','6'):
        graph[node]['inputs']['audit_dir'] = REMOTE+'/audit'
    graph['51']['inputs']['source_audit_dir'] = REMOTE+'/audit'
    graph['52']['inputs']['output_dir'] = REMOTE+'/audit/x0'
    graph['5']['inputs']['run_id'] = shared
    graph['51']['inputs']['source_run_id'] = shared
    for node in ('6','51','52'):
        graph[node]['inputs']['run_id'] = run
    graph['6']['inputs']['pair_id'] = run+'_noise'
    graph['14']['inputs']['filename_prefix'] = run
    graph['50'] = {'class_type':'H3AutomaticWindowRouter','inputs':{
        'model':['41',0],'positive':['51',0],'run_id':run,'audit_dir':REMOTE+'/audit/counterfactual'}}
    return graph


def check(root=ROOT):
    root=Path(root)
    inventory=json.loads((root/'audit/REUSE_INVENTORY.json').read_text())
    archive=root/inventory['archive']
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=inventory['archive_sha256']:
        raise ValueError('source archive changed')
    with zipfile.ZipFile(archive) as zipped:
        if set(zipped.namelist())!=set(inventory['files']) or len(zipped.namelist())!=len(inventory['files']):
            raise ValueError('source archive inventory differs')
        for name,record in inventory['files'].items():
            data=zipped.read(name)
            if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:
                raise ValueError('source bytes changed: '+name)
    for name,record in inventory['reference_copies'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError('original evidence copy changed: '+name)
    selection=json.loads((root/'configs/SELECTION.json').read_text())
    decision=selection_from_verdicts(selection['stable_delay_verdicts'])
    if any(selection[k]!=decision[k] for k in ('status','selected_source_id')):
        raise ValueError('selection record contradicts predeclared priority')
    parent=json.loads((root/'configs/PARENT_CLOSURE.json').read_text())
    resource=json.loads((root/'configs/RESOURCE_PENDING.json').read_text())
    if parent['ready'] is not False or resource['approved'] is not False or selection['launch_allowed'] is not False:
        raise ValueError('this preparation checkpoint cannot claim runtime admission')
    return {'status':'PREPARATION_VERIFIED_NOT_DEPLOYABLE','selected_source_id':selection['selected_source_id'],
            'reused_source_files':len(inventory['files']),
            'exact_numerical_files':len(inventory['exact_numerical_files']),
            'actual_parent_closed':False,'resource_admitted':False}


if __name__=='__main__':
    print(json.dumps(check(),indent=2))
