import unittest

from memory_context import build_memories, interval


class SourceContextTest(unittest.TestCase):
    def build(self, turns):
        return build_memories([turns], ['session-1'], ['2026/11/15 12:00'])

    def test_original_is_intact_and_local_context_is_copied(self):
        statement = 'I prefer relative percentage gaps.'
        before = 'We are discussing Footnote benchmark tables.'
        after = 'The comparison is with mem0.'
        result = self.build([dict(role='user', content=f'{before} {statement} {after}')])
        item, enriched, source = result[0]
        self.assertEqual(item['text'], statement)
        self.assertIn(before, enriched)
        self.assertIn(after, enriched)
        self.assertIn('Memory: ' + statement, enriched)
        self.assertEqual(source, dict(session='session-1', turn=0, sentence=1))

    def test_fix_uses_earlier_user_context_never_later_turn(self):
        result = self.build([dict(role='user', content='The Footnote daemon exits too early.'),
                             dict(role='assistant', content='The fix was to keep the session open.'),
                             dict(role='user', content='FUTURE SECRET QUERY LABEL')])
        self.assertIn('The Footnote daemon exits too early.', result[0][1])
        self.assertNotIn('FUTURE SECRET', result[0][1])

    def test_dedup_uses_original_identity_and_retains_first_session(self):
        statement = 'I prefer compact tables with explicit units.'
        sessions = [[dict(role='user', content='Topic alpha. ' + statement)],
                    [dict(role='user', content='Topic beta. ' + statement)]]
        result = build_memories(sessions, ['s1', 's2'], ['2026-11-14', '2026-11-15'])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0]['session'], 's1')
        self.assertNotIn('beta', result[0][1])

    def test_context_is_bounded_without_cutting_the_statement(self):
        statement = 'I prefer examples with useful source context.'
        result = self.build([dict(role='user', content='a' * 1500 + '. ' + statement + ' ' + 'z' * 1500)])
        self.assertLessEqual(len(result[0][1]), 1000)
        self.assertIn(statement, result[0][1])

    def test_french_text_preserved(self):
        statement = 'I prefer des exemples en français avec leurs références.'
        result = self.build([dict(role='user', content='Présentation du projet Arkéa. ' + statement)])
        self.assertIn('Arkéa', result[0][1])
        self.assertEqual(result[0][0]['text'], statement)

    def test_paired_interval_has_known_bounds(self):
        self.assertEqual(interval({'a': [1], 'b': [1]}), [1, 1])


if __name__ == '__main__':
    unittest.main()
