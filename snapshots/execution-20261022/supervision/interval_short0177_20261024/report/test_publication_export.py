import base64
import contextlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import export_completed_cohort as export


class PublicationTests(unittest.TestCase):
    def test_assembly_review_and_generated_file_shas_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            s = Path(directory).resolve()
            base = s / 'report'; base.mkdir()
            export.report.write(s / 'SOURCE_EVENTS.json', {'events': []})
            reviews = {}
            for role in export.report.METHODS:
                path = s / 'visual' / role / 'REVIEW.json'; path.parent.mkdir(parents=True)
                export.report.write(path, {'review_completed': True, 'root_verified': True})
                reviews[role] = {'file': str(path), 'sha256': export.report.sha(path)}
            generated = {}
            for name in ['INPUT.json', 'ANNOTATION.json', 'MEDIA_BINDINGS.json']:
                export.report.write(base / name, {'fixture': name})
                generated[name] = export.report.sha(base / name)
            gate = dict(passed=True, cohort=export.COHORT, six_arms_complete=True,
                        six_root_verified_reviews=True, metrics_readiness={'complete': True},
                        generated_files=generated, source_events_sha256=export.report.sha(s / 'SOURCE_EVENTS.json'),
                        review_sources=reviews)
            export.report.write(base / 'ASSEMBLY_GATE.json', gate)
            with patch.object(export, 'S', s):
                self.assertTrue(export.verify_assembly(base / 'INPUT.json')['passed'])
                (base / 'ANNOTATION.json').write_text('{"changed":true}')
                with self.assertRaisesRegex(ValueError, 'Assembled input changed'):
                    export.verify_assembly(base / 'INPUT.json')
                export.report.write(base / 'ANNOTATION.json', {'fixture': 'ANNOTATION.json'})
                review_path = s / 'visual/split/REVIEW.json'
                review_path.write_text('{"root_verified":false}')
                with self.assertRaisesRegex(ValueError, 'accepted visual review changed'):
                    export.verify_assembly(base / 'INPUT.json')

    def test_review_cited_full_resolution_frames_are_exported_and_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            s = Path(directory).resolve()
            videos, collections, cited = {}, {}, []
            for role in export.report.ROLES:
                video = s / (role + '.mp4'); video.write_bytes(role.encode())
                videos[role] = export.report.sha(video)
                if role != 'source':
                    collections[role] = {'artifacts': {'video': {'path': str(video)}}}
                    visual = s / 'visual' / role; visual.mkdir(parents=True)
                    frame = visual / 'frame_035.jpg'; frame.write_bytes(('frame ' + role).encode()); cited.append(frame)
                    export.report.write(visual / 'REVIEW.json', {'coverage': {
                        'full_resolution_evidence': [{'path': str(frame), 'sha256': export.report.sha(frame)}]}})
            presentation = s / 'report/media/PRESENTATION.json'; presentation.parent.mkdir(parents=True)
            for name in ['comparison.mp4', 'same_frame.jpg']:
                (presentation.parent / name).write_bytes(name.encode())
            validated = ({'video_sha256': videos}, None, None, None, None, None, presentation)
            source = {'source_video': str(s / 'source.mp4')}
            with patch.object(export, 'S', s):
                media = export.select_media(validated, collections, source)
                self.assertEqual(len(media), 15)
                self.assertTrue(set(cited).issubset({p for _, p, _ in media}))
                cited[0].write_bytes(b'changed frame')
                with self.assertRaisesRegex(ValueError, 'reviewed frame SHA mismatch'):
                    export.select_media(validated, collections, source)

    def test_text_selection_includes_assembly_gate_and_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            s = Path(directory).resolve()
            names = ['SOURCE_EVENTS.json', 'PREPARATION.json', 'BACKEND_CONTRACT.json', 'NATIVE_PILOT_VERIFIED.json',
                     'collect_completed.py', 'verify_six_local.py', 'ALL_LANES_EXIT_VERIFIED.json',
                     'ROOT_SIX_ARMS_VERIFIED.json', 'ROOT_SIX_ARMS_BINDINGS.json',
                     'collection/LOCAL_COLLECTION.json', 'report/INPUT.json', 'report/MEDIA_VISUAL_VERDICT.json',
                     'report/ANNOTATION.json', 'report/MEDIA_BINDINGS.json', 'report/ASSEMBLY_GATE.json',
                     'report/ASSEMBLY.md', 'report/staging/DATA_WITHOUT_MEDIA.json',
                     'report/staging/ACTION_OFFSET_SUMMARY.json', 'report/staging/BUILD_RECEIPT.json',
                     'metrics/manifest.json', 'metrics/SUMMARY.json', 'report/media/PRESENTATION.json']
            for name in names:
                path = s / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('{}')
            config = s / 'report/INPUT.json'
            validated = ({'metrics_manifest': '../metrics/manifest.json', 'metrics_rows': '../metrics/SUMMARY.json',
                          'annotation': 'ANNOTATION.json', 'presentation': 'media/PRESENTATION.json'},)
            with patch.object(export, 'S', s):
                selected = export.select_text(config, validated)
            for name in ['ASSEMBLY.md', 'ASSEMBLY_GATE.json', 'MEDIA_BINDINGS.json']:
                self.assertIn(s / 'report' / name, selected)
            for name in ['verify_six_local.py', 'ALL_LANES_EXIT_VERIFIED.json',
                         'ROOT_SIX_ARMS_VERIFIED.json', 'ROOT_SIX_ARMS_BINDINGS.json', 'report/MEDIA_VISUAL_VERDICT.json']:
                self.assertIn(s / name, selected)

    def test_incomplete_collection_stops_before_reports_or_export(self):
        local = {'cohort': export.COHORT, 'all_six_collected': False, 'errors': {}}
        with patch.object(export.report, 'module'), patch.object(export.report, 'load', return_value=local), \
                patch.object(export.report, 'validate') as validate:
            with self.assertRaisesRegex(ValueError, 'All six immutable collections'):
                export.ready(Path('INPUT.json'))
            validate.assert_not_called()

    def test_selected_export_preserves_other_reports_and_deduplicates_media(self):
        actual_project = export.P
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            p = Path(directory)
            s = p / 'execution-20261022/supervision' / export.COHORT
            cloud = p / 'reports/cloud'; sources = p / 'reports/research_sources_20261024'
            snapshot = p / 'snapshots/execution-20261022/supervision' / export.COHORT
            for folder in [s / 'report', cloud / 'assets', sources, p / 'tools']:
                folder.mkdir(parents=True)
            for name in ['export_handoff.py', 'export_reports.py']:
                shutil.copyfile(actual_project / 'tools' / name, p / 'tools' / name)
            raw = b'original-media-bytes'
            source = s / 'source.mp4'; source.write_bytes(raw)
            shared_sha = export.digest(raw)
            metadata = s / 'SOURCE_EVENTS.json'
            metadata.write_text(json.dumps({'path': '/workspace/research-user/data/example', 'source_sha256': shared_sha}))
            r150 = p / 'reports/R150.html'; v11 = p / 'reports/V1.1.html'
            encoded = base64.b64encode(raw).decode()
            r150.write_text('<html><video src="data:video/mp4;base64,' + encoded + '"></video></html>')
            v11.write_text('<html><video src="data:video/mp4;base64,' + encoded + '"></video></html>')
            originals = {path: path.read_bytes() for path in [r150, v11, metadata, source]}
            untouched = cloud / 'prior.html'; untouched.write_text('retain existing report')
            cloud_manifest = {'reports': [{'file': n, 'asset_references': []} for n in ['R150.html', 'V1.1.html', 'prior.html']]}
            export.report.write(cloud / 'manifest.json', cloud_manifest)
            prior = {'file': 'prior/evidence.json', 'export_sha256': 'retained'}
            export.report.write(sources / 'EXPORT_MANIFEST.json', {'files': [prior], 'media': []})
            private = p / 'reports/handoff_20261024/PRIVATE.md'; private.parent.mkdir(); private.write_text('PRIVATE-CVPR-CONTENT')
            for name, value in [('P', p), ('S', s), ('SNAPSHOT', snapshot), ('CLOUD', cloud), ('SOURCES', sources)]:
                stack.enter_context(patch.object(export, name, value))
            stack.enter_context(patch.object(export.report, 'R150', r150))
            stack.enter_context(patch.object(export.report, 'V11', v11))
            stack.enter_context(patch.object(export, 'ready', return_value=((), {}, {})))
            stack.enter_context(patch.object(export, 'select_text', return_value=[metadata]))
            stack.enter_context(patch.object(export, 'select_media', return_value=[('source', source, shared_sha)]))
            plan = export.apply_export(s / 'report/INPUT.json')
            self.assertTrue(plan['passed'])
            self.assertEqual(untouched.read_text(), 'retain existing report')
            self.assertEqual([x.name for x in (cloud / 'assets').iterdir()], [shared_sha + '.mp4'])
            self.assertEqual((cloud / 'assets' / (shared_sha + '.mp4')).read_bytes(), raw)
            self.assertIn('/workspace/research-user', (snapshot / 'SOURCE_EVENTS.json').read_text())
            self.assertEqual(export.report.load(sources / 'EXPORT_MANIFEST.json')['files'][0], prior)
            cloud_result = export.report.load(cloud / 'manifest.json')
            self.assertEqual(len(cloud_result['reports']), 3)
            self.assertEqual(cloud_result['counts']['unique_assets'], 1)
            manifest = export.report.load(snapshot / 'EXPORT_MANIFEST.json')
            self.assertEqual(manifest['files'][0]['original_sha256'], export.digest(originals[metadata]))
            self.assertEqual(manifest['media'][0]['sha256'], shared_sha)
            published = export.report.load(s / 'report/PUBLICATION_EXPORT.json')
            self.assertTrue(published['passed']); self.assertFalse(published['git_operations'])
            self.assertFalse(any('handoff_20261024' in name for name in published['stage_paths']))
            self.assertTrue(all('PRIVATE-CVPR-CONTENT' not in f.read_text() for f in snapshot.rglob('*') if f.is_file()))
            for path, before in originals.items():
                self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
