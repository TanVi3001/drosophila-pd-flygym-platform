# AI V2 RAG contract — PROPOSED / DEVELOPMENT

`RAGRuntimeContract` requires a frozen corpus SHA-256, explicit approved and denied source IDs, and no internet access. Each retrieved item carries source ID, citation, chunk ID, retrieval score, provenance and access class. A result outside the allowlist or from a forbidden access class is rejected before StudySpec drafting. When `retrieval_log_path` is configured, approved retrievals append timestamp, source ID, chunk ID, citation and corpus hash to JSONL.

No validation-source discovery is performed by this task. A future runtime must block outcome-bearing sources from its corpus and log each retrieval. The prepared metric hooks are Recall@K, Precision@K, Citation Precision, StudySpec Field Accuracy and Unsupported Claim Rate. These require independently constructed gold annotations; none are fabricated here.
