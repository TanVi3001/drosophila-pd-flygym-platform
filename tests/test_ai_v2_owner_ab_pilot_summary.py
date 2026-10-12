import unittest

from scripts.summarize_ai_v2_owner_ab_synthetic_pilot import reconcile_record


def unit(claim_id, branch, axis_a, axis_b, classification):
    return {
        "claim_id": claim_id,
        "case_id": "SYNTHETIC_CASE",
        "branch": branch,
        "field_path": "/field",
        "axis_a": axis_a,
        "axis_b": axis_b,
        "denominator_classification": classification,
        "critical_classification": None,
    }


def fixture_record():
    rows = [
        unit("n1", "llm_no_retrieval", "SUPPORTED", "N/A", "INCLUDE_CONTENT_SUPPORT"),
        unit("n2", "llm_no_retrieval", "PARTIAL", "N/A", "INCLUDE_CONTENT_SUPPORT"),
        unit("r1", "llm_rag", "UNSUPPORTED", "UNSUPPORTED", "INCLUDE_CONTENT_SUPPORT"),
        unit("r2", "llm_rag", "N/A", "N/A", "EXCLUDE_CONTENT_SUPPORT_KEEP_INVENTORY"),
    ]
    return {
        "original_claim_units": rows,
        "owner_confirmed_decisions": rows,
        "unreviewed_claim_ids": [],
        "denominator_rule": {
            "includes_owner_approved": [
                {"claim_id": row["claim_id"]} for row in rows[:3]
            ],
            "exclusions_owner_approved": [{"claim_id": "r2"}],
        },
        "progress": {"severity_unresolved_units": 0,
                     "omission_diagnostics_severity_unresolved": 0},
        "owner_confirmed_omission_diagnostics": [],
    }


class OwnerABPilotSummaryTests(unittest.TestCase):
    def test_keeps_partial_separate_and_exclusion_out_of_a_denominator(self):
        result = reconcile_record(fixture_record())
        no_retrieval = result["fidelity_axis_a_included"]["llm_no_retrieval"]
        self.assertEqual(no_retrieval["denominator"], 2)
        self.assertEqual(no_retrieval["counts"], {
            "SUPPORTED": 1, "PARTIAL": 1, "UNSUPPORTED": 0,
        })
        rag = result["fidelity_axis_a_included"]["llm_rag"]
        self.assertEqual(rag["denominator"], 1)
        self.assertEqual(rag["counts"], {
            "SUPPORTED": 0, "PARTIAL": 0, "UNSUPPORTED": 1,
        })
        self.assertEqual(result["exclude_count"], 1)
        self.assertEqual(result["inventory_total"], 4)

    def test_b_reports_all_inventory_and_included_subset_separately(self):
        result = reconcile_record(fixture_record())
        self.assertEqual(result["axis_b_all_reviewed_inventory"]["llm_rag"], {
            "denominator": 2,
            "counts": {"SUPPORTED": 0, "PARTIAL": 0,
                       "UNSUPPORTED": 1, "N/A": 1},
        })
        self.assertEqual(result["axis_b_included_only"]["llm_rag"], {
            "denominator": 1,
            "counts": {"SUPPORTED": 0, "PARTIAL": 0,
                       "UNSUPPORTED": 1, "N/A": 0},
        })

    def test_secondary_include_index_must_match_each_owner_decision(self):
        record = fixture_record()
        record["denominator_rule"]["includes_owner_approved"].pop()
        with self.assertRaisesRegex(ValueError, "secondary INCLUDE index"):
            reconcile_record(record)


if __name__ == "__main__":
    unittest.main()
