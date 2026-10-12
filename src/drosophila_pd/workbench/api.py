"""Optional FastAPI surface backed by :class:`WorkbenchService`."""

from __future__ import annotations

import hmac
import os
from typing import Any, Mapping

from .benchmark import BenchmarkProtocol, freeze_benchmark_protocol
from .models import StudySpec
from .ranking import RankingPolicy
from .selection import SelectionPolicy
from .support import MappingRecord
from .service import WorkbenchService


def create_app(
    service: WorkbenchService,
    *,
    api_token: str | None = None,
    deployment_env: str = "local",
    rag_corpus: Any | None = None,
    allow_ungrounded_intake: bool = False,
) -> Any:
    """Create a local or token-protected staging API.

    The staging token is a coarse internal-test gate, not production identity
    management. Public deployment still requires a TLS-terminating gateway and
    user-level authentication/authorization.
    """

    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as error:  # pragma: no cover - depends on optional extra
        raise RuntimeError("install the 'workbench' extra to run the FastAPI server") from error

    if deployment_env not in {"local", "staging"}:
        raise ValueError("deployment_env must be 'local' or 'staging'")
    if api_token and len(api_token) < 32:
        raise ValueError("api_token must contain at least 32 characters")
    if deployment_env == "staging" and not api_token:
        raise ValueError("staging requires an API token")

    app = FastAPI(
        title="Fly Research Workbench",
        version="0.2",
        docs_url=None if deployment_env == "staging" else "/docs",
        redoc_url=None if deployment_env == "staging" else "/redoc",
        openapi_url=None if deployment_env == "staging" else "/openapi.json",
    )
    app.state.deployment_env = deployment_env
    app.state.rag_corpus_configured = rag_corpus is not None

    @app.middleware("http")
    async def require_staging_token(request: Any, call_next: Any) -> Any:
        public_paths = {"/", "/healthz", "/readyz"}
        if api_token and request.url.path not in public_paths:
            authorization = request.headers.get("authorization", "")
            scheme, separator, supplied = authorization.partition(" ")
            if (
                not separator
                or scheme.casefold() != "bearer"
                or not hmac.compare_digest(supplied.encode("utf-8"), api_token.encode("utf-8"))
            ):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "A valid staging bearer token is required."},
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)

    @app.get("/healthz")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "fly-research-workbench",
            "environment": deployment_env,
            "authentication_required": bool(api_token),
        }

    @app.get("/readyz")
    def readiness() -> dict[str, Any]:
        checks = {"database": False, "artifact_storage": False}
        try:
            connection = service.store._connect()
            try:
                connection.execute("SELECT 1").fetchone()
                checks["database"] = True
            finally:
                connection.close()
        except Exception:
            checks["database"] = False
        checks["artifact_storage"] = service.artifact_root.is_dir() and os.access(service.artifact_root, os.W_OK)
        if not all(checks.values()):
            raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
        return {"status": "ready", "checks": checks}

    @app.get("/", response_class=HTMLResponse)
    def workbench_page() -> str:
        return _WORKBENCH_HTML

    def failure(error: Exception) -> HTTPException:
        status = 404 if isinstance(error, KeyError) else 400
        return HTTPException(status_code=status, detail=str(error))

    @app.get("/v1/capabilities")
    def capabilities() -> dict[str, Any]:
        return {"capabilities": service.capabilities()}

    @app.get("/v1/mapping-records")
    def mapping_records() -> dict[str, Any]:
        return {"mapping_records": service.list_mapping_records()}

    @app.post("/v1/mapping-records")
    def register_mapping_record(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            record = payload.get("mapping_record", payload)
            return service.register_mapping_record(MappingRecord.from_dict(record))
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/ai/mappings/resolve")
    def resolve_ai_mapping(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            from drosophila_pd.ai_v2.contracts import AIStudySpec
            from drosophila_pd.ai_v2.mapping_resolution import resolve_mapping

            draft = AIStudySpec.from_dict(payload["draft"])
            request = _mapping_request_for_draft(draft, str(payload["candidate_id"]))
            records = [MappingRecord.from_dict(item) for item in service.list_mapping_records().values()]
            return resolve_mapping(request, records).as_dict()
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/ai/studies/draft")
    def create_ai_study_draft(payload: dict[str, Any]) -> dict[str, Any]:
        """Bind an explicitly selected reviewed mapping, then persist a DRAFT."""

        try:
            from drosophila_pd.ai_v2.contracts import AIStudySpec
            from drosophila_pd.ai_v2.mapping_resolution import (
                bind_mapping_to_draft,
                resolve_mapping,
                select_mapping,
            )
            from drosophila_pd.ai_v2.workbench_workflow import AIV2WorkbenchWorkflow

            draft = AIStudySpec.from_dict(payload["draft"])
            candidate_id = str(payload["candidate_id"])
            selection = payload["mapping_selection"]
            if not isinstance(selection, dict):
                raise ValueError("mapping_selection must be an object")
            request = _mapping_request_for_draft(draft, candidate_id)
            records = [MappingRecord.from_dict(item) for item in service.list_mapping_records().values()]
            resolution = resolve_mapping(request, records)
            if resolution.status != "HUMAN_SELECTION_REQUIRED":
                raise HTTPException(
                    status_code=409,
                    detail={"message": "No reviewed compatible mapping is selectable.", "resolution": resolution.as_dict()},
                )
            binding = select_mapping(
                resolution,
                records,
                mapping_id=str(selection["mapping_id"]),
                version=str(selection["version"]),
                record_hash=str(selection["record_hash"]),
            )
            bound_draft = bind_mapping_to_draft(draft, candidate_id=candidate_id, binding=binding)
            created = AIV2WorkbenchWorkflow(service).create_draft(bound_draft)
            return {**created, "mapping_binding": binding.as_dict()}
        except HTTPException:
            raise
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.get("/v1/ai/studies/{study_id}/workflow")
    def get_ai_workflow(study_id: str) -> dict[str, Any]:
        try:
            from drosophila_pd.ai_v2.workbench_workflow import AIV2WorkbenchWorkflow

            return AIV2WorkbenchWorkflow(service).status(study_id)
        except (KeyError, ValueError) as error:
            raise failure(error) from error

    @app.post("/v1/ai/studies/{study_id}/approval")
    def approve_ai_workflow(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            from drosophila_pd.ai_v2.workbench_workflow import AIV2WorkbenchWorkflow

            reviewer = payload.get("reviewer")
            return AIV2WorkbenchWorkflow(service).approve(
                study_id,
                reviewer=reviewer if isinstance(reviewer, str) else None,
            )
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/ai/studies/{study_id}/jobs")
    def submit_ai_job(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            from drosophila_pd.ai_v2.workbench_workflow import AIV2WorkbenchWorkflow

            return AIV2WorkbenchWorkflow(service).submit(study_id, candidate_id=str(payload["candidate_id"]))
        except (KeyError, ValueError, TypeError, RuntimeError) as error:
            raise failure(error) from error

    @app.post("/v1/ai/jobs/{job_id}/run")
    def run_ai_job(job_id: str) -> dict[str, Any]:
        try:
            from drosophila_pd.ai_v2.workbench_workflow import AIV2WorkbenchWorkflow

            return AIV2WorkbenchWorkflow(service).run(job_id)
        except (KeyError, ValueError, RuntimeError) as error:
            raise failure(error) from error

    @app.post("/v1/protocol-intake/draft")
    def protocol_intake_draft(payload: dict[str, Any]) -> dict[str, Any]:
        if not allow_ungrounded_intake:
            raise HTTPException(
                status_code=403,
                detail="Ungrounded provider intake is disabled; use the approved-corpus RAG endpoint.",
            )
        try:
            protocol_text = payload.get("protocol_text")
            if not isinstance(protocol_text, str):
                raise ValueError("protocol_text must be a string")
            source_uri = payload.get("source_uri")
            if source_uri is not None and not isinstance(source_uri, str):
                raise ValueError("source_uri must be a string or null")
            return service.preview_intake(
                protocol_text,
                source_uri=source_uri,
            )
        except (KeyError, ValueError, TypeError, RuntimeError) as error:
            raise failure(error) from error

    @app.get("/v1/ai/rag/status")
    def rag_status() -> dict[str, Any]:
        if rag_corpus is None:
            return {
                "status": "DISABLED",
                "retriever_configured": False,
                "provider_configured": service.intake_provider is not None,
                "provider_ready": False,
                "heldout_status": "LOCKED_NOT_RUN",
            }
        configured_provider_id = (
            str(getattr(service.intake_provider, "provider_id", service.intake_provider.__class__.__name__))
            if service.intake_provider is not None else ""
        )
        configured_provider_endpoint = str(getattr(service.intake_provider, "endpoint", "")) if service.intake_provider else ""
        provider_identity_matches = bool(
            service.intake_provider is not None
            and configured_provider_id == rag_corpus.approved_provider_id
            and configured_provider_endpoint == rag_corpus.approved_provider_endpoint
        )
        return {
            "status": "RETRIEVAL_READY" if rag_corpus.chunk_count else "NOT_READY",
            "retriever_configured": True,
            "provider_configured": service.intake_provider is not None,
            "provider_identity_matches_approval": provider_identity_matches,
            "provider_ready": bool(
                service.intake_provider is not None
                and rag_corpus.provider_sharing_approved
                and rag_corpus.protocol_text_sharing_approved
                and provider_identity_matches
            ),
            "corpus_id": rag_corpus.corpus_id,
            "corpus_sha256": rag_corpus.corpus_sha256,
            "manifest_sha256": rag_corpus.manifest_sha256,
            "chunk_count": rag_corpus.chunk_count,
            "provider_sharing_approved": rag_corpus.provider_sharing_approved,
            "protocol_text_sharing_approved": rag_corpus.protocol_text_sharing_approved,
            "heldout_status": "LOCKED_NOT_RUN",
        }

    @app.post("/v1/ai/rag/retrieve")
    def retrieve_rag_evidence(payload: dict[str, Any]) -> dict[str, Any]:
        if rag_corpus is None:
            raise HTTPException(status_code=503, detail="Frozen approved RAG corpus is not configured.")
        try:
            if set(payload) - {"query", "k"}:
                raise ValueError("RAG retrieval request contains unsupported fields")
            query = payload.get("query")
            if not isinstance(query, str):
                raise ValueError("query must be a string")
            k = payload.get("k", 5)
            hits = rag_corpus.retrieve(query, k=k)
            return {
                "status": "MATCHES_FOUND" if hits else "NO_APPROVED_EVIDENCE_MATCH",
                "corpus_id": rag_corpus.corpus_id,
                "corpus_sha256": rag_corpus.corpus_sha256,
                "manifest_sha256": rag_corpus.manifest_sha256,
                "retrieved_evidence": [hit.as_dict() for hit in hits],
                "provider_called": False,
            }
        except (ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/ai/rag/draft")
    def create_rag_draft(payload: dict[str, Any]) -> dict[str, Any]:
        if rag_corpus is None:
            raise HTTPException(status_code=503, detail="Frozen approved RAG corpus is not configured.")
        try:
            protocol_text = payload.get("protocol_text")
            if not isinstance(protocol_text, str):
                raise ValueError("protocol_text must be a string")
            source_uri = payload.get("source_uri")
            if source_uri is not None and not isinstance(source_uri, str):
                raise ValueError("source_uri must be a string or null")
            k = payload.get("k", 5)
            if set(payload) - {"protocol_text", "source_uri", "k"}:
                raise ValueError("RAG draft request contains unsupported fields")
            return service.preview_rag_intake(protocol_text, rag_corpus, source_uri=source_uri, k=k)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except RuntimeError as error:
            if "not configured" in str(error):
                raise HTTPException(status_code=503, detail=str(error)) from error
            raise HTTPException(status_code=502, detail="RAG provider request failed; no draft was saved.") from error
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/research")
    def create_research_study(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            study = service.create_research_study(StudySpec.from_dict(payload))
            return {
                "study": study.as_dict(),
                "support_assessment": service.get_support_assessment(study.study_id),
            }
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/support-assessment")
    def assess_study_support(study_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            data = payload or {}
            context = data.get("required_context")
            if context is not None and not isinstance(context, dict):
                raise ValueError("required_context must be an object")
            return service.assess_support(study_id, required_context=context)
        except (KeyError, ValueError, TypeError, RuntimeError) as error:
            raise failure(error) from error

    @app.get("/v1/studies/{study_id}/support-assessment")
    def get_study_support(study_id: str) -> dict[str, Any]:
        try:
            assessment = service.get_support_assessment(study_id)
            if assessment is None:
                raise ValueError("support assessment has not been created")
            return assessment
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/support-approval")
    def approve_study_support(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            reviewer = payload.get("reviewer")
            return service.approve_support_assessment(
                study_id,
                reviewer=reviewer if isinstance(reviewer, str) else None,
            )
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/selection")
    def select_study_candidates(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return service.select_study(study_id, SelectionPolicy.from_dict(payload["policy"]))
        except (KeyError, ValueError, TypeError, RuntimeError) as error:
            raise failure(error) from error

    @app.post("/v1/worker/recover-stale")
    def recover_stale(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            data = payload or {}
            stale_after = float(data.get("stale_after_s", 3600.0))
            return {
                "recovered_jobs": [
                    job.as_dict()
                    for job in service.recover_stale_jobs(stale_after_s=stale_after)
                ]
            }
        except (ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/benchmarks/retrospective")
    def retrospective_benchmark(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            protocol = BenchmarkProtocol.from_dict(payload["protocol"])
            predictions = payload.get("predictions", {})
            if not isinstance(predictions, dict):
                raise ValueError("predictions must be an object keyed by case_id")
            return service.evaluate_benchmark(
                protocol,
                predictions,
                evaluation_split=str(payload.get("evaluation_split", "all")),
            )
        except (KeyError, ValueError, TypeError, RuntimeError) as error:
            raise failure(error) from error

    @app.post("/v1/benchmarks/compare")
    def compare_benchmark(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            protocol = BenchmarkProtocol.from_dict(payload["protocol"])
            systems = payload["predictions_by_system"]
            if not isinstance(systems, dict):
                raise ValueError("predictions_by_system must be an object keyed by system name")
            return service.compare_benchmark_systems(
                protocol,
                systems,
                evaluation_split=str(payload.get("evaluation_split", "held_out")),
            )
        except (KeyError, ValueError, TypeError, RuntimeError) as error:
            raise failure(error) from error

    @app.post("/v1/benchmarks/freeze")
    def freeze_benchmark(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            protocol = BenchmarkProtocol.from_dict(payload["protocol"])
            development = payload["development_case_ids"]
            held_out = payload["held_out_case_ids"]
            if not isinstance(development, list) or not isinstance(held_out, list):
                raise ValueError("development_case_ids and held_out_case_ids must be lists")
            frozen = freeze_benchmark_protocol(
                protocol,
                development_case_ids=development,
                held_out_case_ids=held_out,
                frozen_at=str(payload["frozen_at"]),
                label_policy=str(payload["label_policy"]),
                freeze_commit=(
                    None if payload.get("freeze_commit") is None else str(payload["freeze_commit"])
                ),
            )
            return frozen.as_dict()
        except (KeyError, ValueError, TypeError, RuntimeError) as error:
            raise failure(error) from error

    @app.post("/v1/benchmarks/sensitivity")
    def sensitivity(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            runs = payload["runs"]
            if not isinstance(runs, list):
                raise ValueError("runs must be a list")
            return service.sensitivity_report(runs)
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/rankings")
    def rank(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            observations = payload["observations"]
            if not isinstance(observations, list):
                raise ValueError("observations must be a list")
            policy = RankingPolicy.from_dict(payload["policy"])
            return service.rank_observations(observations, policy)
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies")
    def create_study(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return service.create_study(StudySpec.from_dict(payload)).as_dict()
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.get("/v1/studies")
    def list_studies() -> dict[str, Any]:
        return {"studies": [study.as_dict() for study in service.list_studies()]}

    @app.get("/v1/studies/{study_id}")
    def get_study(study_id: str) -> dict[str, Any]:
        try:
            return service.get_study(study_id).as_dict()
        except KeyError as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/jobs")
    def submit_job(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            job = service.submit_job(
                study_id,
                payload.get("config", {}),
                backend=payload.get("backend"),
                job_id=payload.get("job_id"),
            )
            if payload.get("run"):
                job = service.run_job(job.job_id)
            return job.as_dict()
        except (KeyError, ValueError, TypeError, RuntimeError) as error:
            raise failure(error) from error

    @app.get("/v1/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        try:
            return service.get_job(job_id).as_dict()
        except KeyError as error:
            raise failure(error) from error

    @app.post("/v1/jobs/{job_id}/run")
    def run_job(job_id: str) -> dict[str, Any]:
        try:
            return service.run_job(job_id).as_dict()
        except (KeyError, ValueError, RuntimeError) as error:
            raise failure(error) from error

    @app.post("/v1/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        try:
            return service.cancel_job(job_id).as_dict()
        except (KeyError, ValueError) as error:
            raise failure(error) from error

    @app.post("/v1/jobs/{job_id}/resume")
    def resume_job(job_id: str) -> dict[str, Any]:
        try:
            return service.resume_job(job_id).as_dict()
        except (KeyError, ValueError) as error:
            raise failure(error) from error

    @app.get("/v1/studies/{study_id}/jobs")
    def list_jobs(study_id: str) -> dict[str, Any]:
        try:
            service.get_study(study_id)
            return {"jobs": [job.as_dict() for job in service.list_jobs(study_id=study_id)]}
        except KeyError as error:
            raise failure(error) from error

    @app.get("/v1/studies/{study_id}/report")
    def get_report(study_id: str) -> dict[str, Any]:
        try:
            return service.get_report(study_id)
        except KeyError as error:
            raise failure(error) from error

    @app.get("/v1/studies/{study_id}/evidence-bundle")
    def get_evidence_bundle(study_id: str) -> dict[str, Any]:
        try:
            return service.get_evidence_bundle(study_id)
        except (KeyError, ValueError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/review")
    def record_review(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return service.record_review(
                study_id,
                reviewer=payload.get("reviewer"),
                decision=str(payload["decision"]),
                comments=str(payload.get("comments", "")),
            )
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/compare")
    def compare_jobs(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return service.compare_jobs(
                study_id,
                str(payload["reference_job_id"]),
                str(payload["condition_job_id"]),
            )
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/rank")
    def rank_study(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            policy = RankingPolicy.from_dict(payload["policy"])
            return service.rank_study(study_id, policy)
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/confirmation-plan")
    def confirmation_plan(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            seeds = payload.get("seeds")
            if seeds is not None and not isinstance(seeds, list):
                raise ValueError("seeds must be a list when supplied")
            return service.confirmation_plan(
                study_id,
                top_k=int(payload.get("top_k", 3)),
                explicit_seeds=seeds,
                sensitivity_grid=payload.get("sensitivity"),
            )
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/confirmation-plan/submit")
    def submit_confirmation(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            plan = payload.get("plan")
            if plan is not None and not isinstance(plan, dict):
                raise ValueError("plan must be an object when supplied")
            return service.submit_confirmation_plan(
                study_id,
                plan,
                include_sensitivity=bool(payload.get("include_sensitivity", False)),
            )
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/confirmation-plan/run")
    def run_confirmation(study_id: str) -> dict[str, Any]:
        try:
            return service.run_confirmation(study_id)
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/screening/submit")
    def submit_screening(study_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            seeds = payload["seeds"]
            if not isinstance(seeds, list):
                raise ValueError("seeds must be a list")
            candidates = payload.get("candidate_ids")
            if candidates is not None and not isinstance(candidates, list):
                raise ValueError("candidate_ids must be a list when supplied")
            config = payload.get("config")
            if config is not None and not isinstance(config, dict):
                raise ValueError("config must be an object when supplied")
            return service.submit_screening(
                study_id,
                seeds,
                candidate_ids=candidates,
                base_config=config,
            )
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    @app.post("/v1/studies/{study_id}/screening/run")
    def run_screening(study_id: str) -> dict[str, Any]:
        try:
            return service.run_screening(study_id)
        except (KeyError, ValueError, TypeError) as error:
            raise failure(error) from error

    return app


def _mapping_request_for_draft(draft: Any, candidate_id: str) -> Any:
    from drosophila_pd.ai_v2.mapping_resolution import MappingRequest

    study = draft.study
    candidate = next((item for item in study.candidates if item.candidate_id == candidate_id), None)
    if candidate is None or not candidate.target:
        raise ValueError("candidate_id must identify a draft candidate with an explicit target name")
    intervention_type = str(candidate.intervention.get("type", "none")).strip()
    if not intervention_type or intervention_type == "none":
        raise ValueError("mapping resolution requires a non-control intervention type")
    requirements = study.run_plan.get("backend_requirements", {})
    if not isinstance(requirements, Mapping):
        requirements = {}
    dataset_id = study.metadata.get("dataset_id") or requirements.get("dataset_id")
    id_namespace = study.metadata.get("id_namespace") or requirements.get("id_namespace")
    if study.metadata.get("dataset_id") and requirements.get("dataset_id") and study.metadata["dataset_id"] != requirements["dataset_id"]:
        raise ValueError("StudySpec dataset metadata conflict")
    if study.metadata.get("id_namespace") and requirements.get("id_namespace") and study.metadata["id_namespace"] != requirements["id_namespace"]:
        raise ValueError("StudySpec namespace metadata conflict")
    context = study.metadata.get("context", {})
    if not isinstance(context, Mapping):
        raise ValueError("StudySpec metadata.context must be an object")
    return MappingRequest(
        biological_target=candidate.target,
        backend=study.backend,
        dataset_id=str(dataset_id or ""),
        id_namespace=str(id_namespace or ""),
        intervention_type=intervention_type,
        context=dict(context),
    )


_WORKBENCH_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fly Research Workbench</title>
<style>
body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#10151b;color:#e8eef4}
textarea,input,button{font:inherit}textarea{width:100%;min-height:220px;background:#17212b;color:#e8eef4;border:1px solid #496274;padding:.75rem}
button{margin:.4rem .4rem .4rem 0;padding:.5rem .8rem;background:#2d7fc1;color:white;border:0;border-radius:4px;cursor:pointer}
pre{white-space:pre-wrap;background:#17212b;padding:1rem;border-radius:4px;overflow:auto}.card{border:1px solid #304657;border-radius:6px;padding:1rem;margin:1rem 0}
.muted{color:#9ab0c0}.pass{color:#7bd88f}.warn{color:#f2c66d}
</style></head><body>
<h1>Fly Research Workbench <small>v0.2 staging-capable</small></h1>
<p class="muted">Local study/job coordination. Computational completion is not biological validation.</p>
<section class="card"><h2>Staging API connection</h2>
<p class="muted">For an authenticated staging server, paste the temporary team token here. It is kept in this browser tab's session storage only.</p>
<input id="apiToken" type="password" autocomplete="off" placeholder="Staging bearer token" style="width:75%;background:#17212b;color:#e8eef4;border:1px solid #496274;padding:.55rem">
<button onclick="connectApi()">Connect</button><button onclick="disconnectApi()">Disconnect</button><span id="connectionStatus" class="muted">Checking server…</span></section>
<section class="card"><h2>Legacy study demo</h2><p class="muted">This endpoint preserves older ungated demo workflows. Use the evidence-gated research form below for new research studies.</p>
<textarea id="study">{"name":"motor pilot","hypothesis":"a declared perturbation changes path speed","falsifiable_prediction":"path speed differs from matched control","assay":"motor_flat_ground","primary_metric":"mean_planar_path_speed_mm_s","backend":"flygym_healthy","candidates":[{"candidate_id":"control","label":"No perturbation"}],"controls":[{"id":"control","role":"negative_control"}],"sources":[],"run_plan":{"seed_repetitions":10}}</textarea>
<br><button onclick="createStudy()">Create study</button><button onclick="loadAll()">Refresh</button></section>
<section class="card"><h2>Evidence-grounded RAG protocol draft</h2>
<p class="muted">Retrieval is local and limited to a frozen, checksum-verified, owner-approved DEVELOPMENT corpus. The AI provider receives the protocol and retrieved excerpts only when the corpus manifest explicitly approves both kinds of sharing. The result is a draft for researcher review; it cannot create studies, mappings, interventions, simulation settings, approvals, or jobs.</p>
<button onclick="loadRagStatus()">Check RAG readiness</button><button onclick="retrieveEvidence()">Retrieve evidence only</button><pre id="ragStatus">RAG status not checked.</pre>
<textarea id="protocolText" placeholder="Paste protocol text here"></textarea>
<input id="protocolSource" placeholder="Source URI (optional)" style="width:100%;background:#17212b;color:#e8eef4;border:1px solid #496274;padding:.55rem">
<br><button onclick="draftProtocol()">Retrieve + create AI draft</button><pre id="intakeResult">No RAG draft yet.</pre></section>
<section class="card"><h2>AI V2 workflow smoke test — synthetic only</h2>
<p class="muted">This example exercises exact mapping lookup, explicit human choice, separate approval, job submission and run. Its values and IDs are synthetic; it does not call an LLM, FlyWire, MN9, or a biological simulator. Do not present its output as science.</p>
<textarea id="aiStudyDraft">{"schema_version":"ai-v2-study-draft-1","study":{"name":"Synthetic staging smoke test","hypothesis":"The synthetic fixture changes an arbitrary scalar.","falsifiable_prediction":"Synthetic response differs from its fixture control.","assay":"synthetic_demo","primary_metric":"metrics.response","backend":"staging_fixture","candidates":[{"candidate_id":"control","label":"Synthetic control","intervention":{"type":"none"}},{"candidate_id":"condition","label":"Synthetic condition","target":"synthetic target","intervention":{"type":"activation"}}],"controls":[{"id":"control","role":"negative_control"}],"sources":[],"run_plan":{"backend_requirements":{"dataset_id":"synthetic_dataset","id_namespace":"synthetic_id"}},"metadata":{"dataset_id":"synthetic_dataset","id_namespace":"synthetic_id","context":{}}},"evidence_ids":["SYNTHETIC_EVIDENCE_CHUNK"],"approval_status":"DRAFT","provenance":{"provider_id":"synthetic-fixture-not-llm","prompt_version":"synthetic-ui-example-v1"}}</textarea>
<input id="aiCandidateId" value="condition" aria-label="Candidate ID" style="width:100%;background:#17212b;color:#e8eef4;border:1px solid #496274;padding:.55rem">
<br><button onclick="resolveAiMapping()">Resolve available mapping</button>
<select id="aiMappingChoice" style="width:100%;background:#17212b;color:#e8eef4;border:1px solid #496274;padding:.55rem"><option value="">Resolve first, then choose a mapping</option></select>
<br><button onclick="createAiDraft()">Create mapped DRAFT</button>
<input id="aiReviewer" placeholder="Human approver name" style="width:100%;background:#17212b;color:#e8eef4;border:1px solid #496274;padding:.55rem">
<br><button onclick="approveAiStudy()">Approve draft</button><button onclick="submitAiJob()">Submit job</button><button onclick="runAiJob()">Run synthetic job</button><button onclick="refreshAiWorkflow()">Refresh workflow/report</button>
<pre id="aiWorkflowResult">No synthetic workflow has been created.</pre></section>
<section class="card"><h2>Evidence-gated research study</h2>
<p class="muted">Create a support-gated study only after a researcher has checked the protocol draft. Candidate mappings are entered and reviewed separately.</p>
<textarea id="researchStudy">{"name":"MN9 pilot","hypothesis":"declared activation changes the MN9 response","falsifiable_prediction":"MN9 rate differs from matched control","assay":"sensory_mn9","primary_metric":"mn9_rate","backend":"lif_2024","candidates":[{"candidate_id":"control","label":"No stimulation","intervention":{"type":"none"}},{"candidate_id":"candidate-1","label":"Reviewed target","target":"target-name","intervention":{"type":"activation"},"metadata":{"mapping_id":"mapping-v1"}}],"controls":[{"id":"control","role":"negative_control"}],"sources":[],"run_plan":{"seed_repetitions":10},"metadata":{"dataset_id":"flywire-630","id_namespace":"flywire_root_id","context":{}}}</textarea>
<br><button onclick="createResearchStudy()">Create support-gated study</button>
<textarea id="mappingRecord">{"mapping_id":"mapping-v1","version":"1","biological_target":"target-name","backend":"lif_2024","id_namespace":"flywire_root_id","dataset_id":"flywire-630","intervention_type":"activation","target_ids":["123"],"sources":[{"citation":"paper DOI or title","locator":"figure/table/section"}],"review_status":"PENDING_SCIENTIFIC_REVIEW","context":{},"reviewer":null,"reviewed_at":null,"limitations":["Needs scientific review"]}</textarea>
<p class="muted">Review target IDs, namespace, dataset, context, and source evidence before changing review_status. Mapping IDs are immutable; a reviewed revision needs a new mapping ID and version.</p>
<br><button onclick="registerMapping()">Register human-authored mapping record</button>
<input id="supportReviewer" placeholder="Researcher/reviewer name" style="width:100%;background:#17212b;color:#e8eef4;border:1px solid #496274;padding:.55rem">
<textarea id="screenSeeds">[0,1,2,3,4,5,6,7,8,9]</textarea>
<textarea id="selectionPolicy">{"assay":"sensory_mn9","primary_metric":"mn9_rate","budget_k":3,"control_candidate_id":"control","minimum_pairs":3,"bootstrap_samples":1000,"minimum_direction_stability":0.8}</textarea>
<br><button onclick="assessSupport()">Assess support</button><button onclick="approveSupport()">Approve support assessment</button><button onclick="submitResearchScreening()">Submit screening jobs</button><button onclick="runResearchScreening()">Run screening jobs</button><button onclick="selectBudget()">Select within candidate budget</button>
<pre id="supportResult">Support assessment and candidate selection are recorded here.</pre></section>
<section class="card"><h2>Capabilities</h2><pre id="capabilities">Loading...</pre></section>
<section class="card"><h2>Studies and reports</h2><pre id="studies">Loading...</pre></section>
<section class="card"><h2>Ranking and confirmation</h2>
<p class="muted">All actions below are scoped to one study. Ranking requires a declared control, effect threshold and completed paired jobs.</p>
<input id="rankingStudy" placeholder="study_id" style="width:100%;background:#17212b;color:#e8eef4;border:1px solid #496274;padding:.55rem">
<textarea id="rankingPolicy">{"study_id":"STUDY_ID","control_candidate_id":"control","assay":"motor_flat_ground","primary_metric":"mean_planar_path_speed_mm_s","expected_direction":"increase","minimum_pairs":3,"bootstrap_samples":1000,"minimum_effect_threshold":0.5}</textarea>
<input id="topK" type="number" min="1" value="3" style="width:6rem;background:#17212b;color:#e8eef4;border:1px solid #496274;padding:.55rem">
<label><input id="includeSensitivity" type="checkbox"> include declared sensitivity reruns</label>
<br><button onclick="rankStudy()">Rank completed jobs</button><button onclick="makeConfirmationPlan()">Create confirmation plan</button><button onclick="submitConfirmation()">Submit confirmation jobs</button><button onclick="runConfirmation()">Run confirmation jobs</button><button onclick="loadHandoff()">Load handoff</button>
<pre id="ranking">No ranking action yet.</pre></section>
<p class="muted">This local page uses the same service as the CLI. Submission creates pending computational jobs; it does not run them or establish biological validation.</p>
<script>
const get=async (url,opts={})=>{const token=sessionStorage.getItem('workbench_api_token');const headers={'content-type':'application/json',...(opts.headers||{})};if(token)headers.Authorization='Bearer '+token;const r=await fetch(url,{...opts,headers});const x=await r.json();if(!r.ok)throw Error(JSON.stringify(x));return x};
const show=(id,x)=>document.getElementById(id).textContent=JSON.stringify(x,null,2);
const studyId=()=>document.getElementById('rankingStudy').value.trim();
let aiResolvedDraft=null, aiStudyId=null, aiJobId=null;
async function connectApi(){const token=document.getElementById('apiToken').value.trim();if(token)sessionStorage.setItem('workbench_api_token',token);try{await get('/v1/capabilities');document.getElementById('connectionStatus').textContent='Connected';await loadAll();await loadRagStatus()}catch(e){document.getElementById('connectionStatus').textContent='Connection failed: '+String(e)}}
function disconnectApi(){sessionStorage.removeItem('workbench_api_token');document.getElementById('apiToken').value='';document.getElementById('connectionStatus').textContent='Disconnected'}
async function resolveAiMapping(){try{aiResolvedDraft=JSON.parse(document.getElementById('aiStudyDraft').value);const result=await get('/v1/ai/mappings/resolve',{method:'POST',body:JSON.stringify({draft:aiResolvedDraft,candidate_id:document.getElementById('aiCandidateId').value.trim()})});const select=document.getElementById('aiMappingChoice');select.replaceChildren(new Option('Choose a reviewed mapping explicitly',''));for(const item of result.options||[]){select.add(new Option(item.mapping_id+' v'+item.version+' — '+item.review_status,JSON.stringify({mapping_id:item.mapping_id,version:item.version,record_hash:item.record_hash})))}show('aiWorkflowResult',result)}catch(e){show('aiWorkflowResult',{error:String(e)})}}
async function createAiDraft(){try{if(!aiResolvedDraft)throw Error('Resolve mappings first.');const value=document.getElementById('aiMappingChoice').value;if(!value)throw Error('Choose a mapping explicitly; the system will not auto-select.');const result=await get('/v1/ai/studies/draft',{method:'POST',body:JSON.stringify({draft:aiResolvedDraft,candidate_id:document.getElementById('aiCandidateId').value.trim(),mapping_selection:JSON.parse(value)})});aiStudyId=result.study.study_id;document.getElementById('rankingStudy').value=aiStudyId;show('aiWorkflowResult',result)}catch(e){show('aiWorkflowResult',{error:String(e)})}}
async function refreshAiWorkflow(){try{if(!aiStudyId)throw Error('Create the mapped draft first.');show('aiWorkflowResult',await get('/v1/ai/studies/'+aiStudyId+'/workflow'))}catch(e){show('aiWorkflowResult',{error:String(e)})}}
async function approveAiStudy(){try{if(!aiStudyId)throw Error('Create the mapped draft first.');show('aiWorkflowResult',await get('/v1/ai/studies/'+aiStudyId+'/approval',{method:'POST',body:JSON.stringify({reviewer:document.getElementById('aiReviewer').value.trim()})}))}catch(e){show('aiWorkflowResult',{error:String(e)})}}
async function submitAiJob(){try{if(!aiStudyId)throw Error('Create and approve the draft first.');const result=await get('/v1/ai/studies/'+aiStudyId+'/jobs',{method:'POST',body:JSON.stringify({candidate_id:document.getElementById('aiCandidateId').value.trim()})});aiJobId=result.job.job_id;show('aiWorkflowResult',result)}catch(e){show('aiWorkflowResult',{error:String(e)})}}
async function runAiJob(){try{if(!aiJobId)throw Error('Submit a job first.');show('aiWorkflowResult',await get('/v1/ai/jobs/'+aiJobId+'/run',{method:'POST',body:'{}'}))}catch(e){show('aiWorkflowResult',{error:String(e)})}}
async function loadAll(){try{show('capabilities',await get('/v1/capabilities'));const studies=await get('/v1/studies');for(const s of studies.studies){s.jobs=await get('/v1/studies/'+s.study_id+'/jobs');s.report=await get('/v1/studies/'+s.study_id+'/report')}if(!studyId()&&studies.studies.length){document.getElementById('rankingStudy').value=studies.studies[0].study_id;const p=JSON.parse(document.getElementById('rankingPolicy').value);p.study_id=studies.studies[0].study_id;document.getElementById('rankingPolicy').value=JSON.stringify(p,null,2)}show('studies',studies)}catch(e){show('studies',{error:String(e)})}}
async function createStudy(){try{const value=JSON.parse(document.getElementById('study').value);await get('/v1/studies',{method:'POST',body:JSON.stringify(value)});await loadAll()}catch(e){show('studies',{error:String(e)})}}
async function loadRagStatus(){try{show('ragStatus',await get('/v1/ai/rag/status'))}catch(e){show('ragStatus',{error:String(e)})}}
async function retrieveEvidence(){try{show('intakeResult',await get('/v1/ai/rag/retrieve',{method:'POST',body:JSON.stringify({query:document.getElementById('protocolText').value,k:5})}))}catch(e){show('intakeResult',{error:String(e)})}}
async function draftProtocol(){try{show('intakeResult',await get('/v1/ai/rag/draft',{method:'POST',body:JSON.stringify({protocol_text:document.getElementById('protocolText').value,source_uri:document.getElementById('protocolSource').value||null,k:5})}))}catch(e){show('intakeResult',{error:String(e)})}}
async function createResearchStudy(){try{const value=JSON.parse(document.getElementById('researchStudy').value);const result=await get('/v1/studies/research',{method:'POST',body:JSON.stringify(value)});document.getElementById('rankingStudy').value=result.study.study_id;show('supportResult',result);await loadAll()}catch(e){show('supportResult',{error:String(e)})}}
async function registerMapping(){try{show('supportResult',await get('/v1/mapping-records',{method:'POST',body:JSON.stringify(JSON.parse(document.getElementById('mappingRecord').value))}))}catch(e){show('supportResult',{error:String(e)})}}
async function assessSupport(){try{show('supportResult',await get('/v1/studies/'+studyId()+'/support-assessment',{method:'POST',body:'{}'}))}catch(e){show('supportResult',{error:String(e)})}}
async function approveSupport(){try{show('supportResult',await get('/v1/studies/'+studyId()+'/support-approval',{method:'POST',body:JSON.stringify({reviewer:document.getElementById('supportReviewer').value})}))}catch(e){show('supportResult',{error:String(e)})}}
async function submitResearchScreening(){try{show('supportResult',await get('/v1/studies/'+studyId()+'/screening/submit',{method:'POST',body:JSON.stringify({seeds:JSON.parse(document.getElementById('screenSeeds').value)})}))}catch(e){show('supportResult',{error:String(e)})}}
async function runResearchScreening(){try{show('supportResult',await get('/v1/studies/'+studyId()+'/screening/run',{method:'POST',body:'{}'}))}catch(e){show('supportResult',{error:String(e)})}}
async function selectBudget(){try{const policy=JSON.parse(document.getElementById('selectionPolicy').value);policy.study_id=studyId();show('supportResult',await get('/v1/studies/'+studyId()+'/selection',{method:'POST',body:JSON.stringify({policy})}))}catch(e){show('supportResult',{error:String(e)})}}
async function rankStudy(){try{const id=studyId();const policy=JSON.parse(document.getElementById('rankingPolicy').value);policy.study_id=id;show('ranking',await get('/v1/studies/'+id+'/rank',{method:'POST',body:JSON.stringify({policy})}))}catch(e){show('ranking',{error:String(e)})}}
async function makeConfirmationPlan(){try{const id=studyId();show('ranking',await get('/v1/studies/'+id+'/confirmation-plan',{method:'POST',body:JSON.stringify({top_k:Number(document.getElementById('topK').value)})}))}catch(e){show('ranking',{error:String(e)})}}
async function submitConfirmation(){try{const id=studyId();show('ranking',await get('/v1/studies/'+id+'/confirmation-plan/submit',{method:'POST',body:JSON.stringify({include_sensitivity:document.getElementById('includeSensitivity').checked})}))}catch(e){show('ranking',{error:String(e)})}}
async function runConfirmation(){try{const id=studyId();show('ranking',await get('/v1/studies/'+id+'/confirmation-plan/run',{method:'POST',body:'{}'}))}catch(e){show('ranking',{error:String(e)})}}
async function loadHandoff(){try{show('ranking',await get('/v1/studies/'+studyId()+'/evidence-bundle'))}catch(e){show('ranking',{error:String(e)})}}
async function bootstrap(){try{const state=await get('/healthz');if(state.authentication_required){document.getElementById('connectionStatus').textContent='Token required for staging';const saved=sessionStorage.getItem('workbench_api_token');if(saved){document.getElementById('apiToken').value=saved;await connectApi()}}else{document.getElementById('connectionStatus').textContent='Local mode';await loadAll()}}catch(e){document.getElementById('connectionStatus').textContent='Server unavailable'}}
bootstrap();
</script></body></html>"""


__all__ = ["create_app"]
