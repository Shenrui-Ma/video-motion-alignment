"""Copy the existing R121 initial noise on the same server, with exact byte binding."""
from pathlib import Path
import shutil
from r123_contract import ROOT,read,sha,require

def prepare(root=ROOT):
 root=Path(root);c=read(root/'configs/parent_noise.json');source=Path(c['source_file']);manifest=Path(c['source_noise_manifest']);dest=root/'audit'/c['destination_filename']
 require(source.is_absolute() and source.is_file() and not source.is_symlink() and sha(source)==c['source_sha256'],'parent noise bytes differ')
 require(sha(manifest)==c['source_noise_manifest_sha256'],'parent noise manifest differs')
 previous=read(manifest);require(previous['signature']==c['signature'] and previous['actual_noise_streams']==c['actual_noise_streams'],'parent noise signature differs')
 require(dest.parent==root/'audit' and dest.name==c['destination_filename'],'noise destination invalid')
 if not dest.exists():
  with source.open('rb') as src,dest.open('xb') as out:shutil.copyfileobj(src,out)
 require(not dest.is_symlink() and sha(dest)==c['source_sha256'],'copied noise differs')
 return {'passed':True,'source':str(source),'destination':str(dest),'sha256':sha(dest),'actual_noise_streams':c['actual_noise_streams']}
