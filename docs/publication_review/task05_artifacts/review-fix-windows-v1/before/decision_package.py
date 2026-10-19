"""Opt-in, support-only L2 sidecars. No store, jobs, backend or network access.

Can be loaded directly by file path to avoid broad package initializers. Code is
always trusted caller-installed code, never an executable attachment in a bundle.
Integrity is not authenticity, scientific validity, or operational authorization.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import struct
import sys
import types
from pathlib import Path, PurePosixPath

VERSION = "decision-recompute-1"
POLICY = "support-pure-ready-fixture-1"
OBJECTS = {"bundle", "study", "capability", "mappings", "support", "approval",
           "inventory", "context", "decision", "policy", "identity"}


def _bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def pure_modules():
    """Load only the two audited stdlib-only decision dependencies."""
    root = Path(__file__).resolve().parent
    identity = str(root) + ''.join(_digest((root / f"{m}.py").read_bytes())
                                  for m in ("models", "support"))
    name = "_decision_pure_" + _digest(identity.encode())[:16]
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(root)]
        sys.modules[name] = package
        for module in ("models", "support"):
            spec = importlib.util.spec_from_file_location(f"{name}.{module}", root / f"{module}.py")
            loaded = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = loaded
            spec.loader.exec_module(loaded)
    return sys.modules[f"{name}.models"], sys.modules[f"{name}.support"]


def runtime_identity():
    root = Path(__file__).resolve().parent
    return {
        "python": platform.python_version(), "implementation": platform.python_implementation(),
        "system": sys.platform, "pointer_bits": struct.calcsize("P") * 8, "dependencies": "stdlib-only",
        "code": {name: _digest((root / name).read_bytes()) for name in
                 ("models.py", "support.py", "decision_package.py")},
    }


def pure_projection(report):
    return {k: v for k, v in report.items() if k not in {"backend_preflight", "assessment_hash"}}


def export_sidecar(root, snapshots, *, opt_in=False):
    """Attach caller-supplied snapshots to an existing v2 directory, explicitly.

    Never reads workspace references; caller must supply complete JSON snapshots.
    Existing bundle bytes stay untouched. Existing sidecars are never overwritten.
    """
    if not opt_in:
        return None
    root = Path(root).resolve()
    bundle = json.loads((root / "bundle.json").read_text(encoding="utf-8"))
    if bundle.get("evidence_bundle_version") != 2:
        raise ValueError("unsupported EvidenceBundle version")
    if set(snapshots) != OBJECTS - {"bundle", "policy", "identity"}:
        raise ValueError("explicit complete snapshot set required (approval may be null)")
    target = root / VERSION
    target.mkdir(exist_ok=False)
    objects = dict(snapshots, bundle=bundle, policy={"version": POLICY}, identity=runtime_identity())
    entries = []
    for key, value in sorted(objects.items()):
        data = (root / "bundle.json").read_bytes() if key == "bundle" else _bytes(value)
        digest = _digest(data)
        path = f"{VERSION}/{digest}.json"
        if key == "bundle":
            path = "bundle.json"
        else:
            (root / path).write_bytes(data)
        entries.append({"id": key, "schema": f"{key}-snapshot-1", "path": path,
                        "size": len(data), "sha256": digest, "requires": [], "required": True})
    manifest = {"version": VERSION, "resolver": "local-flat-closure-1", "decision_types": ["support"],
                "objects": entries}
    (target / "dependencies.json").write_bytes(_bytes(manifest))
    return target / "dependencies.json"


class PackageError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _require(condition, reason):
    if not condition:
        raise PackageError(reason)


def _read_local(root, relative):
    _require(isinstance(relative, str) and "\\" not in relative and ":" not in relative,
             "UNSAFE_PATH")
    path = PurePosixPath(relative)
    _require(not path.is_absolute() and bool(path.parts) and ".." not in path.parts, "UNSAFE_PATH")
    resolved = (root / relative).resolve()
    _require(resolved.is_relative_to(root), "UNSAFE_PATH")
    _require(resolved.is_file(), f"MISSING_DEPENDENCY:{relative}")
    return resolved.read_bytes()


def _load(root):
    manifest_path = f"{VERSION}/dependencies.json"
    if not (root / manifest_path).exists():
        raise PackageError("LEGACY_NO_SIDECAR")
    manifest = json.loads(_read_local(root, manifest_path))
    _require(manifest["version"] == VERSION, "UNSUPPORTED_SIDECAR_VERSION")
    _require(manifest["resolver"] == "local-flat-closure-1" and
             manifest["decision_types"] == ["support"], "UNSUPPORTED_PROFILE")
    entries = manifest["objects"]
    ids = [e["id"] for e in entries]
    _require(len(ids) == len(set(ids)), "DUPLICATE_OBJECT")
    _require(set(ids) == OBJECTS, "MISSING_OR_UNKNOWN_OBJECT")
    paths = [e["path"] for e in entries]
    _require(len(paths) == len(set(paths)), "DUPLICATE_PATH")
    objects = {}
    for e in entries:
        _require(e["requires"] == [] and e["required"] is True and
                 e["schema"] == f"{e['id']}-snapshot-1", "UNSUPPORTED_DEPENDENCY_GRAPH_OR_SCHEMA")
        data = _read_local(root, e["path"])
        _require(len(data) == e["size"] and _digest(data) == e["sha256"], f"HASH_MISMATCH:{e['id']}")
        objects[e["id"]] = json.loads(data)
    _require(objects["policy"] == {"version": POLICY}, "POLICY_MISMATCH")
    expected_identity = runtime_identity()
    _require(objects["identity"]["code"] == expected_identity["code"], "CODE_MISMATCH")
    _require(objects["identity"] == expected_identity, "ENVIRONMENT_MISMATCH")
    return objects


def _validate(objects):
    models, support = pure_modules()
    raw_study = objects["study"]
    _require(all(k in raw_study for k in ("study_id", "created_at", "configuration_hash")),
             "INCOMPLETE_STUDY_IDENTITY")
    study = models.StudySpec.from_dict(raw_study)
    _require(study.configuration_hash == raw_study["configuration_hash"], "STUDY_HASH_MISMATCH")
    _require(study.metadata.get("engineering_only") is True, "UNSUPPORTED_NONFIXTURE_SCOPE")
    _require(objects["bundle"]["evidence_bundle_version"] == 2 and
             objects["bundle"]["study"] == raw_study and
             objects["bundle"]["study_id"] == study.study_id, "BUNDLE_STUDY_MISMATCH")
    _require(objects["inventory"] == [{"candidate_id": c.candidate_id, "job_state": "NO_JOB_ENGINEERING_FIXTURE"}
                                       for c in study.candidates], "INVENTORY_MISMATCH")
    capability_raw = dict(objects["capability"])
    capability_raw.pop("scientific_scope", None)
    capability = models.CapabilityDescriptor(**capability_raw)
    _require(capability.as_dict() == objects["capability"], "CAPABILITY_NORMALIZATION_MISMATCH")
    mappings = {}
    for raw in objects["mappings"]:
        mapping = support.MappingRecord.from_dict(raw)
        _require(mapping.record_hash == raw["record_hash"], "MAPPING_HASH_MISMATCH")
        _require(mapping.mapping_id not in mappings, "DUPLICATE_MAPPING")
        mappings[mapping.mapping_id] = mapping
    for candidate in study.candidates:
        if candidate.intervention.get("type", "none") != "none":
            _require(all(k in candidate.metadata for k in
                         ("mapping_id", "mapping_version", "mapping_record_hash")), "UNPINNED_MAPPING")
    assessment = objects["support"]
    _require(assessment.get("schema_version") == "study-support-assessment-1", "SUPPORT_VERSION_MISMATCH")
    _require(assessment.get("study_id") == study.study_id and
             assessment.get("study_configuration_hash") == study.configuration_hash, "SUPPORT_BINDING_MISMATCH")
    _require(assessment.get("capability") == objects["capability"], "CAPABILITY_BINDING_MISMATCH")
    preflight = assessment.get("backend_preflight", {})
    _require(preflight.get("status") == "READY" or
             (preflight == {"status": "NOT_RUN", "candidates": {}} and
              assessment.get("run_allowed") is False), "UNSUPPORTED_PREFLIGHT")
    _require(models.stable_hash({k: v for k, v in assessment.items() if k != "assessment_hash"}) ==
             assessment.get("assessment_hash"), "ASSESSMENT_HASH_MISMATCH")
    approval = objects["approval"]
    if approval is not None:
        _require(approval.get("schema_version") == "support-approval-1" and
                 approval.get("study_id") == study.study_id and
                 approval.get("study_configuration_hash") == study.configuration_hash and
                 approval.get("assessment_hash") == assessment["assessment_hash"] and
                 approval.get("status") == "FROZEN_FOR_COMPUTATIONAL_RUN" and
                 isinstance(approval.get("reviewer"), str) and approval["reviewer"].strip() and
                 bool(approval.get("approved_at")), "APPROVAL_BINDING_MISMATCH")
    _require(objects["decision"] == pure_projection(assessment), "SAVED_DECISION_MISMATCH")
    return study, capability, mappings


def recompute(root):
    """Read inert snapshots, validate closure, return decision; never grant authority."""
    try:
        objects = _load(Path(root).resolve())
        study, capability, mappings = _validate(objects)
        _, support = pure_modules()
        decision = pure_projection(support.assess_study_support(
            study, capability, mappings, required_context=objects["context"]))
        return {"status": "RECOMPUTED", "integrity_closure": "VALID",
                "original_agreement": decision == objects["decision"], "decision": decision,
                "operational_authority": False, "approval_evidence_present": objects["approval"] is not None}
    except PackageError as exc:
        return {"status": "NOT_RECONSTRUCTABLE", "reason": exc.reason, "operational_authority": False}
    except (ValueError, TypeError, KeyError, OSError, AttributeError) as exc:
        return {"status": "NOT_RECONSTRUCTABLE", "reason": f"INVALID_PACKAGE:{type(exc).__name__}",
                "operational_authority": False}


if __name__ == "__main__":
    print(json.dumps(recompute(sys.argv[1]), sort_keys=True))