import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import assemble_inputs as a
import build_reports as b


class AssembleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / 'report'
        (self.root / 'collection').mkdir()
        b.write(self.root / 'collection/LOCAL_COLLECTION.json', {'fixture': True})
        source_video = self.root / 'source.mp4'
        source_video.write_bytes(b'source fixture')
        self.source = dict(case_id=b.NEW, title='fixture task', fps=24, valid_frames=60,
            generated_frames=73, source_crop=[16, 8, 1280, 720], reviewed_frames=[0, 59],
            frozen_before_new_outputs=True, frame_index='zero-based inclusive',
            source_video=str(source_video), source_sha256=b.sha(source_video),
            source_evidence=['source fixture'], protocol='frozen fixture protocol',
            events=[dict(id='peak', label='peak', definition='peak definition', source=[35, 40]),
                    dict(id='close', label='close', definition='yawn-close definition', source=[48, 50])])
        b.write(self.root / 'SOURCE_EVENTS.json', self.source)
        self.collections = {}
        for role in b.METHODS:
            directory = self.root / 'collection' / role
            directory.mkdir()
            video = directory / 'raw.mp4'
            video.write_bytes((role + ' fixture').encode())
            metadata = dict(source_sha256=self.source['source_sha256'], prompt='fixture prompt', seed=2026101701)
            self.collections[role] = dict(receipt=dict(video_sha256=b.sha(video), job_id='infer_' + role,
                artifacts=dict(video=dict(path=str(video), sha256=b.sha(video)),
                    result=dict(path=str(directory / 'result.json')), router=dict(path=str(directory / 'router.json')))),
                values=dict(result=dict(metadata=metadata)))
            review = dict(case_id=b.NEW, cohort=a.COHORT, arm=role, review_completed=True, root_verified=True,
                source_events_sha256=b.sha(self.root / 'SOURCE_EVENTS.json'),
                source_events_file=str(self.root / 'SOURCE_EVENTS.json'), raw_video=str(video), raw_video_sha256=b.sha(video),
                fps=24, valid_frames=60, generated_frames=73, crop_xywh=self.source['source_crop'],
                reviewed_frames=[0, 59], frame_index=self.source['frame_index'], events=[],
                observable_actions=[dict(label='ordinary close', interval=[49, 53], included_in_frozen_event_metrics=False)],
                coverage={}, summary='fixture review')
            for event in self.source['events']:
                review['events'].append(dict(id=event['id'], label=event['label'], definition=event['definition'],
                    source_interval=event['source'], output_interval=None, status='missing', offset_frames=None,
                    absolute_offset_frames=None, evidence=role + ': frozen event absent'))
            path = self.root / 'visual' / role
            path.mkdir(parents=True)
            b.write(path / 'REVIEW.json', review)

    def tearDown(self):
        self.temp.cleanup()

    def assemble(self):
        with patch.object(a, 'checked_collection', return_value=self.collections):
            return a.assemble(self.root, self.output, 'Root supplied description')

    def change_review(self, role, change):
        path = self.root / 'visual' / role / 'REVIEW.json'
        review = b.load(path)
        change(review)
        b.write(path, review)

    def metrics(self, complete=True):
        videos = {'source': self.source['source_sha256'], **{r: x['receipt']['video_sha256'] for r, x in self.collections.items()}}
        directory = self.root / 'metrics/prepared'
        directory.mkdir(parents=True)
        jobs = [dict(id='interval20261024_short_0177__' + r, method=r, task_id=b.NEW, cohort=a.COHORT,
                     sha256=videos[r], fps=24, valid_frames=60, crop_xywh=[16, 8, 1280, 720]) for r in b.ROLES]
        b.write(directory / 'manifest.json', dict(jobs=jobs))
        rows = [dict(job_id=j['id'], method=j['method'], task_id=b.NEW, cohort=a.COHORT,
                     metric=m, status='done', score=.75) for j in jobs for m in b.NUMERIC]
        rows += [dict(job_id=j['id'], method=j['method'], task_id=b.NEW, cohort=a.COHORT,
                      metric='quantity_accuracy', status='not_applicable', score=None) for j in jobs]
        if not complete:
            rows.pop(0)
        summary = dict(expected_numeric=63, numeric_done=63 if complete else 62,
                       qa_not_applicable=7, failed=0, passed=complete, rows=rows)
        b.write(self.root / 'metrics/SUMMARY.json', summary)

    def test_six_arm_gate_rejects_pending_before_any_output(self):
        shutil.copyfile(a.HERE.parent / 'collect_completed.py', self.root / 'collect_completed.py')
        b.write(self.root / 'collection/LOCAL_COLLECTION.json', dict(all_six_collected=False, pending={'split': 'running'}))
        with self.assertRaisesRegex(ValueError, 'Six-arm collection gate'):
            a.assemble(self.root, self.output, 'Root description')
        self.assertFalse(self.output.exists())

    def test_missing_events_preserved_and_unrelated_observation_stays_separate(self):
        docs = self.assemble()
        annotation = docs['ANNOTATION.json']
        self.assertEqual(docs['INPUT.json']['assembly_status'], 'awaiting_metrics')
        self.assertFalse(docs['ASSEMBLY_GATE.json']['metrics_readiness']['complete'])
        for event in annotation['events']:
            for role in b.METHODS:
                self.assertIsNone(event[role])
                self.assertEqual(event['status_by_role'][role], 'missing')
                self.assertEqual(event['evidence_by_role'][role], role + ': frozen event absent')
                self.assertIsNone(event['review_event_by_role'][role]['offset_frames'])
        self.assertEqual(len(annotation['events']), 2)
        self.assertEqual(annotation['observable_actions_by_role']['native'][0]['interval'], [49, 53])
        for role, provenance in annotation['review_sources'].items():
            self.assertEqual(provenance['sha256'], b.sha(self.root / 'visual' / role / 'REVIEW.json'))
        measure = b.module('assembly_event_measure', b.REFRESH / 'action_offsets.py').measure
        self.assertEqual(measure(annotation)['mean_absolute_offset'], dict.fromkeys(b.ROLES))
        gate = a.write_inputs(self.output, docs)
        self.assertEqual(set(gate['generated_files']), {'INPUT.json', 'ANNOTATION.json', 'MEDIA_BINDINGS.json'})
        for name, digest in gate['generated_files'].items():
            self.assertEqual(b.sha(self.output / name), digest)
        self.assertEqual(docs['MEDIA_BINDINGS.json']['completion_gate'], str(self.output / 'ASSEMBLY_GATE.json'))

    def test_each_review_requires_root_verification(self):
        self.change_review('split', lambda x: x.update(root_verified=False))
        with self.assertRaisesRegex(ValueError, 'split: visual review/root verification incomplete'):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_changed_source_event_hash_rejected(self):
        self.change_review('fixed', lambda x: x.update(source_events_sha256='a' * 64))
        with self.assertRaisesRegex(ValueError, 'source-event SHA/path mismatch'):
            self.assemble()

    def test_wrong_review_video_and_missing_offset_rejected(self):
        self.change_review('late', lambda x: x.update(raw_video_sha256='a' * 64))
        with self.assertRaisesRegex(ValueError, 'review video mismatch'):
            self.assemble()
        self.change_review('late', lambda x: x.update(raw_video_sha256=self.collections['late']['receipt']['video_sha256']))
        self.change_review('late', lambda x: x['events'][0].update(offset_frames=0))
        with self.assertRaisesRegex(ValueError, 'missing event has a measured offset'):
            self.assemble()

    def test_present_event_keeps_actual_interval_offset_and_evidence(self):
        self.change_review('early', lambda x: x['events'][0].update(output_interval=[36, 41], status='measured',
                           offset_frames=1, absolute_offset_frames=1, evidence='specific measured evidence'))
        docs = self.assemble()
        event = docs['ANNOTATION.json']['events'][0]
        self.assertEqual(event['early'], [36, 41])
        self.assertEqual(event['review_event_by_role']['early']['offset_frames'], 1)
        self.assertEqual(event['evidence_by_role']['early'], 'specific measured evidence')

    def test_full_metrics_required_for_complete_state(self):
        self.metrics(complete=False)
        self.assertEqual(self.assemble()['INPUT.json']['assembly_status'], 'awaiting_metrics')
        path = self.root / 'metrics/SUMMARY.json'
        summary = b.load(path)
        summary['passed'] = True
        b.write(path, summary)
        with self.assertRaisesRegex(ValueError, 'passed flag'):
            self.assemble()
        shutil.rmtree(self.root / 'metrics')
        self.metrics(complete=True)
        docs = self.assemble()
        self.assertEqual(docs['INPUT.json']['assembly_status'], 'metrics_complete')
        self.assertEqual(docs['INPUT.json']['metrics_readiness']['numeric_done'], 63)

    def test_wrong_metrics_video_is_rejected(self):
        self.metrics()
        path = self.root / 'metrics/prepared/manifest.json'
        manifest = b.load(path)
        manifest['jobs'][2]['sha256'] = 'a' * 64
        b.write(path, manifest)
        with self.assertRaisesRegex(ValueError, 'scored video/frame mismatch'):
            self.assemble()

    def test_duplicate_metric_row_is_rejected(self):
        self.metrics()
        path = self.root / 'metrics/SUMMARY.json'
        summary = b.load(path)
        summary['rows'].append(copy.deepcopy(summary['rows'][0]))
        b.write(path, summary)
        with self.assertRaisesRegex(ValueError, 'Duplicate metrics row'):
            self.assemble()


if __name__ == '__main__':
    unittest.main()
