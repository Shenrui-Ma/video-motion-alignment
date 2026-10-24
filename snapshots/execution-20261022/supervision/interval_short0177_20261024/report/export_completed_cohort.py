#!/usr/bin/env python3
"""Export only the accepted short_0177 cohort using existing repository conventions.

Default: validate and write a local publication plan. --export additionally writes
sanitized snapshots and cloud copies. This script never invokes Git or inference.
"""
import argparse
import ast
import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import build_reports as report

S = Path(__file__).resolve().parent.parent
P = report.PROJECT
COHORT = 'interval_short0177_20261024'
SNAPSHOT = P / 'snapshots/execution-20261022/supervision' / COHORT
CLOUD = P / 'reports/cloud'
SOURCES = P / 'reports/research_sources_20261024'
TEXT = {'.py', '.json', '.jsonl', '.md', '.txt', '.csv', '.yaml', '.yml', '.js', '.html'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def confined(path):
    path = Path(path).resolve(strict=True)
    path.relative_to(S)
    require(path.is_file() and not path.is_symlink(), 'Expected a local cohort file: ' + str(path))
    return path


def verify_assembly(config):
    """Keep the exported annotation bound to the six accepted visual reviews."""
    base = Path(config).resolve().parent
    gate = report.load(base / 'ASSEMBLY_GATE.json')
    require(gate.get('passed') is True and gate['cohort'] == COHORT and
            gate.get('six_arms_complete') is True and gate.get('six_root_verified_reviews') is True,
            'Accepted six-arm report assembly required')
    require(gate['metrics_readiness'].get('complete') is True, 'Reassemble after the complete official metrics arrive')
    require(set(gate['generated_files']) == {'INPUT.json', 'ANNOTATION.json', 'MEDIA_BINDINGS.json'} and
            Path(config).name == 'INPUT.json', 'Unexpected assembled report inputs')
    for name, expected in gate['generated_files'].items():
        require(report.sha(confined(base / name)) == expected, 'Assembled input changed: ' + name)
    require(report.sha(S / 'SOURCE_EVENTS.json') == gate['source_events_sha256'], 'Frozen source events changed after assembly')
    require(set(gate['review_sources']) == set(report.METHODS), 'Expected six bound visual reviews')
    for role, entry in gate['review_sources'].items():
        path = confined(entry['file'])
        require(path == (S / 'visual' / role / 'REVIEW.json').resolve() and
                report.sha(path) == entry['sha256'], role + ': accepted visual review changed')
        review = report.load(path)
        require(review.get('review_completed') is True and review.get('root_verified') is True,
                role + ': root visual verification missing')
    return gate


def ready(config):
    """A publication gate, independent of queue-running or summary status strings."""
    collector = report.module('interval_publication_collector', S / 'collect_completed.py')
    local = report.load(S / 'collection/LOCAL_COLLECTION.json')
    require(local['cohort'] == COHORT and local.get('all_six_collected') is True and not local.get('errors'),
            'All six immutable collections must pass before export')
    require(set(local['arms']) == set(report.METHODS), 'Unexpected collection arms')
    collections = {}
    for role in report.METHODS:
        require(local['arms'][role]['status'] == 'completed', role + ': collection incomplete')
        collections[role] = collector.inspect_existing(S / 'collection' / role, role)
        verified = report.load(collections[role]['artifacts']['verified']['path'])
        timing = report.load(collections[role]['artifacts']['timing']['path'])
        require(verified.get('passed') is True and verified['complete_forwards'] == 20 and verified['completed_blocks'] == 1000,
                role + ': complete-arm verification missing')
        require(timing.get('passed') is True and timing['status'] == 'complete' and len(timing['per_step_seconds']) == 20,
                role + ': complete 20-step timing missing')
    verify_assembly(config)
    validated = report.validate(config)
    c, records, scores, annotation, measurement, presentation, pp = validated
    for role in report.METHODS:
        item = collections[role]
        require(c['video_sha256'][role] == item['video_sha256'], role + ': report/collection video mismatch')
        require(records[role]['result']['attempt_id'] == item['attempt_id'], role + ': report/collection attempt mismatch')
    require(all(scores[r]['quantity_accuracy']['status'] == 'not_applicable' for r in report.ROLES),
            'All seven QA statuses must be recorded as not_applicable')
    source = report.load(S / 'SOURCE_EVENTS.json')
    require(source['source_sha256'] == c['video_sha256']['source'], 'Frozen source SHA mismatch')
    require([(e['id'], e['source']) for e in annotation['events']] == [(e['id'], e['source']) for e in source['events']],
            'Final annotation differs from the frozen source event definitions')
    receipt = report.load(S / 'report/PUBLISHED.json')
    require(receipt.get('published') is True, 'Publish the validated local reports before exporting them')
    for target in (report.R150, report.V11):
        expected = [sha for name, sha in receipt['outputs'].items() if Path(name).name == target.name]
        require(len(expected) == 1 and report.sha(target) == expected[0], 'Published report changed after acceptance: ' + target.name)
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', report.R150.read_text(), re.S).group(1))
    require(len(data['cases']) == 15 and sum(x['main_cohort'] for x in data['cases']) == 10, 'Expected 10 IVE + 1 Flex + 4 historical cases')
    case = next(x for x in data['cases'] if x['source_id'] == report.NEW)
    require(case['cohort'] == COHORT and case['mean_absolute_offset'] == measurement['mean_absolute_offset'], 'Published annotation mismatch')
    return validated, collections, source


def select_text(config, validated):
    c = validated[0]
    selected = {S / n for n in ['SOURCE_EVENTS.json', 'PREPARATION.json', 'BACKEND_CONTRACT.json',
        'NATIVE_PILOT_VERIFIED.json', 'collect_completed.py', 'verify_six_local.py',
        'ALL_LANES_EXIT_VERIFIED.json', 'ROOT_SIX_ARMS_VERIFIED.json', 'ROOT_SIX_ARMS_BINDINGS.json',
        'collection/LOCAL_COLLECTION.json']}
    selected.update((S / 'collection').glob('*/*.json'))
    selected.update(p for p in (S / 'runtime/v3').rglob('*') if p.is_file() and p.suffix in TEXT
                    and '__pycache__' not in p.parts and 'input' not in p.parts)
    selected.update(p for p in (S / 'metrics').rglob('*') if p.is_file() and p.suffix in TEXT
                    and '__pycache__' not in p.parts and not any(part in {'frames', 'logs', 'runtime'} for part in p.parts)
                    and p.name not in {'HOST81_READONLY.json', 'MODEL_INPUTS_READONLY.json'})
    selected.update(p for p in (S / 'report').iterdir() if p.is_file() and
                    (p.suffix in {'.py', '.js'} or p.name in {'README.md', 'PUBLICATION.md', 'ASSEMBLY.md',
                     'showcase_template.html', 'INPUT.json', 'MEDIA_BINDINGS.json', 'ASSEMBLY_GATE.json',
                     'MEDIA_VISUAL_VERDICT.json', 'PUBLISHED.json'}))
    selected.update(S / 'report/staging' / name for name in ['DATA_WITHOUT_MEDIA.json', 'ACTION_OFFSET_SUMMARY.json', 'BUILD_RECEIPT.json'])
    selected.update((S / 'visual').glob('*/REVIEW.json'))
    selected.update((S / 'visual').glob('*/EXTRACTION.json'))
    selected.add(Path(config).resolve())
    base = Path(config).resolve().parent
    selected.update(report.resolve(base, c[key]) for key in ['metrics_manifest', 'metrics_rows', 'annotation', 'presentation'])
    return sorted(confined(path) for path in selected)


def select_media(validated, collections, source):
    c, _, _, _, _, _, pp = validated
    media = [('source', Path(source['source_video']), c['video_sha256']['source'])]
    media += [(r, Path(collections[r]['artifacts']['video']['path']), c['video_sha256'][r]) for r in report.METHODS]
    media += [(name, pp.parent / name, report.sha(pp.parent / name)) for name in ['comparison.mp4', 'same_frame.jpg']]
    # The reviewed contact sheets keep annotation intervals inspectable offline.
    media += [(str(p.relative_to(S)), p, report.sha(p)) for p in sorted((S / 'visual').glob('*/all_*.jpg'))]
    # REVIEW cites these exact full-resolution frames, in addition to contact sheets.
    included = {path.resolve() for _, path, _ in media}
    for role in report.METHODS:
        review = report.load(S / 'visual' / role / 'REVIEW.json')
        for key in ['contact_sheets', 'full_resolution_evidence']:
            for evidence in review.get('coverage', {}).get(key, []):
                path = confined(evidence['path'])
                require(report.sha(path) == evidence['sha256'], role + ': reviewed frame SHA mismatch')
                if path not in included:
                    media.append((str(path.relative_to(S)), path, evidence['sha256']))
                    included.add(path)
    for name, path, sha in media:
        require(path.is_file() and report.sha(path) == sha, 'Media SHA mismatch: ' + name)
        require(path.stat().st_size <= 95 * 1024 * 1024, 'Media exceeds repository 95 MiB asset limit: ' + name)
    return media


def prepare(config):
    validated, collections, source = ready(config)
    sanitizer = report.module('interval_existing_sanitizer', P / 'tools/export_handoff.py')
    exporter = report.module('interval_existing_report_exporter', P / 'tools/export_reports.py')
    files = []
    for path in select_text(config, validated):
        raw = path.read_bytes()
        cooked = sanitizer.sanitize(raw.decode('utf-8')).encode('utf-8')
        if path.suffix == '.json':
            json.loads(cooked)
        if path.suffix == '.py':
            ast.parse(cooked)
        compressed = len(cooked) > 5 * 1024 * 1024
        destination = SNAPSHOT / path.relative_to(S)
        if compressed:
            destination = destination.with_name(destination.name + '.gz')
            cooked = gzip.compress(cooked, mtime=0)
        require(len(cooked) <= exporter.MAX_BLOB, 'Text exceeds repository blob limit')
        files.append((path, destination, raw, cooked, compressed))
    media = select_media(validated, collections, source)
    plan = dict(schema='interval-short0177-publication-plan-v1', cohort=COHORT, passed=True,
        prepared_at=datetime.now(timezone.utc).isoformat(), numeric_metrics=63, qa_not_applicable=7,
        text_files=len(files), text_export_bytes=sum(len(x[3]) for x in files),
        unique_media_bytes=sum(p.stat().st_size for _, p, _ in {sha: (n, p, sha) for n, p, sha in media}.values()),
        media=[dict(role=name, source_relative=str(path.relative_to(P)), destination='reports/cloud/assets/' + sha + path.suffix.lower(),
                    sha256=sha, bytes=path.stat().st_size) for name, path, sha in media],
        snapshots=[str(destination.relative_to(P)) for _, destination, _, _, _ in files],
        cloud_reports=[str(p.relative_to(P)) for p in [CLOUD / report.R150.name, CLOUD / report.V11.name]],
        excluded=['reports/handoff_20261024/**', 'failed attempts', 'server occupancy inventories', 'model weights', 'raw GPU tensors'],
        git_operations=False)
    return plan, files, media, sanitizer, exporter


def apply_export(config):
    plan, files, media, sanitizer, exporter = prepare(config)
    records, media_records = [], []
    for path, destination, raw, cooked, compressed in files:
        require(path.read_bytes() == raw, 'Source changed after export preparation')
        sanitizer.write(destination, cooked)
        records.append(dict(file=destination.relative_to(P).as_posix(), source_relative=path.relative_to(P).as_posix(),
            original_sha256=digest(raw), export_sha256=digest(cooked), source_bytes=len(raw), bytes=len(cooked),
            sanitized=True, compression='gzip' if compressed else 'none'))
    (CLOUD / 'assets').mkdir(parents=True, exist_ok=True)
    for name, path, sha in media:
        destination = CLOUD / 'assets' / (sha + path.suffix.lower())
        if destination.exists():
            require(report.sha(destination) == sha, 'Existing content-addressed asset differs')
        else:
            exporter.atom_write(destination, path.read_bytes())
        media_records.append(dict(role=name, source_relative=path.relative_to(P).as_posix(),
            file=destination.relative_to(P).as_posix(), sha256=sha, bytes=destination.stat().st_size))
    cloud = report.load(CLOUD / 'manifest.json')
    existing = {r['file']: r for r in cloud['reports']}
    for src in [report.R150, report.V11]:
        require(src.name in existing, 'Expected an existing report entry')
        existing[src.name] = exporter.export_one(src, CLOUD)
    cloud['reports'] = [existing[r['file']] for r in cloud['reports']]
    assets = {a['path']: a for r in cloud['reports'] for a in r['asset_references']}
    cloud['unique_assets'] = list(assets.values())
    cloud['counts'] = dict(reports=len(cloud['reports']), unique_assets=len(assets),
        media_references=sum(len(r['asset_references']) for r in cloud['reports']),
        unique_media_bytes=sum(a['bytes'] for a in assets.values()), largest_asset_bytes=max(a['bytes'] for a in assets.values()))
    exporter.atom_write(CLOUD / 'manifest.json', (json.dumps(cloud, ensure_ascii=False, indent=2) + '\n').encode())
    public = report.load(SOURCES / 'EXPORT_MANIFEST.json')
    old_files = {r['file']: r for r in public['files']}; old_files.update({r['file']: r for r in records})
    old_media = {r['source_relative']: r for r in public['media']}; old_media.update({r['source_relative']: r for r in media_records})
    public['files'] = list(old_files.values()); public['media'] = list(old_media.values())
    sanitizer.write(SOURCES / 'EXPORT_MANIFEST.json', (json.dumps(public, ensure_ascii=False, indent=2) + '\n').encode())
    manifest = dict(schema='interval-short0177-publication-v1', cohort=COHORT, files=records, media=media_records,
        reports=[existing[src.name] for src in [report.R150, report.V11]], plan=plan,
        policy='Selected completed cohort only; existing sanitization and SHA-addressed media conventions; private planning handoff excluded.')
    report.write(SNAPSHOT / 'EXPORT_MANIFEST.json', manifest)
    index = '# short_0177 六配置区间对照\n\n' + '\n'.join([
        '- 六路完整验收与媒体绑定：`ROOT_SIX_ARMS_VERIFIED.json`、`ROOT_SIX_ARMS_BINDINGS.json`；逐项校验代码 `verify_six_local.py`。',
        '- 三条运行通道退出：`ALL_LANES_EXIT_VERIFIED.json`；对照媒体视觉检查：`report/MEDIA_VISUAL_VERDICT.json`。',
        '- 配置、提示词与输出 SHA：`report/INPUT.json`、`collection/*/{result,verified,manifest}.json`。',
        '- 完整路由、逐步计时、后端证据：`collection/*/{router,timing,backend,backend_contract}.json`。',
        '- 本轮模型图与运行实现：`runtime/v3/package/`。',
        '- 逐条官方指标与评分作业绑定：`metrics/`；精确入口见 `report/INPUT.json`。',
        '- 冻结源事件：`SOURCE_EVENTS.json`；成片事件与新汇总见 `report/INPUT.json` 的 annotation 入口及 `report/staging/ACTION_OFFSET_SUMMARY.json`。',
        '- `EXPORT_MANIFEST.json` 逐文件记录原始 SHA、导出 SHA、原路径及媒体路径。',
        '- 以下媒体使用相同原始字节。下载仓库并保持目录结构即可离线查看。',
    ]) + '\n\n'
    for item in media_records:
        import os
        link = Path(os.path.relpath(P / item['file'], SNAPSHOT)).as_posix()
        index += f"- [{item['role']}]({link}) · {item['bytes']} bytes · `{item['sha256']}`\n"
    (SNAPSHOT / 'README.md').write_text(index)
    for row in records:
        require(report.sha(P / row['file']) == row['export_sha256'], 'Exported text verification failed')
    for row in media_records:
        require(report.sha(P / row['file']) == row['sha256'], 'Exported media verification failed')
    for row in manifest['reports']:
        require(report.sha(CLOUD / row['file']) == row['export_sha256'], 'Exported report verification failed')
        for asset in row['asset_references']:
            require(report.sha(CLOUD / asset['path']) == asset['sha256'], 'Cloud report media missing or changed')
    stage_paths = [r['file'] for r in records] + [r['file'] for r in media_records]
    stage_paths += [str((SNAPSHOT / n).relative_to(P)) for n in ['README.md', 'EXPORT_MANIFEST.json']]
    stage_paths += [str((CLOUD / r['file']).relative_to(P)) for r in manifest['reports']]
    stage_paths += [str((CLOUD / a['path']).relative_to(P)) for r in manifest['reports'] for a in r['asset_references']]
    stage_paths += ['reports/cloud/manifest.json', 'reports/research_sources_20261024/EXPORT_MANIFEST.json']
    report.write(S / 'report/PUBLICATION_EXPORT.json', dict(passed=True, cohort=COHORT,
        manifest=str(SNAPSHOT / 'EXPORT_MANIFEST.json'), stage_paths=sorted(set(stage_paths)),
        new_text_bytes=sum(r['bytes'] for r in records), distinct_cohort_media_bytes=plan['unique_media_bytes'], git_operations=False))
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=S / 'report/INPUT.json')
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    try:
        plan = apply_export(args.input) if args.export else prepare(args.input)[0]
        report.write(S / 'report/PUBLICATION_PLAN.json', plan)
        print(json.dumps({k: plan[k] for k in ['passed', 'cohort', 'text_files', 'text_export_bytes', 'unique_media_bytes']}, ensure_ascii=False))
    except (ValueError, AssertionError, KeyError, FileNotFoundError) as error:
        print(json.dumps(dict(passed=False, error=str(error), exports_written=False if not args.export else 'inspect before retry'), ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
