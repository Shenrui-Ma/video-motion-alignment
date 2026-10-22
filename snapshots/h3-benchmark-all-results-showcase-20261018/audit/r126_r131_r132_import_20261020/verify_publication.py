from pathlib import Path
import json,hashlib,mmap,re,base64,subprocess,time
R=Path(__file__).resolve().parents[2];A=Path(__file__).parent;build=json.loads((R/'task_view_20261019/BUILD.json').read_text());H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();page=Path(build['output']);alias=Path(build['canonical_output']);assert page.stat().st_ino==alias.stat().st_ino
with page.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as m:
 assert hashlib.sha256(m).hexdigest()==build['sha256'];raw=re.search(rb'<script id="metadata" type="application/json">(.*?)</script>',m,re.S).group(1);d=json.loads(raw)
 assert d==json.loads((R/'task_view_20261019/DATA.json').read_text());seen=set()
 for z in re.finditer(rb'<script type="application/octet-stream" id="asset_([0-9a-f]+)">(.*?)</script>',m,re.S):
  sha=z.group(1).decode();assert sha not in seen;seen.add(sha);assert hashlib.sha256(base64.b64decode(z.group(2),validate=True)).hexdigest()==sha;assert sha in build['assets']
 assert seen==set(build['assets'])==set(d['asset_types'])
 assert not re.search(rb'(?:src|href)=["\'](?:https?://|file:|/Users/|/data[0-9]/)',m)
 for v in d['versions'].values():
  for p in v['players']:
   assert all(p[k] in seen for k in ['asset','poster','still']);assert p['labels'] and p['still_labels']
 r=d['versions']['r129_long_0039_aligned_clock'];assert r['mode']=='positional_control' and not r['has_guided'] and r['has_alternative'];assert r['mf']['guided'] is None and r['mf']['native']==0.8777332312340698 and r['mf']['aligned']==0.9319045038663815
 assert r['alignment_native'] is False and r['alignment_alternative'] is True and r['still_frame']==81;assert r['method']=='RoPE整体对齐' and '蓝色修改失败' in r['summary'];assert len(r['players'])==1 and r['players'][0]['labels'][2]=='3.RoPE时间坐标对齐'
 p=d['versions']['r127_long_0122_full_context'];assert p['still_frame']==16 and p['alignment_native'] is False and p['alignment_guided'] is False;assert p['mf']['native']==0.8275033421306062 and p['mf']['guided']==0.8031466759826568
 assert len(d['versions'])==104 and len(d['tasks'])==53 and d['unique_sources']==44
 r132=d['versions']['r132_long_0039_reference_origin'];assert r132['mode']=='reference_origin_control' and r132['has_guided'];assert r132['mf']['guided'] is None and r132['mf']['reference_origin']==0.8793789565005053;assert r132['alignment_native'] is False and r132['alignment_guided'] is False;assert r132['method']=='参考分支相位引导' and '探索性' in r132['summary'];assert r132['players'][0]['labels'][2]=='3.参考分支相位引导'
 r126=d['versions']['r126_long_0059_full_context'];assert r126['mf']['native']==0.8050170051044884 and r126['mf']['guided']==0.8037195712200009 and r126['still_frame']==107
 r131=d['versions']['r131_short_0177_full_context'];assert r131['mf']['native']==0.9120900968318817 and not r131['has_guided'] and r131['alignment_native'] is True
js=(R/'task_view_20261019/template.html').read_text().split('<script>')[1].split('</script>')[0];(A/'template_check.js').write_text(js);subprocess.run(['node','--check',str(A/'template_check.js')],check=True)
funcs=[]
for name,nextname in [('metricColumns','metricHTML'),('alignmentMark','alignmentHTML'),('alignmentHTML','renderTask')]:funcs.append(js[js.index('function '+name+'('):js.index('function '+nextname+'(')])
code='\n'.join(funcs)+'\nconst v='+json.dumps(r,ensure_ascii=False)+';const c=metricColumns(v);if(c.values[1]!==0.9319045038663815||c.labels[1]!=="RoPE 时间坐标对齐")throw Error("score labels");const h=alignmentHTML(v);if(h.includes("尚无成片")||h.includes("引导编辑"))throw Error("role labels");';subprocess.run(['node','-e',code],check=True)
subprocess.run(['node','-e','\n'.join(funcs)+'\nconst v='+json.dumps(r132,ensure_ascii=False)+';const c=metricColumns(v);if(c.values[1]!==0.8793789565005053||!c.labels[1].includes("参考分支"))throw Error("reference phase MF");'],check=True)
res={'passed':True,'output':str(page),'alias':str(alias),'same_inode':True,'sha256':build['sha256'],'bytes':build['bytes'],'versions':104,'tasks':53,'independent_sources':44,'verified_embedded_assets':len(seen),'all_player_poster_still_bindings':True,'positional_roles_and_MF':True,'reference_origin_roles_qualification_and_MF':True,'JS_syntax_and_role_functions':True,'browser_layout_assessment':'not assessed; no layout style changes, local browser restriction preserved','created_unix':time.time()};(A/'PUBLICATION_VERIFIED.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps(res,ensure_ascii=False,indent=2))
