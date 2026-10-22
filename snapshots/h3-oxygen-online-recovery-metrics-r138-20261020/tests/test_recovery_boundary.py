import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c

def fixture():
    cfg=c.read(c.ROOT/'configs/RESUME.json');a=copy.deepcopy(c.read(c.ROOT/'configs/OLD_AUDIT_COMPACT.json'));old=copy.deepcopy(a['counterfactual']);x=a['counterfactual'];x['branches']=[b for b in x['branches'] if b['physical_index']<9]
    for b in x['branches']:b.update(execution_generation='R133',original_file=b['file'],file='/new/'+Path(b['file']).name)
    for s in x['steps']:s.update(execution_generation='R133',chosen_file='/new/'+Path(s['chosen_file']).name)
    x['pair_gates']=[g for g in x['pair_gates'] if g['gate']!='native_prefix' or g['physical_index']<9]
    restored=next(b for b in old['branches'] if b['physical_index']==9 and b['branch']=='native')
    for i in range(9,20):
        b=copy.deepcopy(restored);b.update(physical_index=i,nfe_index=len(x['branches']),execution_generation='R138');x['branches'].append(b)
        s=copy.deepcopy(old['steps'][8]);s.update(physical_index=i,execution_generation='R138');s['decision']['chosen_full']=False;x['steps'].append(s)
        m=copy.deepcopy(old['measurements'][8]);m['physical_index']=i;x['measurements'].append(m)
        x['pair_gates'].append({'gate':'native_prefix','physical_index':i,'branch':'native','status':'not_applicable'})
    x.update(logical_model_nfe=23,logical_euler_updates=20,callback_count=20,inputs=[{'physical_index':i} for i in range(9,20)])
    x['resume']={'schema':'r138-resume-lineage-v1','config_sha256':c.sha(c.ROOT/'configs/RESUME.json'),'source_run':cfg['source_run'],'source_audit':cfg['source_audit'],'source_release':cfg['source_release'],'start_physical_index':9,'inherited_complete_updates':9,'inherited_logical_model_nfe':12,'old_actual_executed_model_nfe':13,'reconstruction_model_nfe':0,'initial_rng_bytes_available':False,'replayed_archival_callbacks':list(range(9)),'first_restored_native_exact':True,'prefix_reconstruction_exact':True,'new_initial_binding':old['pair_gates'][0],'discarded_old_execution':restored,'state9_signature':restored['same_input'],'logical_model_nfe':23,'actual_new_model_nfe':11,'actual_all_generations_model_nfe':24,'actual_new_euler_updates':11,'logical_euler_updates':20}
    x['resume']['conditioning_identity_equivalence']=c.condition_equivalence(x['conditioning'],old['conditioning'])
    a.update(status='complete',completed_forward_calls=23,completed_calls=1150,routed_calls=150,calls_by_forward=[50]*23)
    a['compact_receipt'].update(extractor_sha256=c.sha(c.ROOT/'scripts/compact_audit.py'),measurements_complete=20,original_file=str(Path(c.config()['producer_remote'])/f'audit/counterfactual/{c.RUN}.json'))
    return a

class Boundary(unittest.TestCase):
    def test_valid_logical_and_actual_cost(self):
        r=c.verify_counts(fixture());self.assertEqual((r['logical_NFE'],r['actual_all_generations_NFE']),(23,24));self.assertEqual(r['old_actual_NFE'],13)
    def test_old_failed_call_cannot_disappear(self):
        a=fixture();a['counterfactual']['resume']['actual_all_generations_model_nfe']=23
        with self.assertRaisesRegex(ValueError,'omits failed work'):c.verify_counts(a)
    def test_changed_inherited_measurement(self):
        a=fixture();a['counterfactual']['measurements'][1]['response_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'inherited observer'):c.verify_counts(a)
    def test_new_owner_generation_cannot_relabel_old_step(self):
        a=fixture();a['counterfactual']['steps'][1]['execution_generation']='R138'
        with self.assertRaisesRegex(ValueError,'execution generation'):c.verify_counts(a)
    def test_restored_prediction_must_match(self):
        a=fixture();b=next(b for b in a['counterfactual']['branches'] if b['physical_index']==9);b['raw_stream_signatures'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'restored Native9 differs'):c.verify_counts(a)
    def test_missing_new_checkpoint(self):
        a=fixture();a['counterfactual']['inputs'].pop()
        with self.assertRaisesRegex(ValueError,'checkpoint indices'):c.verify_counts(a)
    def test_prefix_equality_not_extended_after_first_on(self):
        a=fixture();g=next(g for g in a['counterfactual']['pair_gates'] if g.get('physical_index')==10);g['status']='pass'
        with self.assertRaisesRegex(ValueError,'outside common prefix'):c.verify_counts(a)
    def test_partial_old_attempt_not_success(self):
        a=c.read(c.ROOT/'configs/OLD_AUDIT_COMPACT.json')
        with self.assertRaises((ValueError,KeyError)):c.verify_counts(a)
    def test_cross_root_observation_only(self):
        old=c.config()['old_producer_remote'];self.assertTrue(c.safe_path(old+'/audit/observations/a/pose/native.pose.json'))
        with self.assertRaises(ValueError):c.safe_path(old+'/audit/x0/large.pt')
    def test_no_duplicate_new_euler_checkpoint(self):
        a=fixture();a['counterfactual']['inputs'][-1]['physical_index']=18
        with self.assertRaisesRegex(ValueError,'checkpoint indices'):c.verify_counts(a)
    def test_two_uuid_fields_allowed_only(self):
        a=fixture();old=copy.deepcopy(a['counterfactual']['conditioning']);new=copy.deepcopy(old)
        for stage in ('original','processed'):new['tree'][stage]['positive'][0]['uuid']='11111111-1111-4111-8111-111111111111'
        new['sha256']=c.hashlib.sha256(c.json.dumps(new['tree'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        proof=c.condition_equivalence(new,old);self.assertEqual(len(proof['equivalent_except_paths']),2)
    def test_non_uuid_condition_change_rejected(self):
        a=fixture();old=copy.deepcopy(a['counterfactual']['conditioning']);new=copy.deepcopy(old);new['tree']['original']['positive'][0]['unregistered']=1
        new['sha256']=c.hashlib.sha256(c.json.dumps(new['tree'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,'beyond the two'):c.condition_equivalence(new,old)
    def test_complete_generation_hash_still_required(self):
        a=fixture();a['counterfactual']['branches'][-1]['condition_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'complete condition hash'):c.verify_counts(a)

if __name__=='__main__':unittest.main()
