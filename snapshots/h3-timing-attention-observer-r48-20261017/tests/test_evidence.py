import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from verify_completed import validate_report,inside
from r46_contract import read

class EvidenceTests(unittest.TestCase):
    def valid(self):
        s=read(ROOT/'configs/sources.json')['bad']
        r={'schema':'r46-single-state-report-v1','label':'bad','status':'complete','source_run':s['source_run'],'seed':s['seed'],
           'condition_sha256':s['condition']['sha256'],'raw_input_signature':s['raw_input']['packed_signature'],
           'DiT_NFE':1,'attempted_forwards':1,'completed_forwards':1,'completed_blocks':50,'native_attention_calls':50,
           **{k:0 for k in ['Euler_updates','ordinary_callbacks','VAE_calls','Qwen_calls','routed_calls']},
           **{k:True for k in ['Native_AV_bitwise_equal','input_sigma_grid_condition_RNG_unchanged','original_UUID_restored','materialization_rng_unchanged']},
           'actual_sigma':s['full_grid'][4],'full_grid':s['full_grid'],
           'output_head':{'index':4,'sigma':s['full_grid'][4],'sigma_next':s['full_grid'][5],'pdd_active':False,'bank_size':1,'shifts':[12.,3.]},
           'probe':{'block':25,'heads':[0,14,28,42],'queries_per_head':1050,
                    'quality':{'status':'PASS','gates':{k:True for k in ['finite','group_lse','subset_lse','probability_sum','query_lse_unchanged']},'additional_attention_calls':43,'clamped':False},
                    'selected_original_QKV_output_exact':True,'global_rng_unchanged':True,'original_output_not_passed_to_statistics':True,'full_QKV_copy':False}}
        from test_sigma_guard import fixture
        r['sigma_path']=fixture()[-1]
        return r,s
    def test_matching_schema(self):r,s=self.valid();validate_report(r,'bad',s)
    def test_failed_or_wrong_source_counts(self):
        for key,value in [('status','failed'),('seed',2026101313),('DiT_NFE',0),('attempted_forwards',2),('completed_forwards',0),('Euler_updates',1),('Native_AV_bitwise_equal',False)]:
            r,s=self.valid();r[key]=value
            with self.assertRaises(ValueError):validate_report(r,'bad',s)
    def test_numerical_unknown_rejected(self):
        r,s=self.valid();r['probe']['quality']['status']='UNKNOWN_NUMERICAL'
        with self.assertRaises(ValueError):validate_report(r,'bad',s)
    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):inside(ROOT,ROOT/'../other/attention.pt')
        with self.assertRaises(ValueError):inside(ROOT,'attention.pt')

if __name__=='__main__':unittest.main()
