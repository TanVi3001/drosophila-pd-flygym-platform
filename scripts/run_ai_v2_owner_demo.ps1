param(
    [string]$Python = 'E:\research-\.venvs\ai-v2-staging-312\Scripts\python.exe',
    [string]$FrozenPackage = '.workbench/evidence/owner_demo_protocol_frozen_v1',
    [switch]$Run,
    [switch]$PromptForKey
)

# Default is an offline integrity/schema check. Credentials never enter argv.
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskExit = 2
$taskSecret = $null
$taskOldEnvironment = @{}
$taskEnvironmentNames = @(
    'WORKBENCH_INTAKE_BASE_URL', 'WORKBENCH_INTAKE_MODEL',
    'WORKBENCH_INTAKE_API_KEY_ENV', 'WORKBENCH_LLM_KEY'
)
foreach ($taskName in $taskEnvironmentNames) {
    $taskOldEnvironment[$taskName] = [Environment]::GetEnvironmentVariable($taskName, 'Process')
}

Push-Location -LiteralPath $taskRoot
try {
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw 'The specified staging Python executable is unavailable.'
    }
    & $Python scripts/prepare_ai_v2_owner_demo.py --check-frozen --review-package $FrozenPackage
    if ($LASTEXITCODE -ne 0) { throw 'Frozen package integrity failed. No provider call made.' }

    $taskArguments = @(
        'scripts/compare_ai_v2_protocols.py',
        '--corpus', (Join-Path $FrozenPackage 'protocol_development_corpus_draft.jsonl'),
        '--rubric', (Join-Path $FrozenPackage 'reference_owner_reviewed.json'),
        '--manifest', (Join-Path $FrozenPackage 'corpus.manifest.json'),
        '--manual', (Join-Path $FrozenPackage 'manual_template_pending.json')
    )
    if ($Run) {
        $taskDecision = Get-Content -LiteralPath (Join-Path $FrozenPackage 'owner_decision.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $taskBaseUrl = $taskDecision.provider_endpoint -replace '/chat/completions$', ''
        $env:WORKBENCH_INTAKE_BASE_URL = $taskBaseUrl
        $env:WORKBENCH_INTAKE_MODEL = $taskDecision.model_id
        $env:WORKBENCH_INTAKE_API_KEY_ENV = 'WORKBENCH_LLM_KEY'
        if ([string]::IsNullOrWhiteSpace($env:WORKBENCH_LLM_KEY) -and $PromptForKey) {
            $taskSecret = Read-Host 'Gemini API key (hidden; do not paste in chat)' -AsSecureString
            $taskPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($taskSecret)
            try {
                $env:WORKBENCH_LLM_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($taskPointer)
            } finally {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($taskPointer)
            }
        }
        if ([string]::IsNullOrWhiteSpace($env:WORKBENCH_LLM_KEY)) {
            throw 'BLOCKED_MISSING_CREDENTIAL: rerun with -Run -PromptForKey; no provider call made.'
        }
        $taskOutput = Join-Path '.workbench/ai-v2-comparisons' ('paired-' + [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
        $taskArguments += @('--run', '--allow-provider-calls', '--output-dir', $taskOutput)
        Write-Output "Result directory: $taskOutput"
    } else {
        $taskArguments += '--dry-run'
    }
    & $Python @taskArguments
    $taskExit = $LASTEXITCODE
    if ($Run -and $taskExit -eq 1) {
        Write-Output 'Comparison is incomplete (manual baseline is PENDING); inspect actual report and errors. This is not a full three-arm PASS.'
    }
} catch {
    # No exception details: do not accidentally disclose private inputs/keys.
    Write-Output 'BLOCKED: check frozen integrity and local key. If the offline check passes and no key is configured, use -Run -PromptForKey.'
} finally {
    foreach ($taskName in $taskEnvironmentNames) {
        [Environment]::SetEnvironmentVariable($taskName, $taskOldEnvironment[$taskName], 'Process')
    }
    if ($null -ne $taskSecret) { $taskSecret.Dispose() }
    Pop-Location
}
exit $taskExit
