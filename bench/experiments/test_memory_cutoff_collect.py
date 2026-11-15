import unittest

from memory_cutoff_collect import memories, query_text, split


class CollectionTest(unittest.TestCase):
    def test_abstention_stays_with_question(self):
        self.assertEqual(split('031748ae'), split('031748ae_abs'))

    def test_historical_extraction_and_date(self):
        q = {'haystack_session_ids': ['s1'], 'haystack_dates': ['2023/04/05 12:00'],
             'haystack_sessions': [[{'role': 'user', 'content': 'I prefer to work with clear examples.'},
                                    {'role': 'assistant', 'content': 'The fix was to restart the process.'}]]}
        result = memories(q)
        self.assertEqual([x['kind'] for x in result], ['preference', 'fix'])
        self.assertEqual([x['scope'] for x in result], ['global', 'longmem'])
        self.assertEqual(result[0]['observed_at'], '2023-04-05')

    def test_utf8_query_is_bounded(self):
        self.assertLessEqual(len(query_text({'question': 'é' * 400}).encode()), 500)


if __name__ == '__main__':
    unittest.main()
