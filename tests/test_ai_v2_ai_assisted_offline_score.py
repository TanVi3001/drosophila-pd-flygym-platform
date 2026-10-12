import unittest

from scripts.score_ai_v2_ai_assisted_template_offline import score_content, task_na


def case(case_id="FIXTURE_001"):
    return {"case_id": case_id, "category": "extraction", "protocol_text": "Synthetic fixture",
            "required_fields": ["hypothesis", "assay", "context"],
            "gold_fields": {"hypothesis": None, "assay": "fixture_assay", "context": {"sex": "female"}},
            "gold_missing_fields": ["hypothesis"]}


def row(case_id="FIXTURE_001", status="COMPLETED"):
    return {"case_id": case_id, "status": status,
            "fields": {"assay": "fixture_assay", "context": {"sex": "female"}},
            "missing_fields": ["hypothesis"]}


class AIFrameworkOfflineScoreTests(unittest.TestCase):
    def test_absent_null_gold_is_scored_and_nonnull_denominator_is_separate(self):
        result, details = score_content([case()], [row()])
        self.assertEqual(result["field_exact"]["correct"], 3)
        self.assertEqual(result["field_exact"]["denominator"], 3)
        self.assertEqual(result["field_exact"]["non_null_denominator"], 2)
        self.assertFalse(details[0]["field_checks"][0]["output_present"])
        self.assertEqual(result["missing_fields"], {"tp": 1, "fp": 0, "fn": 0,
                                                   "precision": 1.0, "recall": 1.0, "f1": 1.0})

    def test_context_extra_note_remains_composite_mismatch_without_repair(self):
        item = row()
        item["fields"]["context"]["feeding_state"] = "not specified"
        result, details = score_content([case()], [item])
        self.assertEqual(result["field_exact"]["correct"], 2)
        error = details[0]["field_errors"][0]
        self.assertEqual(error["field"], "context")
        self.assertEqual(error["output_value"]["feeding_state"], "not specified")
        self.assertEqual(item["fields"]["context"]["feeding_state"], "not specified")

    def test_missing_sets_preserve_false_positives_and_false_negatives(self):
        item = row()
        item["missing_fields"] = ["assay"]
        result, _ = score_content([case()], [item])
        self.assertEqual(result["missing_fields"], {"tp": 0, "fp": 1, "fn": 1,
                                                   "precision": 0.0, "recall": 0.0, "f1": 0.0})

    def test_failures_remain_in_field_and_completion_denominators(self):
        result, _ = score_content([case()], [row(status="ERROR")])
        self.assertEqual(result["field_exact"]["denominator"], 3)
        self.assertEqual(result["field_exact"]["correct"], 0)
        self.assertEqual(result["completion"], {"count": 0, "denominator": 1, "rate": 0.0})
        self.assertEqual(result["missing_fields"]["fn"], 1)

    def test_diagnostic_excluded_and_extra_or_duplicate_rows_rejected(self):
        diagnostic = {"case_id": "PROBE", "category": "no_lexical_evidence_probe"}
        result, _ = score_content([case(), diagnostic], [row()])
        self.assertEqual(result["completion"]["denominator"], 1)
        with self.assertRaises(ValueError):
            score_content([case(), diagnostic], [row(), row("PROBE")])
        with self.assertRaises(ValueError):
            score_content([case()], [row(), row()])

    def test_na_and_not_measured_are_not_zero_scores(self):
        self.assertEqual(task_na("no retrieval"), {"status": "N/A", "value": None, "reason": "no retrieval"})
        result, _ = score_content([case()], [row(status="NOT_RUN")])
        self.assertIsNone(result["field_exact"]["accuracy"])
        self.assertIsNone(result["missing_fields"]["f1"])


if __name__ == "__main__":
    unittest.main()
