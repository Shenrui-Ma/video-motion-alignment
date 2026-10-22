from pathlib import Path
import base64
import hashlib
import html
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parent
REPORT = Path('/Users/researcher/DevProjects/video-motion-alignment/reports/视频编辑中动作时间对齐-研究进展v1.html')


def uri(path, mime):
    return 'data:' + mime + ';base64,' + base64.b64encode(Path(path).read_bytes()).decode()


def replace_once(text, old, new):
    assert text.count(old) == 1, (old[:120], text.count(old))
    return text.replace(old, new, 1)


def build():
    source = REPORT.read_text()
    record = json.loads((ROOT / 'source_record.json').read_text())
    assert hashlib.sha256(source.encode()).hexdigest() == record['sha256'], 'Report changed during preparation; rebase edits onto the latest document.'
    out = source
    out = replace_once(out, '2.4　参考分支的时间相位对齐（已暂停）', '2.4　参考分支的时间相位对齐（已搁置）')
    out = replace_once(out, '图 5  /  已暂停的辅助时间相位尝试', '图 5  /  参考分支时间相位对齐（已搁置）')
    out = replace_once(out, '相位单独配置：q′ 仍读取全部参考时间', '相位对齐：q′ 仍读取全部参考时间')
    out = replace_once(out, '图 5．相位单独配置的计算流程：', '图 5．参考分支时间相位对齐的计算流程：')
    old = '组合配置进一步将上式的参考 K/V 限定为同时间 bin 的 R<sub>τ</sub>，同时保留原参考视频概率总和 m。两种配置均在第 7–15 个去噪步启用，覆盖全部 50 个 Block，α=1。相位单独配置先测试书封改色，组合配置随后测试五组已有样例；结果见 3.4 节。当前固定 Δ 相位配置已暂停。'
    new = '将时间相位对齐与 2.2 节的时间对齐引导结合时，上式的参考 K/V 限定为同时间 bin 的 R<sub>τ</sub>，并保留参考视频概率总和 m。两种方法均在第 7–15 个去噪步启用，覆盖全部 50 个 Block，α=1。单独的相位对齐先测试书封改色，再与时间对齐引导结合测试五组已有样例；结果见 3.5 节。<b>参考分支时间相位对齐方法已搁置。</b>'
    out = replace_once(out, old, new)

    data_start = out.index('<p><b>FlexiAct</b> 是动作迁移方法及其 benchmark。')
    data_end = out.index('</div>\n<div class="prose"><h3>3.2', data_start)
    out = out[:data_start] + (ROOT / 'dataset_section.html').read_text() + out[data_end:]

    e = json.loads((ROOT / 'phase_example.json').read_text())
    photo = uri(e['assets']['reference_image']['path'], 'image/jpeg')
    frame = uri(e['assets']['screenshot']['path'], 'image/jpeg')
    video = uri(ROOT / 'phase_sam_fourway_padded.mp4', 'video/mp4')
    phase = f'''<div class="prose"><h3 id="phase-experiment">3.5　参考分支时间相位对齐实验</h3>
<p>在已有时间对齐引导上加入参考分支时间相位变换，五组配对实验均完成编辑任务：机舱、饮酒和手帕任务的动作时差持平，书本由 9.20 帧变为 9.50 帧，Sam 舞蹈由 1 帧增至 12 帧。<b>参考分支时间相位对齐方法已搁置。</b></p>
<p>下面展示 Sam 舞蹈对照。两种引导均使用第 7–15 个去噪步、α=1 和同一视频动作窗口，增加时间相位变换后，动作重新出现明显延后。</p></div>
<article class="result" id="phase-sam"><div class="resulthead"><h3>角色替换 — 真人书记舞替换为 Sam Altman</h3><span>自有舞蹈素材 · R148</span></div>
<div class="inputnote"><p><b>输入：</b>源视频、Sam 肖像参考图与文本。</p><p><b>任务：</b>{html.escape(e['prompt_summary'])}</p>
<details><summary>参考图与完整提示词（历史六段提示词）</summary><img src="{photo}" alt="Sam Altman 角色参考图" style="width:150px;height:auto;margin:12px 0"><pre>{html.escape(e['prompt_exact'])}</pre></details></div>
<figure><img loading="lazy" src="{frame}" alt="参考、普通编辑、时间对齐引导、引导加相位对齐的同帧截图"><figcaption class="imagecaption">同帧对比（2.375 秒）：参考、普通编辑、时间对齐引导、时间对齐引导＋相位对齐。</figcaption></figure>
<video controls playsinline preload="none" src="{video}"></video><div class="controls"><button type="button" data-rate="1">1×</button><button type="button" data-rate="0.5">0.5×</button><button type="button" data-restart>从头播放</button></div>
<div class="imagecaption">普通编辑延后 13 帧，时间对齐引导延后 1 帧，加入相位对齐后延后 12 帧。时差来自成片的手臂动作序列匹配。</div></article>
<div class="prose"><h3>3.6　评价指标</h3>
'''
    phase_start = out.index('<div class="prose"><p><b>参考分支相位实验。</b>')
    phase_end = out.index('<p><b>评价指标。</b>', phase_start)
    out = out[:phase_start] + phase + out[phase_end:]
    out = replace_once(out, '<p><b>评价指标。</b>FlexiAct', '<p>FlexiAct')

    abstract = lambda s: re.search(r'<section id="abstract"[\s\S]*?</section>', s).group()
    assert abstract(source) == abstract(out)
    old_assets = re.findall(r'src="(data:[^"]+)"', source)
    new_assets = re.findall(r'src="(data:[^"]+)"', out)
    assert all(a in new_assets for a in old_assets)
    assert out.count('<video ') == source.count('<video ') + 1
    assert out.count('<svg') == source.count('<svg')
    assert '已暂停' not in out
    assert '当前固定 Δ' not in out
    (ROOT / 'updated_report.html').write_text(out)
    (ROOT / 'edit_validation.json').write_text(json.dumps({
        'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'updated_sha256': hashlib.sha256(out.encode()).hexdigest(),
        'abstract_unchanged': True,
        'existing_media_preserved': True,
        'videos_before': source.count('<video '),
        'videos_after': out.count('<video '),
        'svg_count': out.count('<svg'),
        'new_sections': ['3.1 dataset suitability counts', '3.5 phase comparison'],
    }, ensure_ascii=False, indent=2))
    print('Prepared:', ROOT / 'updated_report.html')


if __name__ == '__main__':
    build()
