import hashlib,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXPECTED={'configs/source.pose.json': '8d731e0c55072c216d191729be21d6b42077f79b35dfdc5810c902fac8e6f8e4', 'configs/source_provenance.json': 'a4cc024978c319845de95b43fc5ed91bbdd54803bee4fd8c18f75ae7b565e6c9', 'configs/inherited_actual87361_kernel.json': 'f91a689f5141a1ca415430c2d9ac6b291d55cf1be65bee6a0f0513851a8ac577'}
class InheritedEvidenceTests(unittest.TestCase):
 def test_original_evidence_bytes_preserved(self):
  for name,digest in EXPECTED.items():
   self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
 def test_original_config_source_values_not_port_substituted(self):
  import json
  p=json.loads((ROOT/'configs/source.pose.json').read_text())
  self.assertEqual(p['frames'][38]['persons'][0]['coco17_score'][5],0.8498267531394958)
if __name__=='__main__':unittest.main()
