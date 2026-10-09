# Build the downloadable bundle from the single skill source.
$ErrorActionPreference = 'Stop'
$studySkillSource = Join-Path $PSScriptRoot 'skills\helpstudy'
$studyPackageRoot = Join-Path $PSScriptRoot 'packages'
if (-not (Test-Path -LiteralPath (Join-Path $studySkillSource 'SKILL.md'))) { throw 'Missing SKILL.md' }
New-Item -ItemType Directory -Path $studyPackageRoot -Force | Out-Null
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$studyArchivePath = Join-Path $studyPackageRoot 'helpstudy-skill.zip'
$studyArchiveStream = [IO.File]::Open($studyArchivePath, [IO.FileMode]::Create)
$studyArchive = [IO.Compression.ZipArchive]::new($studyArchiveStream, [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($studySkillFile in Get-ChildItem -LiteralPath $studySkillSource -Recurse -File) {
        $studyRelativePath = [IO.Path]::GetRelativePath($studySkillSource, $studySkillFile.FullName).Replace('\', '/')
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($studyArchive, $studySkillFile.FullName, ('helpstudy/' + $studyRelativePath)) | Out-Null
    }
} finally {
    $studyArchive.Dispose()
    $studyArchiveStream.Dispose()
}
Write-Output $studyArchivePath
