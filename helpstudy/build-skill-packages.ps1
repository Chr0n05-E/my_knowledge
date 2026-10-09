# Build portable skill/plugin bundles from the canonical skill source.
$ErrorActionPreference = 'Stop'
$studySkillSource = Join-Path $PSScriptRoot 'skills\helpstudy'
$studyPackageRoot = Join-Path $PSScriptRoot 'packages'
New-Item -ItemType Directory -Path $studyPackageRoot -Force | Out-Null
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$studySkillFiles = Get-ChildItem -LiteralPath $studySkillSource -Recurse -File
if (-not (Test-Path -LiteralPath (Join-Path $studySkillSource 'SKILL.md'))) { throw 'Missing SKILL.md' }
$studyPluginSkillRoot = Join-Path $PSScriptRoot 'plugin\skills\helpstudy'
foreach ($studySkillFile in $studySkillFiles) {
    $studyPluginFile = Join-Path $studyPluginSkillRoot ([IO.Path]::GetRelativePath($studySkillSource, $studySkillFile.FullName))
    New-Item -ItemType Directory -Path (Split-Path $studyPluginFile -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $studySkillFile.FullName -Destination $studyPluginFile -Force
}

foreach ($studyBundleKind in @('skill', 'plugin')) {
    $studyArchivePath = Join-Path $studyPackageRoot "helpstudy-$studyBundleKind.zip"
    $studyArchiveStream = [IO.File]::Open($studyArchivePath, [IO.FileMode]::Create)
    $studyArchive = [IO.Compression.ZipArchive]::new($studyArchiveStream, [IO.Compression.ZipArchiveMode]::Create)
    try {
        if ($studyBundleKind -eq 'plugin') {
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($studyArchive, (Join-Path $PSScriptRoot 'plugin\plugin.json'), 'helpstudy/plugin.json') | Out-Null
        }
        foreach ($studySkillFile in $studySkillFiles) {
            $studyRelativePath = [IO.Path]::GetRelativePath($studySkillSource, $studySkillFile.FullName).Replace('\', '/')
            $studyPrefix = if ($studyBundleKind -eq 'plugin') { 'helpstudy/skills/helpstudy/' } else { 'helpstudy/' }
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($studyArchive, $studySkillFile.FullName, ($studyPrefix + $studyRelativePath)) | Out-Null
        }
    } finally {
        $studyArchive.Dispose()
        $studyArchiveStream.Dispose()
    }
    Write-Output $studyArchivePath
}
