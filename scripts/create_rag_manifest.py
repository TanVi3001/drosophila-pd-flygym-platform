#!/usr/bin/env python3
"""Freeze an already curated development-only RAG JSONL corpus manifest.

This helper records operator attestations; it cannot determine whether source
text contains biological outcomes. A reviewer must inspect and approve inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from drosophila_pd.workbench.rag import load_frozen_evidence_corpus


def build_manifest(args: argparse.Namespace) -> tuple[Path, dict[str, object]]:
    corpus_path = args.corpus.resolve(strict=True)
    target_path = args.manifest.resolve(strict=False)
    target_parent = target_path.parent.resolve(strict=True)
    if not corpus_path.is_file():
        raise ValueError("--corpus must point to a regular JSONL file")
    if corpus_path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("corpus exceeds the 128 MiB runtime limit")
    if not corpus_path.is_relative_to(target_parent):
        raise ValueError("corpus must be inside the manifest directory; package files together")
    if target_path.exists():
        raise FileExistsError("manifest already exists; use a new versioned filename instead of overwriting a freeze")
    if not args.owner_approved or not args.outcome_free:
        raise ValueError("explicit --owner-approved and --outcome-free attestations are required")
    if not args.reviewed_by:
        raise ValueError("provide at least one --reviewed-by reviewer identifier")
    if args.provider_sharing_approved and args.protocol_text_sharing_approved:
        if not args.approved_provider_id or not args.approved_provider_endpoint:
            raise ValueError("both explicit sharing flags require --approved-provider-id and --approved-provider-endpoint")
        parsed = urlsplit(args.approved_provider_endpoint)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("approved provider endpoint must be an HTTP(S) URL without credentials/query/fragment")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("non-loopback provider endpoints must use HTTPS")
    elif args.approved_provider_id or args.approved_provider_endpoint:
        raise ValueError("provider identity/endpoint may be supplied only when both sharing flags are enabled")

    corpus_hash = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": "approved-evidence-corpus-1",
        "corpus_id": args.corpus_id,
        "corpus_file": corpus_path.relative_to(target_parent).as_posix(),
        "corpus_sha256": corpus_hash,
        "approved_source_ids": sorted({value.strip() for value in args.approved_source_id if value.strip()}),
        "denied_source_ids": sorted({value.strip() for value in args.denied_source_id if value.strip()}),
        "partition": "DEVELOPMENT",
        "owner_approved": True,
        "outcome_free": True,
        "provider_sharing_approved": args.provider_sharing_approved,
        "protocol_text_sharing_approved": args.protocol_text_sharing_approved,
        "reviewed_by": sorted({value.strip() for value in args.reviewed_by if value.strip()}),
        "reviewed_at": datetime.now(UTC).isoformat(),
        "approved_provider_id": args.approved_provider_id or "",
        "approved_provider_endpoint": args.approved_provider_endpoint or "",
    }
    if not manifest["approved_source_ids"]:
        raise ValueError("provide at least one --approved-source-id")
    if set(manifest["approved_source_ids"]) & set(manifest["denied_source_ids"]):
        raise ValueError("approved and denied source IDs must be disjoint")

    fd, temp_name = tempfile.mkstemp(prefix=".rag-manifest-check-", suffix=".json", dir=target_parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        load_frozen_evidence_corpus(temp_path, retrieval_log_path=target_parent / ".manifest-validation-no-retrieval.jsonl")
        with target_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        # Verify the exact persisted file after creation.
        corpus = load_frozen_evidence_corpus(
            target_path,
            retrieval_log_path=target_parent / ".manifest-validation-no-retrieval.jsonl",
        )
        return target_path, {
            "corpus_id": corpus.corpus_id,
            "corpus_sha256": corpus.corpus_sha256,
            "manifest_sha256": corpus.manifest_sha256,
            "chunk_count": corpus.chunk_count,
            "manifest_path": str(target_path),
            "partition": "DEVELOPMENT",
            "provider_sharing_approved": corpus.provider_sharing_approved,
            "protocol_text_sharing_approved": corpus.protocol_text_sharing_approved,
            "note": "Attestations are operator-declared; this utility does not inspect or classify biological outcomes.",
        }
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True, help="Curated JSONL chunks; must be beside/under the manifest directory")
    parser.add_argument("--manifest", type=Path, required=True, help="New manifest path; existing files are never overwritten")
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--approved-source-id", action="append", default=[])
    parser.add_argument("--denied-source-id", action="append", default=[])
    parser.add_argument("--reviewed-by", action="append", default=[])
    parser.add_argument("--owner-approved", action="store_true")
    parser.add_argument("--outcome-free", action="store_true")
    parser.add_argument("--provider-sharing-approved", action="store_true")
    parser.add_argument("--protocol-text-sharing-approved", action="store_true")
    parser.add_argument("--approved-provider-id")
    parser.add_argument("--approved-provider-endpoint")
    args = parser.parse_args()
    try:
        _path, report = build_manifest(args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
