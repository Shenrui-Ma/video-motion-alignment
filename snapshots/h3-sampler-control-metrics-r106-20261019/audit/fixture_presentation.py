from pathlib import Path
import json,tempfile,shutil,importlib.util
from unittest.mock import patch
R=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('c',R/'scripts/consume.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
with tempfile.TemporaryDirectory(prefix='r106_consumer_fixture_') as d:
 root=Path(d);inc=root/'incoming';inc.mkdir();show=root/'showcase';audit=root/'audit';download=root/'downloads';download.mkdir()
 source=c.PRODUCER/'inputs/short_0252_video.mp4'
 for name in ('source','euler','res_multistep'):shutil.copy2(source,inc/(name+'.mp4'))
 c.put(inc/'gate.json',{'FIXTURE':True});c.put(inc/'COLLECTION.json',{'FIXTURE':True,'files':{p.name:c.sha(p) for p in inc.iterdir()}})
 with patch.multiple(c,ROOT=root,INC=inc,SHOW=show,AUDIT=audit,DOWNLOAD=download),patch.object(c,'validate_collected',return_value=None):c.build()
 p=c.read(show/'PRESENTATION.json');mf=c.read(root/'prepared/MF_INPUTS.json')
 assert len(p['all_frame_pages'])==17 and p['comparison']['properties']['count']==98
 assert set(mf['files'])=={'source','euler','res_multistep'} and all(x['frame_count']==98 for x in mf['files'].values())
 result={'passed':True,'synthetic_fixture_only':True,'source_repeated_for_three_columns':True,'model_outputs_used':False,'render_frames':98,'pages':17,'column_labels':p['column_labels'],'metric_lossless_crop_checks':3,'temporary_outputs_removed_on_exit':True,'actual_output_status':'PENDING'}
c.put(R/'audit/PRESENTATION_FIXTURE.json',result);print(json.dumps(result))
