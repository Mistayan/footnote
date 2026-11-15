import unittest

from memory_qualification import EXTRA_LIMIT, compact


class QualificationTest(unittest.TestCase):
    def test_keeps_original_statement_and_short_subject(self):
        statement = 'I prefer relative gaps with explicit units.'
        turns = [dict(role='user', content='For Rust daemon benchmark tables. ' + statement)]
        item = dict(text=statement, kind='preference')
        qualified = compact(item, dict(turn=0, sentence=1), turns)
        self.assertEqual(qualified, 'Subject: For Rust daemon benchmark tables.\n' + statement)
        self.assertLessEqual(len(qualified) - len(statement), EXTRA_LIMIT)

    def test_context_is_bounded_even_with_multibyte_text(self):
        statement = 'I prefer des exemples lisibles et précis.'
        turns = [dict(role='user', content=('écriture claire ' * 100) + '. ' + statement)]
        qualified = compact(dict(text=statement, kind='preference'), dict(turn=0, sentence=1), turns)
        self.assertTrue(qualified.endswith(statement))
        self.assertLessEqual(len(qualified) - len(statement), EXTRA_LIMIT)

    def test_fix_uses_previous_user_not_future_turn(self):
        statement = 'The fix was to retain the Rust daemon connection.'
        turns = [dict(role='user', content='Windows named pipes fail. Extra details.'),
                 dict(role='assistant', content=statement),
                 dict(role='user', content='FUTURE QUERY GOLD Linux')]
        qualified = compact(dict(text=statement, kind='fix'), dict(turn=1, sentence=0), turns)
        self.assertEqual(qualified, 'Subject: Windows named pipes fail.\n' + statement)
        self.assertNotIn('Linux', qualified)

    def test_missing_qualification_preserves_memory(self):
        statement = 'I prefer readable output with clear units.'
        self.assertEqual(compact(dict(text=statement, kind='preference'), dict(turn=0, sentence=0),
                                 [dict(role='user', content=statement)]), statement)

    def test_changed_source_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'source statement changed'):
            compact(dict(text='original', kind='fix'), dict(turn=0, sentence=0),
                    [dict(role='assistant', content='different')])


if __name__ == '__main__':
    unittest.main()
