# Learning task synchronization. Run with PowerShell 7 from any directory.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Before', 'After')][string]$Mode,
    [string[]]$Paths = @('helpstudy'),
    [string]$Message = 'study: update learning records'
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-StudyGit {
    param([string[]]$Arguments)
    $result = & git -C $repoRoot @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Git failed: $($Arguments -join ' ')`n$($result -join "`n")"
    }
    # Native stderr warnings must not be treated as paths or Git query values.
    foreach ($entry in $result) {
        if ($entry -is [System.Management.Automation.ErrorRecord]) {
            Write-Host $entry.ToString()
        } else {
            Write-Output ([string]$entry)
        }
    }
}

$branch = (Invoke-StudyGit @('branch', '--show-current') | Out-String).Trim()
if ($branch -ne 'main') { throw 'Learning sync requires main; current branch was preserved.' }
$remote = (Invoke-StudyGit @('remote', 'get-url', 'origin') | Out-String).Trim()
if ($remote -ne 'https://github.com/Chr0n05-E/my_knowledge.git') {
    throw 'Unexpected origin; no changes were made.'
}
foreach ($operation in @('MERGE_HEAD', 'rebase-merge', 'rebase-apply', 'CHERRY_PICK_HEAD')) {
    $operationPath = (Invoke-StudyGit @('rev-parse', '--git-path', $operation) | Out-String).Trim()
    if (-not [IO.Path]::IsPathRooted($operationPath)) { $operationPath = Join-Path $repoRoot $operationPath }
    if (Test-Path -LiteralPath $operationPath) { throw "Finish existing Git operation first: $operation" }
}

if ($Mode -eq 'Before') {
    Invoke-StudyGit @('fetch', 'origin') | Write-Output
    $counts = ((Invoke-StudyGit @('rev-list', '--left-right', '--count', 'HEAD...origin/main') | Out-String).Trim() -split '\s+')
    $status = Invoke-StudyGit @('status', '--porcelain')
    if ($status) { throw 'Uncommitted changes exist. Review and preserve them before synchronization; no stash or overwrite was performed.' }
    if ([int]$counts[0] -gt 0) { throw 'Local unpublished commits exist. Review them before starting a new learning task.' }
    if ([int]$counts[1] -gt 0) {
        Invoke-StudyGit @('log', '--oneline', 'HEAD..origin/main') | Write-Output
        Invoke-StudyGit @('diff', '--stat', 'HEAD..origin/main') | Write-Output
        Invoke-StudyGit @('merge', '--ff-only', 'origin/main') | Write-Output
    }
    Write-Output 'Repository is current. Read the changed learning records before planning.'
    return
}

# Only explicitly selected study/pipeline files may be committed.
$allowed = @('helpstudy', 'AGENTS.md', 'tools/sync-study.ps1')
foreach ($path in $Paths) {
    if ($path -notin $allowed) { throw "Path is outside learning sync scope: $path" }
}
$alreadyStaged = Invoke-StudyGit @('diff', '--cached', '--name-only')
if ($alreadyStaged) { throw 'Existing staged changes were preserved. Review them before the learning commit.' }
$changed = @()
$changed += @(Invoke-StudyGit @('-c', 'core.quotepath=false', 'diff', '--name-only', 'HEAD'))
$changed += @(Invoke-StudyGit @('-c', 'core.quotepath=false', 'ls-files', '--others', '--exclude-standard'))
foreach ($file in $changed) {
    $selected = $false
    foreach ($path in $Paths) {
        if ($file -eq $path -or $file.StartsWith("$path/", [StringComparison]::Ordinal)) { $selected = $true }
    }
    if (-not $selected) { throw "Unrelated changes were preserved; commit them separately first: $file" }
}
if (-not $changed) { Write-Output 'No file changes to publish.'; return }
Invoke-StudyGit (@('add', '--') + $Paths) | Write-Output
Invoke-StudyGit @('diff', '--cached', '--stat') | Write-Output
Invoke-StudyGit @('commit', '-m', $Message) | Write-Output

# Another device may have published while this task was running.
for ($attempt = 1; $attempt -le 3; $attempt++) {
    Invoke-StudyGit @('fetch', 'origin') | Write-Output
    $behind = [int]((Invoke-StudyGit @('rev-list', '--count', 'HEAD..origin/main') | Out-String).Trim())
    if ($behind -gt 0) {
        & git -C $repoRoot rebase origin/main 2>&1 | Write-Output
        if ($LASTEXITCODE -ne 0) {
            Invoke-StudyGit @('rebase', '--abort') | Write-Output
            throw 'Concurrent edits conflict. Rebase was aborted; the local learning commit is preserved and was not pushed.'
        }
    }
    & git -C $repoRoot push origin HEAD:main 2>&1 | Write-Output
    if ($LASTEXITCODE -eq 0) {
        Write-Output 'Learning records were published to GitHub.'
        Invoke-StudyGit @('rev-parse', 'HEAD') | Write-Output
        return
    }
}
throw 'Push failed after three attempts. The local commit is preserved; report the failure instead of claiming synchronization.'
