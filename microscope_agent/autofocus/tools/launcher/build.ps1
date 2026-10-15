# Build "DINO Autofocus.exe" with the .NET Framework compiler in Windows (no SDK needed).
#   powershell -ExecutionPolicy Bypass -File tools\launcher\build.ps1 [-Port 8765] [-Out path] [-Force]
# The repo path compiled into the exe is the clone this script runs from. The default output
# is the Desktop; an existing exe there is replaced only with -Force, which first copies it to
# "<name>.prev.exe" (or "<name>.prev.<stamp>.exe" if that exists). Paths are literal: [ and ] in
# -Out are file-name characters, not wildcards. See docs\runbooks\launcher.md.
param(
    [int]$Port = 8765,
    [string]$Out = (Join-Path ([Environment]::GetFolderPath("Desktop")) "DINO Autofocus.exe"),
    [switch]$Force
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path -LiteralPath (Join-Path $here "..\..")).Path
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$ico = Join-Path $here "autofocus.ico"
# absolute (csc resolves relative paths against the process directory) and with its folder present
$Out = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out)
$outDir = Split-Path -Parent $Out
if (-not (Test-Path -LiteralPath $outDir)) { [IO.Directory]::CreateDirectory($outDir) | Out-Null }
if (Test-Path -LiteralPath $Out) {
    $old = Get-Item -LiteralPath $Out
    if (-not $Force) {
        Write-Output "exists: $Out ($($old.Length) bytes, $($old.LastWriteTime)); add -Force to replace it"
        exit 1
    }
    # keep the replaced exe next to it; never overwrite an earlier copy
    $base = Join-Path $outDir ([IO.Path]::GetFileNameWithoutExtension($Out))
    $prev = "$base.prev.exe"
    if (Test-Path -LiteralPath $prev) {
        $prev = "$base.prev.$(Get-Date -Format 'yyyyMMdd-HHmmss').exe"
        $n = 2
        while (Test-Path -LiteralPath $prev) {
            $prev = "$base.prev.$(Get-Date -Format 'yyyyMMdd-HHmmss')_$n.exe"; $n++
        }
    }
    Copy-Item -LiteralPath $Out -Destination $prev
    Write-Output "replacing: $Out ($($old.Length) bytes, $($old.LastWriteTime))"
    Write-Output "kept the old exe as: $prev"
}
if (-not (Test-Path -LiteralPath $ico)) {
    Push-Location -LiteralPath $repo
    try { uv run python (Join-Path $here "make_icon.py") } finally { Pop-Location }
}
$src = Join-Path $env:TEMP "DinoAutofocusLauncher.cs"
(Get-Content -LiteralPath (Join-Path $here "Launcher.cs") -Raw -Encoding UTF8) `
    -replace 'const string Repo = @"[^"]*";', ('const string Repo = @"' + $repo + '";') `
    -replace 'const int Port = \d+;', ('const int Port = ' + $Port + ';') |
    Set-Content -LiteralPath $src -Encoding UTF8
& $csc /nologo /target:winexe /optimize+ /win32icon:"$ico" `
    /r:System.Windows.Forms.dll /r:System.Drawing.dll /out:"$Out" "$src"
if ($LASTEXITCODE -eq 0) { Write-Output "built $Out (repo $repo, port $Port)" } else { exit $LASTEXITCODE }
