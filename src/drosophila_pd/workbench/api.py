"""Optional FastAPI surface backed by :class:`WorkbenchService`."""

from __future__ import annotations

from typing import Any

from .benchmark import BenchmarkProtocol, freeze_benchmark_protocol
from .models import StudySpec
from .ranking import RankingPolicy
from .service import WorkbenchService


def create_app(service: WorkbenchService) -> Any:
    """Create the localhost API; FastAPI remains an optional dependency."""

    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import HTMLResponse
    except ImportError as error:  # pragma: no cover - depends on optional extra
        raise RuntimeError("install the 'workbench' extra to run the FastAPI server") from error

    app = FastAPI(title="Fly Research Workbench", version="0.1")

    @app.get("/", response_class=HTMLResponse)
    def workbench_page() -> str:
        return _WORKBENCH_HTML

    def failure(error: Exception) -> HTTPException:
        status = 404 if isinstance(error, KeyError) else 400
        return HTTPException(status_code=status, detail=str(error))

    @app.get("/v1/capabilities")
    def capabilities() -> dict[str, Any]:
        return {"capabilities": service.capabilities()}

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
<h1>Fly Research Workbench <small>v0.1</small></h1>
<p class="muted">Local study/job coordination. Computational completion is not biological validation.</p>
<section class="card"><h2>Create study</h2>
<textarea id="study">{"name":"motor pilot","hypothesis":"a declared perturbation changes path speed","falsifiable_prediction":"path speed differs from matched control","assay":"motor_flat_ground","primary_metric":"mean_planar_path_speed_mm_s","backend":"flygym_healthy","candidates":[{"candidate_id":"control","label":"No perturbation"}],"controls":[{"id":"control","role":"negative_control"}],"sources":[],"run_plan":{"seed_repetitions":10}}</textarea>
<br><button onclick="createStudy()">Create study</button><button onclick="loadAll()">Refresh</button></section>
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
const get=async (url,opts={})=>{const r=await fetch(url,{headers:{'content-type':'application/json'},...opts});const x=await r.json();if(!r.ok)throw Error(JSON.stringify(x));return x};
const show=(id,x)=>document.getElementById(id).textContent=JSON.stringify(x,null,2);
const studyId=()=>document.getElementById('rankingStudy').value.trim();
async function loadAll(){try{show('capabilities',await get('/v1/capabilities'));const studies=await get('/v1/studies');for(const s of studies.studies){s.jobs=await get('/v1/studies/'+s.study_id+'/jobs');s.report=await get('/v1/studies/'+s.study_id+'/report')}if(!studyId()&&studies.studies.length){document.getElementById('rankingStudy').value=studies.studies[0].study_id;const p=JSON.parse(document.getElementById('rankingPolicy').value);p.study_id=studies.studies[0].study_id;document.getElementById('rankingPolicy').value=JSON.stringify(p,null,2)}show('studies',studies)}catch(e){show('studies',{error:String(e)})}}
async function createStudy(){try{const value=JSON.parse(document.getElementById('study').value);await get('/v1/studies',{method:'POST',body:JSON.stringify(value)});await loadAll()}catch(e){show('studies',{error:String(e)})}}
async function rankStudy(){try{const id=studyId();const policy=JSON.parse(document.getElementById('rankingPolicy').value);policy.study_id=id;show('ranking',await get('/v1/studies/'+id+'/rank',{method:'POST',body:JSON.stringify({policy})}))}catch(e){show('ranking',{error:String(e)})}}
async function makeConfirmationPlan(){try{const id=studyId();show('ranking',await get('/v1/studies/'+id+'/confirmation-plan',{method:'POST',body:JSON.stringify({top_k:Number(document.getElementById('topK').value)})}))}catch(e){show('ranking',{error:String(e)})}}
async function submitConfirmation(){try{const id=studyId();show('ranking',await get('/v1/studies/'+id+'/confirmation-plan/submit',{method:'POST',body:JSON.stringify({include_sensitivity:document.getElementById('includeSensitivity').checked})}))}catch(e){show('ranking',{error:String(e)})}}
async function runConfirmation(){try{const id=studyId();show('ranking',await get('/v1/studies/'+id+'/confirmation-plan/run',{method:'POST',body:'{}'}))}catch(e){show('ranking',{error:String(e)})}}
async function loadHandoff(){try{show('ranking',await get('/v1/studies/'+studyId()+'/evidence-bundle'))}catch(e){show('ranking',{error:String(e)})}}
loadAll();
</script></body></html>"""


__all__ = ["create_app"]
