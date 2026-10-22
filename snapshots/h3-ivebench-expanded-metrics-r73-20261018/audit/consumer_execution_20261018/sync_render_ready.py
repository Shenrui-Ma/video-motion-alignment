"""CPU-only portable intake and presentation of the five frozen actual pairs."""
from pathlib import Path
import base64
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
REMOTE = '/data5/researcher/h3_runs/ivebench_expanded_metrics_r73_20261018'
PYTHON = '/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
SOURCES = ('short_0252', 'short_0344', 'short_0065', 'short_0135', 'short_0035')
ENV = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1')
HTML = Path('/Users/researcher/Downloads/H3_IVEBench_P1五条新素材_固定引导_20261018.html')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def remote_ready(source):
    code = 'import json;from pathlib import Path;p=Path(' + repr(REMOTE + '/prepared/' + source + '/READY.json') + ');print(json.dumps(json.loads(p.read_text()) if p.exists() else None))'
    result = subprocess.run(['ssh', 'H3_SERVER_A', 'python3 -c ' + shlex.quote(code)], text=True, capture_output=True, timeout=30, check=True)
    return json.loads(result.stdout)


def sync(source):
    code = '''
from pathlib import Path
import hashlib, io, json, sys, tarfile
r=Path(REMOTE); source=SOURCE
ready=json.loads((r/'prepared'/source/'READY.json').read_text());assert ready['passed'] is True
paths=list((r/'incoming'/source).glob('*'))
paths += [r/'prepared'/source/name for name in ('READY.json','METRIC_INPUTS.json','source_score.mp4','native_score.mp4','forced_score.mp4')]
assert all(p.is_file() and p.suffix in ('.mp4','.json') and p.stat().st_size < 200000000 for p in paths)
manifest=[{'path':str(p.relative_to(r)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths)]
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as t:
 for p in sorted(paths):t.add(p,arcname=str(p.relative_to(r)))
 raw=(json.dumps(manifest,indent=2)+'\\n').encode();info=tarfile.TarInfo('REMOTE_MEDIA_MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
'''.replace('Path(REMOTE)', 'Path(' + repr(REMOTE) + ')').replace('source=SOURCE', 'source=' + repr(source))
    archive = AUDIT / (source + '_actual_media.tar')
    if not archive.exists():
        partial=archive.with_suffix('.partial')
        with partial.open('wb') as out:
            subprocess.run(['ssh', 'H3_SERVER_A', 'python3 -c ' + shlex.quote(code)], stdout=out, check=True, timeout=600)
        partial.rename(archive)
    with tarfile.open(archive) as t:
        manifest=json.load(t.extractfile('REMOTE_MEDIA_MANIFEST.json'))
        for item in manifest:
            name=item['path'];assert not name.startswith('/') and '..' not in Path(name).parts
            data=t.extractfile(name).read();assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
            dst=ROOT/name
            if dst.exists(): assert dst.read_bytes()==data, 'Existing actual evidence differs: '+name
            else: dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
    (AUDIT/(source+'_MEDIA_SYNC.json')).write_text(json.dumps({'archive':str(archive),'archive_sha256':sha(archive),'files':manifest},indent=2)+'\n')


def render(source):
    presentation=ROOT/'showcase'/source/'PRESENTATION.json'
    if not presentation.exists():
        subprocess.run([PYTHON,str(ROOT/'scripts/render_pair.py'),'--source',source],env=ENV,check=True,timeout=900)
    record=json.loads(presentation.read_text())
    for item in record['videos']:
        media=ROOT/'showcase'/source/(item['name']+'.mp4')
        assert sha(media)==item['video']['sha256']
        view='完整有效片段' if item['name']=='full_valid' else '前2秒'
        dest=Path('/Users/researcher/Downloads')/('H3_IVEBench_P1_'+source+'_'+view+'_三栏对照_20261018.mp4')
        if dest.exists():assert sha(dest)==sha(media)
        else:shutil.copy2(media,dest)
    subprocess.run([PYTHON,str(ROOT/'scripts/make_showcase.py'),'--output',str(HTML)],env=ENV,check=True,timeout=180)
    document=HTML.read_text();embedded=re.findall(r'data:video/mp4;base64,([^\"]+)',document)
    expected=[]
    for key in SOURCES:
        p=ROOT/'showcase'/key/'PRESENTATION.json'
        if p.exists():expected += [Path(item['video']['file']) for item in json.loads(p.read_text())['videos']]
    assert len(embedded)==len(expected)
    for encoded,path in zip(embedded,expected): assert base64.b64decode(encoded,validate=True)==path.read_bytes()
    result={'source':source,'passed':True,'presentation_sha256':sha(presentation),'html':str(HTML),'html_sha256':sha(HTML),'embedded_videos':len(embedded),'visual_review':'PENDING; no generated content quality claim'}
    (AUDIT/(source+'_PRESENTATION_READY.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('PRESENTATION_READY '+json.dumps(result),flush=True)


if __name__=='__main__':
    deadline=time.monotonic()+12*3600
    for source in SOURCES:
        while True:
            ready=remote_ready(source)
            if ready is not None:
                assert ready['passed'] is True and ready['source']==source
                print('ACTUAL_PAIR_READY '+source,flush=True)
                sync(source);render(source);break
            if time.monotonic()>deadline:raise TimeoutError('Bounded presentation wait expired: '+source)
            time.sleep(45)
