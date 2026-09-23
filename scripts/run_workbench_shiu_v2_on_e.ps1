[CmdletBinding()]
param(
    [string]$RunName = "",
    [switch]$DryRun,
    [int]$Seed = 20260922,
    [int]$Trials = 1,
    [double]$DurationS = 1.0,
    [double]$StimulusRateHz = 50.0
)

$ErrorActionPreference = "Stop"

$FlyGymRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WorkspaceRoot = (Resolve-Path (Join-Path $FlyGymRoot "..")).Path
if ((Split-Path -Path $WorkspaceRoot -Qualifier) -ne "E:") {
    throw "This wrapper is intentionally pinned to E:. Current workspace: $WorkspaceRoot"
}
$NeuralRepo = Join-Path $WorkspaceRoot "drosophila-pd-neural-disease"
$ModelRoot = Join-Path $WorkspaceRoot "external\Drosophila_brain_model"
$ResultsRoot = Join-Path $ModelRoot "results"
$Python = Join-Path $WorkspaceRoot ".venvs\baseline-2024-312\Scripts\python.exe"
$BatchScript = Join-Path $FlyGymRoot "scripts\run_shiu_v2_rewired_lif_batch.py"
$LifScript = Join-Path $NeuralRepo "scripts\run_lif_condition.py"
$Protocol = Join-Path $FlyGymRoot "configs\workbench\shiu_public_benchmark_v2.json"
$Mapping = Join-Path $FlyGymRoot "configs\workbench\shiu_v2_flywire630_mapping.csv"
$Connectivity = Join-Path $ModelRoot "results\workbench_graph_nulls\flywire630_v1\graph_null_630_seed20260922_r01.parquet"
$Annotation = Join-Path $NeuralRepo "annotations\flywire630_shiu_table3_upstream.csv"
$Completeness = Join-Path $ModelRoot "2023_03_23_completeness_630_final.csv"

foreach ($required in @($Python, $BatchScript, $LifScript, $Protocol, $Mapping, $Connectivity, $Annotation, $Completeness)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file is missing: $required"
    }
}

if ([string]::IsNullOrWhiteSpace($RunName)) {
    $RunName = "workbench_shiu_v2_rewired_lif_{0}" -f (Get-Date -Format "yyyyMMdd_HHmmss")
}
$OutputRoot = Join-Path $ResultsRoot $RunName
$BatchSummary = Join-Path $OutputRoot "batch_summary.json"
$TempRoot = Join-Path $ModelRoot "tmp\workbench_shiu_v2"

New-Item -ItemType Directory -Force -Path $OutputRoot, $TempRoot | Out-Null

# Keep Python, joblib, Brian2 code generation, and temporary model files on E:.
$env:TEMP = $TempRoot
$env:TMP = $TempRoot
$env:JOBLIB_TEMP_FOLDER = Join-Path $TempRoot "joblib"
$env:PYTHONNOUSERSITE = "1"
$env:PATH = "{0};{1}" -f (Split-Path $Python), $env:PATH

$Arguments = @(
    $BatchScript,
    "--protocol", $Protocol,
    "--mapping", $Mapping,
    "--connectivity", $Connectivity,
    "--neural-repo", $NeuralRepo,
    "--neural-python", $Python,
    "--lif-script", $LifScript,
    "--model-root", $ModelRoot,
    "--annotation-file", $Annotation,
    "--output-root", $OutputRoot,
    "--output", $BatchSummary,
    "--seed", $Seed,
    "--trials", $Trials,
    "--duration-s", $DurationS,
    "--stimulus-rate-hz", $StimulusRateHz
)
if ($DryRun) {
    $Arguments += "--dry-run"
}

Write-Host "Python:       $Python"
Write-Host "Output root:  $OutputRoot"
Write-Host "Temp root:    $TempRoot"
Write-Host "Dry run:      $DryRun"

& $Python @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "Workbench batch failed with exit code $LASTEXITCODE. See $OutputRoot"
}
