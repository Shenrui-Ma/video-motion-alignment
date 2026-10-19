"""Regression for the actual R50 empty /proc/cmdline startup race."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import service


class SpawnIdentityTests(unittest.TestCase):
    def bind(self, rows, command=None):
        command = command or ['python3', '-u', '/owned/child.py']
        process = Mock(pid=123)
        process.poll.return_value = None
        tick = [0.]
        def sleep(dt):
            tick[0] += dt
        index = [0]
        def lookup(pid):
            self.assertEqual(pid, 123)
            result = rows[min(index[0], len(rows)-1)]
            index[0] += 1
            return result
        return service.bind_launched_child(process, command, timeout=.1,
            lookup=lookup, clock=lambda: tick[0], sleep=sleep)

    def row(self, command, start='100', uid=None):
        return dict(uid=os.getuid() if uid is None else uid,
                    start_ticks=start, cmdline=command)

    def test_empty_and_fork_command_wait_for_exec(self):
        ready = self.row('python3 -u /owned/child.py ')
        self.assertEqual(self.bind([None, self.row(''),
            self.row('python3 /owned/parent.py '), ready]), ready)

    def test_wrong_argv_never_binds(self):
        with self.assertRaisesRegex(RuntimeError, 'complete expected argv'):
            self.bind([self.row('python3 -u /unrelated/child.py ')])

    def test_new_pid_generation_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'generation changed'):
            self.bind([self.row(''), self.row('python3 -u /owned/child.py ', '101')])

    def test_other_uid_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'owner differs'):
            self.bind([self.row('python3 -u /owned/child.py ', uid=os.getuid()+1)])

    def test_exited_child_rejected(self):
        process = Mock(pid=123)
        process.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, 'complete expected argv'):
            service.bind_launched_child(process, ['python3'])


if __name__ == '__main__':
    unittest.main()
