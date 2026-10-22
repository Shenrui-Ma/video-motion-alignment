"""Event-table denominators must follow each frozen protocol."""
import unittest

from build_report import events_table


class EventTableTests(unittest.TestCase):
    def test_five_event_means_use_all_events(self):
        events = [dict(id=str(i), label=str(i), source=[0, 2],
                       native=[d, d + 2], global_weak=[0, 2])
                  for i, d in enumerate([16, 16, 16, 17, 14])]
        annotation = dict(events=[dict(id=e['id'], new_interval=[0, 2]) for e in events],
                          mean_absolute_offset_frames=0)
        html = events_table(annotation, dict(events=events))
        self.assertIn('<td>15.800</td><td>0.000</td><td>0.000</td>', html)

    def test_missing_event_does_not_shrink_denominator(self):
        events = [dict(id=str(i), label=str(i), source=[0, 2],
                       native=[3, 5] if i else None, global_weak=[0, 2])
                  for i in range(5)]
        annotation = dict(events=[dict(id=e['id'], new_interval=[0, 2]) for e in events],
                          mean_absolute_offset_frames=0)
        html = events_table(annotation, dict(events=events))
        self.assertIn('<td>待测</td><td>0.000</td><td>0.000</td>', html)


if __name__ == '__main__':
    unittest.main()
