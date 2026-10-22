import hashlib

import os

from pathlib import Path

import sys

import tempfile

import unittest

from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / 'scripts'))

import process_identity as p

import service

from observer_import import t

class Clock:
    def __init__(self): self.value = 0
    def now(self): return self.value
    def sleep(self, dt): self.value += dt

class Process:
    pid = 2345
    returncode = None
    def __init__(self): self.signals = []
    def poll(self): return self.returncode
    def terminate(self): self.signals.append('TERM'); self.returncode = -15
    def kill(self): self.signals.append('KILL'); self.returncode = -9
    def wait(self, timeout): return self.returncode

def row(command, start=123):
    command = b'\0'.join(os.fsencode(v) for v in command) + b'\0'
    return {'pid': 2345, 'uid': os.getuid(), 'start_ticks': start,
            'command': command, 'cmdline_sha256': hashlib.sha256(command).hexdigest()}

class ProcessBinding(unittest.TestCase):
    def test_empty_cmdline_is_not_a_hashable_identity(self):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder); proc = root / '2345'; proc.mkdir()
                tail = ['S'] + ['0'] * 18 + ['123']
                (proc / 'stat').write_text('2345 (python ) name) ' + ' '.join(tail))
                (proc / 'cmdline').write_bytes(b'')
                self.assertIsNone(p.snapshot(2345, root))
                (proc / 'cmdline').write_bytes(b'python3\0child.py\0')
                actual = p.snapshot(2345, root)
                self.assertEqual(actual['start_ticks'], 123)
                self.assertEqual(actual['command'], b'python3\0child.py\0')
                self.assertEqual(p.service_record(actual)['start_ticks'], '123')
                (proc / 'stat').write_text('2345 (name) Z ' + ' '.join(tail[1:]))
                self.assertIsNone(p.snapshot(2345, root))

    def test_waits_past_empty_and_pre_exec_command(self):
            command = ['python3', '-u', 'child.py']; expected = row(command)
            sequence = iter([None, row(['launcher']), expected]); clock = Clock()
            actual = p.bind_launched_child(Process(), command, lookup=lambda _: next(sequence), clock=clock.now, sleep=clock.sleep)
            self.assertEqual(actual, expected)
            self.assertGreaterEqual(clock.value, .02)

    def test_reused_generation_refused(self):
            clock = Clock(); sequence = iter([row(['old']), row(['python3'], 124)])
            with self.assertRaisesRegex(RuntimeError, 'generation changed'):
                p.bind_launched_child(Process(), ['python3'], lookup=lambda _: next(sequence), clock=clock.now, sleep=clock.sleep)

    def test_incomplete_child_never_publishes_success(self):
            process = Process(); clock = Clock()
            with self.assertRaisesRegex(RuntimeError, 'complete expected argv'):
                p.bind_or_reap(process, ['python3'], timeout=.03, lookup=lambda _: None, clock=clock.now, sleep=clock.sleep)
            self.assertEqual(process.signals, ['TERM'])

    def test_service_boundary_uses_bound_complete_command(self):
            process = Process(); expected = row(['python3', 'service_entry.py'])
            with patch.object(p, 'bind_or_reap', return_value=expected) as bind:
                result = service.bind_child(process, ['python3', 'service_entry.py'])
            bind.assert_called_once()
            self.assertEqual(result, p.service_record(expected))
            self.assertNotEqual(result['cmdline'], '')

    def test_transport_binding_waits_for_real_argv(self):
            command = ['python3', '-u', 'decoder.py']; expected = row(command)
            expected.pop('command'); sequence = iter([None, dict(expected, cmdline_sha256='wrong'), expected]); clock = Clock()
            actual = t.bind_launched_child(Process(), command, lookup=lambda _: next(sequence), clock=clock.now, sleep=clock.sleep)
            self.assertEqual(actual, expected)

    def test_transport_primary_failure_survives_cleanup_failure(self):
            parent = {'pid': 900, 'uid': os.getuid(), 'start_ticks': 2, 'cmdline_sha256': 'p'}
            process = Process(); expected = row(['python3']); expected.pop('command')
            with tempfile.TemporaryDirectory() as folder:
                with patch.object(t, 'alive', side_effect=lambda value: value == parent), \
                     patch.object(t.subprocess, 'Popen', return_value=process), \
                     patch.object(t, 'bind_launched_child', side_effect=ValueError('ORIGINAL_BIND_ERROR')), \
                     patch.object(t, 'terminate_owned', side_effect=TimeoutError('SECONDARY_CLEANUP_ERROR')):
                    with self.assertRaisesRegex(ValueError, 'ORIGINAL_BIND_ERROR'):
                        t.run_child(['python3'], {}, folder, 'decode', 30, parent)
                result = t.read_json(Path(folder) / 'decode.exit.json')
                self.assertIn('SECONDARY_CLEANUP_ERROR', result['cleanup_error'])
                self.assertFalse((Path(folder) / 'decode.process.json').exists())
