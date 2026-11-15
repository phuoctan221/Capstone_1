import unittest

from app.services.mastery_service import (
    MasteryConfig,
    is_learned,
    is_mastered,
    skill_learned,
    skill_mastered,
    update_skill,
)


class MasteryRuleTests(unittest.TestCase):
    def setUp(self):
        self.scores = {"meaning": 50.0, "spelling": 20.0, "context": 0.0}

    def test_correct_updates_only_practised_skill(self):
        updated = update_skill(self.scores, "meaning", True, response_time_ms=9000)
        self.assertEqual(updated["meaning"], 60.0)
        self.assertEqual(updated["spelling"], 20.0)
        self.assertEqual(updated["context"], 0.0)

    def test_fast_correct_gets_bonus(self):
        updated = update_skill(self.scores, "meaning", True, response_time_ms=1000)
        self.assertEqual(updated["meaning"], 62.0)

    def test_hint_reduces_gain_and_beats_fast_bonus(self):
        updated = update_skill(
            self.scores, "meaning", True, response_time_ms=500, hint_used=True
        )
        self.assertEqual(updated["meaning"], 55.0)

    def test_wrong_answer_penalises_and_clamps_at_zero(self):
        updated = update_skill(self.scores, "context", False)
        self.assertEqual(updated["context"], 0.0)

        low = update_skill({"meaning": 2, "spelling": 0, "context": 0}, "meaning", False)
        self.assertEqual(low["meaning"], 0.0)

    def test_score_clamps_at_hundred(self):
        updated = update_skill({"meaning": 99, "spelling": 0, "context": 0}, "meaning", True)
        self.assertEqual(updated["meaning"], 100.0)

    def test_custom_config(self):
        config = MasteryConfig(
            correct_gain=25,
            wrong_penalty=10,
            hint_factor=0.2,
            fast_bonus=0,
            threshold=90,
        )
        updated = update_skill(self.scores, "spelling", True, config=config)
        self.assertEqual(updated["spelling"], 45.0)
        self.assertFalse(is_mastered(updated, config.threshold))

    def test_learned_and_mastered(self):
        self.assertTrue(is_learned({"meaning": 1, "spelling": 0, "context": 0}))
        self.assertFalse(is_learned({"meaning": 0, "spelling": 0, "context": 0}))
        self.assertTrue(
            is_mastered({"meaning": 80, "spelling": 80, "context": 80}, threshold=80)
        )
        self.assertFalse(
            is_mastered({"meaning": 80, "spelling": 79, "context": 80}, threshold=80)
        )
        self.assertTrue(skill_learned({"meaning": 3, "spelling": 0, "context": 0}, "meaning"))
        self.assertTrue(
            skill_mastered({"meaning": 90, "spelling": 0, "context": 0}, "meaning", 80)
        )

    def test_unknown_skill_raises(self):
        with self.assertRaises(ValueError):
            update_skill(self.scores, "listening", True)


if __name__ == "__main__":
    unittest.main()
