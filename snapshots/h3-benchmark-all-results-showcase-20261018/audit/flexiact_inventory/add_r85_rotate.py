from pathlib import Path
import shutil,json,hashlib,subprocess
A=Path(__file__).parent;O=A.parents[1];bak=A/'r85_rotate_added';bak.mkdir(exist_ok=True)
for p in [O/'inventory/flexiact.json',A/'build_inventory.py',A/'PATH_AND_SHA_VALIDATION.json']:
 q=bak/(p.name+'.before');assert not q.exists();shutil.copy2(p,q)
p=A/'build_inventory.py';s=p.read_text();marker='# Validate actual file availability, bind SHA, and forbid duplicate output sets.'
block="""# R85 third completed pair: actual new P1 Native and fixed guidance.
key='rotate__game_girl_1';c=cs85[key];paired_review=r85/'audit/visual_review_rotate_gamegirl1';pm=r85/f'showcase/{key}/PRESENTATION.json';p=read(pm);gate=Path(p['gate']['file']);assert read(gate)['passed'];verified(gate,p['gate']['sha256'])
x=row('flex_r85_'+key+'_fixed','rotate','R85 · P1新同机配对','game_girl_1',r85/'inputs'/c['video'],r85/f'incoming/{key}/native.mp4',r85/f'incoming/{key}/forced.mp4',r85/f'showcase/{key}/full_valid.mp4','完整147帧审阅：两版均换成短棕发黑银铠甲女性，胸前合手、双脚固定、躯干往返转动保留。普通编辑已基本同相，固定引导未显示清楚时序收益。头部朝向和转幅有共有细差；深灰背景与目标图深青背景仅部分匹配，未见引导新增明显重影。','无明显改善',[pm,gate,paired_review/'REVIEW.json',paired_review/'FRAME_LEDGER.json',r85/f'results/{key}/HUMAN_REVIEW.json']);items.append(bind_input(x,c,r85,ct85))
"""
assert s.count(marker)==1;s=s.replace(marker,block+marker);p.write_text(s)
subprocess.run(['/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python',str(p)],check=True)
a=json.loads((bak/'flexiact.json.before').read_text());b=json.loads((O/'inventory/flexiact.json').read_text());aa={x['id']:x for x in a['items']};bb={x['id']:x for x in b['items']};assert all(bb[k]==v for k,v in aa.items());assert set(bb)-set(aa)=={'flex_r85_rotate__game_girl_1_fixed'}
receipt={'passed':True,'old_items_unchanged':len(aa),'new_item':'flex_r85_rotate__game_girl_1_fixed','total':len(bb),'inventory_sha256':hashlib.sha256((O/'inventory/flexiact.json').read_bytes()).hexdigest()};(bak/'VALIDATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt)
