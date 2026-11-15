import unittest

from scripts.enrich_vocabularies import (
    dictionary_changes,
    keyword_domain,
    missing_phonetic,
    normalize_ipa,
    parse_fields,
    parse_topic_response,
    parse_words,
)


class ParseFieldsTests(unittest.TestCase):
    def test_all_expands_to_every_field(self):
        self.assertEqual(parse_fields("all"), ["phonetic", "topic", "status"])

    def test_deduplicates_and_keeps_order(self):
        self.assertEqual(
            parse_fields("topic, phonetic,topic"), ["topic", "phonetic"]
        )

    def test_rejects_unknown_field(self):
        with self.assertRaises(ValueError):
            parse_fields("phonetic,meaning")


class ParseWordsTests(unittest.TestCase):
    def test_normalizes_and_deduplicates(self):
        self.assertEqual(parse_words(" Apple, apple,,BANK "), ["apple", "bank"])

    def test_empty_returns_empty_list(self):
        self.assertEqual(parse_words(""), [])


class PhoneticDetectionTests(unittest.TestCase):
    def test_empty_is_missing(self):
        self.assertTrue(missing_phonetic(""))

    def test_partial_ipa_is_missing(self):
        self.assertTrue(missing_phonetic("/-ˈæpl"))
        self.assertTrue(missing_phonetic("ˈæpl-/"))

    def test_full_ipa_is_present(self):
        self.assertFalse(missing_phonetic("/ˈæpl/"))


class NormalizeIpaTests(unittest.TestCase):
    def test_keeps_clean_slashed_value(self):
        self.assertEqual(normalize_ipa("/ˈæpl/"), "/ˈæpl/")

    def test_wraps_plain_value(self):
        self.assertEqual(normalize_ipa("əˈbændən"), "/əˈbændən/")

    def test_strips_bracket_alternatives(self):
        self.assertEqual(normalize_ipa("[bæθ⁓bɛəθ⁓beəθ]"), "/bæθ/")

    def test_takes_first_alternative(self):
        self.assertEqual(normalize_ipa("/ˈiːðəɹ, ˈaɪðəɹ/"), "/ˈiːðəɹ/")

    def test_empty_stays_empty(self):
        self.assertEqual(normalize_ipa(""), "")

    def test_partial_value_is_rejected(self):
        self.assertEqual(normalize_ipa("/-partial"), "")


class KeywordDomainTests(unittest.TestCase):
    def test_technology_word(self):
        self.assertEqual(keyword_domain("software"), "technology")

    def test_business_word(self):
        self.assertEqual(keyword_domain("invoice"), "business")

    def test_definition_hint(self):
        self.assertEqual(
            keyword_domain("monitor", "A computer screen that displays data."),
            "technology",
        )

    def test_general_when_no_hint(self):
        self.assertEqual(keyword_domain("banana", "A long yellow fruit."), "general")


class ParseTopicResponseTests(unittest.TestCase):
    def test_keeps_only_known_words(self):
        buckets = parse_topic_response(
            {"technology": ["software", "unknown"], "business": ["Invoice"]},
            ["software", "invoice", "banana"],
        )
        self.assertEqual(buckets["technology"], {"software"})
        self.assertEqual(buckets["business"], {"invoice"})

    def test_accepts_single_string_and_uppercase_keys(self):
        buckets = parse_topic_response(
            {"Technology": "software", "Business": "invoice"},
            ["software", "invoice"],
        )
        self.assertEqual(buckets["technology"], {"software"})
        self.assertEqual(buckets["business"], {"invoice"})

    def test_ignores_invalid_payload(self):
        buckets = parse_topic_response(["software"], ["software"])
        self.assertEqual(buckets["technology"], set())
        self.assertEqual(buckets["business"], set())


class DictionaryChangesTests(unittest.TestCase):
    def test_fills_empty_fields_only(self):
        document = {
            "phonetic": "",
            "english_definition": "",
            "example": "",
            "synonyms": [],
            "antonyms": [],
        }
        candidate = {
            "phonetic": "/ˈæpl/",
            "english_definition": "A round fruit.",
            "example": "She ate an apple.",
            "synonyms": ["pome"],
            "antonyms": [],
        }
        changes = dictionary_changes(document, candidate)
        self.assertEqual(changes["phonetic"], "/ˈæpl/")
        self.assertEqual(changes["phonetic_source"], "dictionaryapi.dev")
        self.assertEqual(changes["english_definition"], "A round fruit.")
        self.assertEqual(changes["example"], "She ate an apple.")
        self.assertEqual(changes["synonyms"], ["pome"])
        self.assertNotIn("antonyms", changes)

    def test_never_overwrites_existing_values(self):
        document = {
            "phonetic": "/ɔːlˈredi/",
            "english_definition": "Existing definition.",
            "example": "Existing example.",
            "synonyms": ["existing"],
            "antonyms": ["existing"],
            "meaning": "nghĩa tiếng Việt",
        }
        candidate = {
            "phonetic": "/new/",
            "english_definition": "New definition.",
            "example": "New example.",
            "synonyms": ["new"],
            "antonyms": ["new"],
        }
        changes = dictionary_changes(document, candidate)
        self.assertEqual(changes, {})
        self.assertNotIn("meaning", changes)

    def test_skips_partial_candidate_phonetic(self):
        document = {"phonetic": "", "english_definition": "x", "example": "y"}
        candidate = {"phonetic": "/-partial"}
        changes = dictionary_changes(document, candidate)
        self.assertNotIn("phonetic", changes)


if __name__ == "__main__":
    unittest.main()
