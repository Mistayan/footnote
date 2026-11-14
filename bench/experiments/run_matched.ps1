# -TailOnly skips the model checks and engine runs and resumes at the paired intervals (after a crash in the tail).
param([string]$AfterLog = 'bench/work/model_latency.log', [switch]$TailOnly)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
Set-Location -LiteralPath (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
if (-not $TailOnly) {
Write-Output "Waiting for $AfterLog"
while (-not ((Test-Path -LiteralPath $AfterLog) -and ((Get-Content -LiteralPath $AfterLog) -contains 'DONE'))) {
    Start-Sleep -Seconds 20
}

Write-Output '== heldout checks for dev-qualified model configurations'
& rtk proxy bench/.labenv/Scripts/python.exe -I bench/experiments/confirm_models.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$failedRuns = 0
foreach ($dataset in @('syntec', 'nfcorpus', 'scifact', 'alloprof', 'mix-fr-en')) {
    if (-not (Test-Path -LiteralPath "bench/work/matched-inputs/$dataset/meta.json")) {
        & rtk proxy bench/.labenv/Scripts/python.exe -I bench/experiments/matched_inputs.py $dataset
        if ($LASTEXITCODE -ne 0) {
            @{ timestamp_utc = [DateTime]::UtcNow.ToString('o'); dataset = $dataset; engine = 'input-export'; exit_code = $LASTEXITCODE } |
                ConvertTo-Json -Compress | Add-Content -LiteralPath 'bench/work/matched-failures.jsonl'
            $failedRuns++
            continue
        }
    }
    foreach ($engine in @('matched-sqlite-tantivy', 'matched-lance-rrf', 'matched-lance-cc', 'matched-lance-tantivy')) {
        Write-Output "== $dataset $engine"
        & rtk proxy bench/.dbenv/Scripts/python.exe -I bench/run.py $dataset "ext:$engine"
        if ($LASTEXITCODE -ne 0) {
            @{ timestamp_utc = [DateTime]::UtcNow.ToString('o'); dataset = $dataset; engine = $engine; exit_code = $LASTEXITCODE } |
                ConvertTo-Json -Compress | Add-Content -LiteralPath 'bench/work/matched-failures.jsonl'
            $failedRuns++
        }
    }
}
foreach ($track in @('competitors', 'matched')) {
    $reportArgs = @('proxy', 'bench/.dbenv/Scripts/python.exe', '-I', 'bench/experiments/headtohead_table.py', '--since', '20261113T070000Z')
    if ($track -eq 'matched') { $reportArgs += '--matched' }
    $reportText = & rtk @reportArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $reportPath = if ($track -eq 'matched') { 'bench/experiments/LANCEDB-RESULTS.md' } else { 'bench/experiments/HEADTOHEAD.md' }
    $reportText | Set-Content -LiteralPath $reportPath -Encoding utf8
}
$modelReport = & rtk proxy bench/.dbenv/Scripts/python.exe -I bench/sweep_report.py models2 --split dev
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
@('# Model candidate dev results', '', 'Tuning results only. These are not end-to-end latency measurements or heldout confirmation.', '') + $modelReport |
    Set-Content -LiteralPath 'bench/experiments/MODEL-CANDIDATES.md' -Encoding utf8
$encodingReport = @('# Resident query encoding', '', 'Encoding only, no retrieval or query cache. Same fixed dev queries per corpus for every model.', '',
                    '| Dataset | Model | Queries | Dimensions | p50 ms | p95 ms | Model files MiB |', '|---|---|---:|---:|---:|---:|---:|')
foreach ($row in (Get-Content -LiteralPath 'bench/sweeps/model_latency.jsonl' | ConvertFrom-Json)) {
    $latency = $row.latency_ms
    $size = [Math]::Round($row.model_bytes / 1MB, 2)
    $encodingReport += "| $($row.dataset) | $($row.model) | $($latency.queries) | $($latency.dimensions) | $($latency.p50) | $($latency.p95) | $size |"
}
$encodingReport | Set-Content -LiteralPath 'bench/experiments/MODEL-LATENCY.md' -Encoding utf8

if ($failedRuns -gt 0) {
    Write-Output "FAILED: $failedRuns runs; see bench/work/matched-failures.jsonl"
    exit 1
}
}
$intervalReport = @('# Paired retrieval intervals', '', 'Paired bootstrap, 10,000 query resamples and fixed seed. Per-comparison intervals, without multiplicity correction. Competitor configurations differ in models/chunking; matched controls use identical frozen vectors and exclude encoding.', '')
foreach ($track in @('competitors', 'matched')) {
    $baseline = if ($track -eq 'matched') { 'matched-sqlite-tantivy' } else { 'shipped-ensemble-mcp' }
    $variants = if ($track -eq 'matched') { @('matched-lance-rrf', 'matched-lance-cc', 'matched-lance-tantivy') } else { @('mem0', 'mem0-multilingual', 'cognee', 'cognee-lexical', 'cognee-multilingual') }
    foreach ($dataset in @('syntec', 'nfcorpus', 'scifact', 'alloprof', 'mix-fr-en')) {
        $first = Get-ChildItem -LiteralPath 'bench/receipts' -Filter "*-$dataset-$baseline.json" |
            Where-Object { $_.Name -ge '20261113T070000Z' } | Sort-Object Name -Descending | Select-Object -First 1
        if ($null -eq $first) { throw "Missing baseline receipt: $dataset $baseline" }
        foreach ($variant in $variants) {
            if ($track -eq 'competitors' -and $dataset -eq 'mix-fr-en' -and $variant -notin @('mem0-multilingual', 'cognee-multilingual')) { continue }
            $second = Get-ChildItem -LiteralPath 'bench/receipts' -Filter "*-$dataset-$variant.json" |
                Where-Object { $_.Name -ge '20261113T070000Z' } | Sort-Object Name -Descending | Select-Object -First 1
            if ($null -eq $second) {  # a competitor run that failed has no receipt: report the gap, keep the other comparisons
                $intervalReport += @("**No comparison for $dataset / ${variant}:** no complete receipt (the run failed or was not made).", '')
                continue
            }
            $a = $first.FullName -replace '\.json$', '.rankings.json.gz'
            $b = $second.FullName -replace '\.json$', '.rankings.json.gz'
            $comparison = & rtk proxy bench/.dbenv/Scripts/python.exe -I bench/compare.py $dataset $a $b --resamples 10000
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            $intervalReport += @('```text') + $comparison + @('```', '', "[Baseline](../receipts/$($first.Name)), [candidate](../receipts/$($second.Name)).", '')
        }
    }
}
$intervalReport | Set-Content -LiteralPath 'bench/experiments/HEADTOHEAD-INTERVALS.md' -Encoding utf8
Write-Output '== lexical scale, 100k and 1M synthetic documents, three backends'
& rtk proxy bench/.dbenv/Scripts/python.exe -I bench/dbbake/track_a_scale.py --sizes 100000,1000000
if ($LASTEXITCODE -ne 0) {
    $scaleExit = $LASTEXITCODE
    @{ timestamp_utc = [DateTime]::UtcNow.ToString('o'); dataset = 'synthetic-100k-1M'; engine = 'lexical-scale'; exit_code = $scaleExit } |
        ConvertTo-Json -Compress | Add-Content -LiteralPath 'bench/work/matched-failures.jsonl'
    exit $scaleExit
}

foreach ($pattern in @('test_headtohead_table.py', 'test_model_latency.py', 'test_matched.py', 'test_confirm_models.py')) {
    & rtk proxy bench/.dbenv/Scripts/python.exe -I -m unittest discover -s bench/experiments -p $pattern -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
foreach ($command in @(@('cargo', 'fmt', '--check'), @('cargo', 'clippy', '--all-targets'), @('cargo', 'test'),
                       @('proxy', 'bench/.dbenv/Scripts/python.exe', '-I', 'bench/test_metrics.py'),
                       @('proxy', 'bench/.dbenv/Scripts/python.exe', '-I', 'bench/test_validation.py'), @('git', 'diff', '--check'))) {
    Write-Output "== check: rtk $($command -join ' ')"
    & rtk @command
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
Write-Output 'DONE'
