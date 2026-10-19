import copy
import json
from pathlib import Path
import tempfile
import unittest

import replay as r


def row(window=(40, 55), feature='left_arm_direction', gain=.75,
        lag=8, baseline='delayed_candidate'):
    return {'window':list(window), 'feature':feature, 'status':'measured',
            'baseline':baseline, 'min_gain':gain,
            'comparison':{str(c):{'proposal_lag':lag, 'null_comparisons':[
                {'null_lag':e,'null_cost':1.,'proposal_cost':1.-gain}
                for e in range(-2,3)]} for c in (.3,.5)}}


def ob(index, rows=(), unknown=False):
    return {'physical_index':index,'status':'unknown_visibility' if unknown else 'measured',
            'windows':list(rows)}


class Decisions(unittest.TestCase):
    def test_first_observation_cannot_activate_local_or_global(self):
        x=r.replay([ob(0,[row()])])['steps'][0]
        self.assertFalse(x['local_compatible']['chosen_full'])
        self.assertFalse(x['global_mean_W2']['chosen_full'])
        self.assertTrue(x['one_step']['chosen_full'])

    def test_persistent_same_interval_activates(self):
        x=r.replay([ob(0,[row()]),ob(1,[row()])])['steps'][1]
        self.assertTrue(x['local_compatible']['chosen_full'])
        self.assertTrue(x['global_mean_W2']['chosen_full'])

    def test_different_regions_scalar_on_local_off(self):
        x=r.replay([ob(0,[row((0,15))]),ob(1,[row((80,95))])])['steps'][1]
        self.assertFalse(x['local_compatible']['chosen_full'])
        self.assertTrue(x['global_mean_W2']['chosen_full'])

    def test_different_arms_do_not_persist(self):
        x=r.replay([ob(0,[row(feature='left_arm_direction')]),
                    ob(1,[row(feature='right_arm_direction')])])['steps'][1]
        self.assertFalse(x['local_compatible']['chosen_full'])

    def test_unknown_breaks_history(self):
        x=r.replay([ob(0,[row()]),ob(1,unknown=True),ob(2,[row()])])['steps'][2]
        self.assertFalse(x['local_compatible']['chosen_full'])
        self.assertFalse(x['global_mean_W2']['chosen_full'])
        self.assertEqual(x['global_mean_W2']['reason'],'global_mean_W2_UNKNOWN')

    def test_gain_equal_threshold_is_not_candidate(self):
        x=r.replay([ob(0,[row(gain=.5)]),ob(1,[row(gain=.5)])])['steps'][1]
        self.assertFalse(x['one_step']['chosen_full'])
        self.assertFalse(x['global_mean_W2']['scalar_gate_on'])

    def test_global_includes_advanced_but_does_not_route_it(self):
        a=row(baseline='advanced_candidate',lag=-10)
        x=r.replay([ob(0,[a]),ob(1,[a])])['steps'][1]['global_mean_W2']
        self.assertTrue(x['scalar_gate_on'])
        self.assertFalse(x['chosen_full'])
        self.assertEqual(x['current_global']['advanced_contributors'],1)

    def test_missing_excluded_negative_clipped(self):
        a=row(gain=-.1)
        unknown={'status':'unknown'}
        x=r.global_score([row(),a,unknown])
        self.assertEqual(x['measured_count'],2)
        self.assertEqual(x['score'],.375)
        self.assertEqual(x['negative_gain_clipped'],1)

    def test_lag_jump_does_not_change_original_policy(self):
        x=r.replay([ob(0,[row(lag=3)]),ob(1,[row(lag=23)])])['steps'][1]
        self.assertTrue(x['local_compatible']['chosen_full'])
        e=x['compatible_lag_edges'][0]
        self.assertTrue(e['same_feature'])
        self.assertEqual(e['max_absolute_delta_frames'],20)
        self.assertTrue(e['any_delta_over_2_descriptive_only'])

    def test_shared_part_edges_are_distinguished(self):
        x=r.replay([ob(0,[row(feature='arm_direction')]),ob(1,[row()])])['steps'][1]
        self.assertFalse(x['compatible_lag_edges'][0]['same_feature'])
        self.assertEqual(x['compatible_lag_edges'][0]['shared_arms'],['left'])

    def test_overlap_chain_representative_leaves_union_out(self):
        rows=[row((0,15),gain=.8),row((12,27)),row((24,39))]
        x=r.replay([ob(0,rows),ob(1,rows)])['steps'][1]['component_coverage']
        self.assertEqual(len(x),1)
        self.assertEqual(x[0]['span'],[0,39])
        self.assertEqual(x[0]['representative_window'],[0,15])
        self.assertEqual(x[0]['rgb_coverage_fraction'],.4)
        self.assertTrue(x[0]['excluded_bins'])

    def test_exact_actual_decision_and_mutation_rejection(self):
        obs=[ob(0,[row()]),ob(1,[row()])]
        expected=r.replay(obs)
        actual=[{'physical_index':i,'decision':s['local_compatible']}
                for i,s in enumerate(expected['steps'])]
        r.replay(obs,actual)
        bad=copy.deepcopy(actual);bad[1]['decision']['latent_bins']=[]
        with self.assertRaisesRegex(ValueError,'actual local policy mismatch'):
            r.replay(obs,bad)

    def test_zero_frame_nominal_mapping_and_union(self):
        self.assertEqual(r.bins_for([[50,65]])[0],list(range(14,20)))
        self.assertEqual(r.bins_for([[0,0]])[0],[0])
        self.assertEqual(r.bins_for([[140,140]])[0],[41])
        self.assertEqual(r.bins_for([[0,0],[0,0]])[0],[0])

    def test_duplicate_or_missing_window_inventory_rejected(self):
        p={'source_pose_sha256':'source'}
        x={'schema':'r27-whole-timeline-observation-v1','physical_index':0,
           'source_pose_sha256':'source','thresholds':[.3,.5],'status':'measured','windows':[]}
        with self.assertRaisesRegex(ValueError,'scan window'):
            r.validate_observer(x,0,p)
        self.assertEqual(len(r.expected_rows()),186)

    def test_no_rows_global_is_unknown_not_zero(self):
        self.assertEqual(r.global_score([])['status'],'UNKNOWN')
        self.assertIsNone(r.global_score([])['score'])

    def test_invalid_gain_and_sequence_rejected(self):
        with self.assertRaisesRegex(ValueError,'gain'):
            r.global_score([row(gain=float('nan'))])
        with self.assertRaisesRegex(ValueError,'observer order'):
            r.replay([ob(1,[row()])])

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'unsafe'):
                r.inside(Path(td),'../x')
            with self.assertRaisesRegex(ValueError,'unsafe'):
                r.inside(Path(td),'/etc/passwd')


def make_archive(root):
    """Complete synthetic JSON chain, no models/tensors/real observations."""
    inv={};remote='/synthetic';run='synthetic'
    def put(rel,value):
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value));inv[rel]={'sha256':r.sha(p),'bytes':p.stat().st_size}
        return remote+'/'+rel,inv[rel]['sha256']
    conf={'cases':[{'run_id':run}]};_,ph=put('configs/protocol.json',conf)
    _,source_sha=put('configs/source.pose.json',{'synthetic_source':True})
    measurements=[];branches=[];obs=[]
    for i in range(20):
        prefix='audit/observations/step'+str(i)
        endpoint='audit/counterfactual/endpoint'+str(i)+'.pt'
        inv[endpoint]={'sha256':'tensor'+str(i),'bytes':0}
        common={'physical_index':i,'nfe_index':i,'seed':1,'sigma':1.-i/20,
                'condition_sha256':'condition','reference_sha256':'reference'}
        native=dict(common,branch='native',file=remote+'/'+endpoint,file_sha256='tensor'+str(i),
                    raw_stream_signatures=[{'sha256':'video'},{'sha256':'audio'}])
        req=dict(common,run_id=run,branch='native',request_id='r'+str(i),endpoint_file_sha256='tensor'+str(i))
        rp,rh=put(prefix+'/request.json',req)
        posep,poseh=put(prefix+'/pose.json',{'synthetic':True})
        o=dict(ob(i,unknown=True),schema='r27-whole-timeline-observation-v1',
               source_pose_sha256=source_sha,edited_pose_sha256=poseh,thresholds=[.3,.5])
        op,oh=put(prefix+'/observer.json',o);obs.append(o)
        res=dict(common,status='complete',request_id='r'+str(i),request_sha256=rh,
                 endpoint_file_sha256='tensor'+str(i),observer={'file':op,'sha256':oh},
                 pose={'file':posep,'sha256':poseh})
        sp,sh=put(prefix+'/response.json',res)
        measurements.append({'physical_index':i,'status':'complete','request_file':rp,'request_sha256':rh,
                             'response_file':sp,'response_sha256':sh,'observer':o})
        branches.append(native)
    steps=[{'physical_index':i,'decision':x['local_compatible']}
           for i,x in enumerate(r.replay(obs)['steps'])]
    put('audit/counterfactual/'+run+'.json',{'status':'complete','counterfactual':{
        'steps':steps,'measurements':measurements,'branches':branches,'actual_euler_updates':20,'callback_count':20}})
    put('logs/'+run+'_history.json',{'status':{'completed':True,'status_str':'success'}})
    (root/'FILE_INVENTORY.json').write_text(json.dumps(inv))
    (root/'RUNTIME_GATE.json').write_text(json.dumps({'status':'pass'}))
    (root/'RUN_GATE.json').write_text(json.dumps({'passed':True,'run_id':run,
        'runtime':{'status':'pass'},'file_inventory_sha256':r.sha(root/'FILE_INVENTORY.json')}))
    protocol={'allowed_runs':[run],'producer_root_remote':remote,
              'producer_protocol_sha256':ph,'source_pose_sha256':source_sha}
    return protocol


class Ingestion(unittest.TestCase):
    def test_completed_raw_chain(self):
        with tempfile.TemporaryDirectory() as td:
            p=make_archive(Path(td));run,obs,steps,prov=r.ingest(td,p)
            self.assertEqual(run,'synthetic');self.assertEqual(len(obs),20)
            r.replay(obs,steps)
            self.assertEqual(len(prov['endpoint_hash_chain']),20)
            self.assertFalse(prov['tensor_bytes_loaded'])

    def test_raw_observer_replacement_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=make_archive(root)
            (root/'audit/observations/step0/observer.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'raw archive hash mismatch'):
                r.ingest(root,p)

    def test_incomplete_gate_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=make_archive(root)
            (root/'RUN_GATE.json').write_text(json.dumps({'passed':False,'run_id':'synthetic'}))
            with self.assertRaisesRegex(ValueError,'completed registered'):
                r.ingest(root,p)

    def test_inventory_replacement_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=make_archive(root)
            (root/'FILE_INVENTORY.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'inventory SHA'):
                r.ingest(root,p)

    def test_gate_runtime_replacement_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=make_archive(root)
            (root/'RUNTIME_GATE.json').write_text(json.dumps({'status':'pass','changed':True}))
            with self.assertRaisesRegex(ValueError,'runtime result differs'):
                r.ingest(root,p)


if __name__=='__main__':
    unittest.main()
