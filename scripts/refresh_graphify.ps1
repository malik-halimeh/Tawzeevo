param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string] $IntendedSha,

    [switch] $CheckOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$policyPath = Join-Path $repositoryRoot 'docs\assurance\GRAPHIFY.md'
$graphPath = Join-Path $repositoryRoot 'graphify-out\graph.json'

function Invoke-GraphifyText {
    param([string[]] $Arguments)

    $result = & graphify @Arguments 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "Graphify failed: graphify $($Arguments -join ' ')`n$result"
    }
    return $result
}

Push-Location $repositoryRoot
try {
    if (-not (Get-Command graphify -ErrorAction SilentlyContinue)) {
        throw 'Graphify is not installed. Install it in an isolated uv tool environment: uv --system-certs tool install graphifyy'
    }

    $resolvedSha = (& git rev-parse --verify "$IntendedSha^{commit}").Trim()
    if ($LASTEXITCODE -ne 0 -or $resolvedSha -ne $IntendedSha.ToLowerInvariant()) {
        throw "Intended SHA does not resolve exactly: $IntendedSha"
    }

    $headSha = (& git rev-parse HEAD).Trim()
    if ($headSha -ne $resolvedSha) {
        throw "HEAD ($headSha) does not match CURRENT_INTENDED_SHA ($resolvedSha)."
    }

    $versionOutput = Invoke-GraphifyText -Arguments @('--version')
    if ($versionOutput -notmatch '(?<version>\d+\.\d+\.\d+)') {
        throw "Could not determine Graphify version from: $versionOutput"
    }
    $graphifyVersion = $Matches.version

    if (-not $CheckOnly) {
        $trackedChanges = & git status --porcelain=v1 --untracked-files=no
        if ($trackedChanges) {
            throw 'Tracked working-tree changes exist. Commit or restore them before building a commit-addressed graph.'
        }
        Invoke-GraphifyText -Arguments @('extract', '.', '--code-only', '--no-cluster', '--force') | Out-Null
    }

    if (-not (Test-Path -LiteralPath $graphPath)) {
        throw 'graphify-out/graph.json is missing; run the script without -CheckOnly.'
    }

    $graph = Get-Content -Raw -LiteralPath $graphPath | ConvertFrom-Json
    $nodeCount = @($graph.nodes).Count
    $edgeCount = @($graph.edges).Count
    if ($nodeCount -lt 1 -or $edgeCount -lt 1) {
        throw "Graph is unexpectedly empty (nodes=$nodeCount, edges=$edgeCount)."
    }

    $routePath = Invoke-GraphifyText -Arguments @('path', 'confirm_invoice_editor()', 'confirm_invoice()')
    $tenantRepository = Invoke-GraphifyText -Arguments @('explain', 'set_tenant_scope()')
    $invoiceTest = Invoke-GraphifyText -Arguments @(
        'explain',
        'test_confirmation_is_idempotent_assigns_official_number_and_posts_one_charge()'
    )

    if ($routePath -notmatch 'calls \[EXTRACTED\]' -or $routePath -notmatch 'confirm_invoice') {
        throw 'Representative API-to-service extracted path validation failed.'
    }
    if ($tenantRepository -notmatch 'repositories[/\\]tenancy\.py') {
        throw 'Representative repository/database symbol validation failed.'
    }
    if ($invoiceTest -notmatch 'tests[/\\]test_invoice_editor\.py') {
        throw 'Representative financial test symbol validation failed.'
    }

    $policyText = Get-Content -Raw -LiteralPath $policyPath
    $statePattern = '(?s)<!-- GRAPHIFY_STATE_START -->.*?<!-- GRAPHIFY_STATE_END -->'
    if ($policyText -notmatch $statePattern) {
        throw 'Graphify freshness state block is missing from the policy.'
    }

    if ($CheckOnly) {
        if ($policyText -notmatch "GRAPH_SOURCE_SHA=$([regex]::Escape($resolvedSha))") {
            throw "Recorded GRAPH_SOURCE_SHA does not match CURRENT_INTENDED_SHA ($resolvedSha)."
        }
        if ($policyText -notmatch "GRAPHIFY_VERSION=$([regex]::Escape($graphifyVersion))") {
            throw "Recorded Graphify version does not match installed version ($graphifyVersion)."
        }
    }
    else {
        $refreshedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        $state = @"
<!-- GRAPHIFY_STATE_START -->
GRAPH_SOURCE_SHA=$resolvedSha
GRAPH_REFRESHED_AT_UTC=$refreshedAt
GRAPHIFY_VERSION=$graphifyVersion
GRAPH_MODE=structural-code-only-no-cluster
GRAPH_VALIDATION=PASS
GRAPH_NODES=$nodeCount
GRAPH_EDGES=$edgeCount
<!-- GRAPHIFY_STATE_END -->
"@
        $updatedPolicy = [regex]::Replace($policyText, $statePattern, $state)
        [System.IO.File]::WriteAllText($policyPath, $updatedPolicy, [System.Text.UTF8Encoding]::new($false))
    }

    Write-Output "Graphify validation PASS: sha=$resolvedSha version=$graphifyVersion nodes=$nodeCount edges=$edgeCount"
}
finally {
    Pop-Location
}
