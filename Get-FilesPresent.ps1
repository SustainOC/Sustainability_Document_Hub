<#
    Get-FilesPresent.ps1
    Sustainability Document Hub

    Lists every file in the document library clones so the catalogue can be
    reconciled against what is actually published, and prints the size
    breakdown needed to decide whether the library still needs to be split
    across more than one repository.

    EASIEST WAY TO RUN IT
      Double-click  Run-FilesPresent.cmd  in the repository root.
      That launcher sets the execution policy for the one run and keeps the
      window open so you can read the output.

    If the folders holding your clones are somewhere this script cannot find,
    it will ask you to paste the path. You can also drag that folder onto
    Run-FilesPresent.cmd.

    OUTPUT
      files_present.csv, written next to the launcher. Send that file back.
#>

[CmdletBinding()]
param(
    # Folder that CONTAINS the library clones, e.g. the SharePoint folder
    # holding Docs and Docs2. Leave blank to search automatically.
    [string]   $LibraryPath = "",

    # Names of the clone folders. Leave as-is unless you renamed them.
    [string[]] $Roots = @(),

    [string]   $Out = "files_present.csv"
)

$ErrorActionPreference = "Stop"
$script:exitCode = 0

function Clean-Path([string]$p) {
    if (-not $p) { return "" }
    # Windows "Copy as path" wraps the path in quotes, and pasted paths often
    # carry stray whitespace. Strip both, in either order, repeatedly.
    for ($i = 0; $i -lt 4; $i++) {
        $p = $p.Trim()
        $p = $p.Trim('"')
        $p = $p.Trim("'")
    }
    return $p.TrimEnd('\', '/')
}

function Write-Head($text) {
    Write-Host ""
    Write-Host $text -ForegroundColor Cyan
    Write-Host ("-" * $text.Length) -ForegroundColor DarkCyan
}

try {
    # ---- where am I -----------------------------------------------------
    if ($PSScriptRoot) { $scriptDir = $PSScriptRoot }
    else { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition }
    $repoRoot = Split-Path -Parent $scriptDir      # tools\ -> repo root

    Write-Head "Sustainability Document Hub - file inventory"
    Write-Host ("Script folder : {0}" -f $scriptDir)

    # ---- find the folder holding the clones -----------------------------
    function Find-Libraries([string]$start) {
        $found = @()
        $dir = $start
        for ($i = 0; $i -lt 5 -and $dir; $i++) {
            $hits = @(Get-ChildItem -LiteralPath $dir -Directory -ErrorAction SilentlyContinue |
                      Where-Object { $_.Name -match '^(Docs|Doc)[0-9]*$' -or $_.Name -match '^lib-' })
            if ($hits.Count -gt 0) { $found = $hits; break }
            $parent = Split-Path -Parent $dir
            if ($parent -eq $dir) { break }
            $dir = $parent
        }
        return ,$found
    }

    $libDirs = @()

    if ($LibraryPath) {
        $LibraryPath = Clean-Path $LibraryPath
        if (-not (Test-Path -LiteralPath $LibraryPath)) {
            throw "That path does not exist: $LibraryPath"
        }
        if ($Roots.Count -gt 0) {
            $libDirs = @($Roots | ForEach-Object { Join-Path $LibraryPath $_ } |
                         Where-Object { Test-Path -LiteralPath $_ } |
                         ForEach-Object { Get-Item -LiteralPath $_ })
        } else {
            $libDirs = Find-Libraries $LibraryPath
            if ($libDirs.Count -eq 0) {
                # maybe they pointed straight at a single clone
                $libDirs = @(Get-Item -LiteralPath $LibraryPath)
            }
        }
    } else {
        $libDirs = Find-Libraries $repoRoot
    }

    if ($libDirs.Count -eq 0) {
        Write-Host ""
        Write-Host "Could not find the library clones automatically." -ForegroundColor Yellow
        Write-Host "Paste the full path to the folder that CONTAINS them"
        Write-Host "(the folder you can see Docs and Docs2 inside), then press Enter."
        Write-Host ""
        $typed = Clean-Path (Read-Host "Path")
        if (-not $typed) { throw "No path entered." }
        if (-not (Test-Path -LiteralPath $typed)) { throw "That path does not exist: $typed" }
        $libDirs = Find-Libraries $typed
        if ($libDirs.Count -eq 0) { $libDirs = @(Get-Item -LiteralPath $typed) }
    }

    Write-Host ("Libraries     : {0}" -f (($libDirs | ForEach-Object { $_.Name }) -join ", "))

    # ---- walk them ------------------------------------------------------
    $rows = New-Object System.Collections.Generic.List[object]

    foreach ($dir in $libDirs) {
        $base = $dir.FullName.TrimEnd('\')
        Write-Host ("Scanning {0} ..." -f $dir.Name)
        Get-ChildItem -LiteralPath $base -Recurse -File -Force -ErrorAction SilentlyContinue |
          Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' -and $_.Name -ne '.nojekyll' } |
          ForEach-Object {
              $rel = $_.FullName.Substring($base.Length + 1).Replace('\', '/')
              $rows.Add([pscustomobject]@{
                  repo  = $dir.Name
                  path  = $rel
                  bytes = $_.Length
                  ext   = $_.Extension.ToLower()
              })
          }
    }

    if ($rows.Count -eq 0) { throw "No files found. Check that you pointed at the right folder." }

    # ---- write ----------------------------------------------------------
    $outPath = if ([System.IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path $repoRoot $Out }
    $rows | Sort-Object repo, path |
        Export-Csv -LiteralPath $outPath -NoTypeInformation -Encoding UTF8

    # ---- report ---------------------------------------------------------
    Write-Head "Per repository"
    foreach ($g in ($rows | Group-Object repo | Sort-Object Name)) {
        $sum = ($g.Group | Measure-Object bytes -Sum).Sum
        $pdf = @($g.Group | Where-Object { $_.ext -eq '.pdf' }).Count
        Write-Host ("  {0,-10} {1,5} files  ({2,4} pdf)  {3,8:N1} MB" -f `
                    $g.Name, $g.Count, $pdf, ($sum / 1MB))
    }
    $total = ($rows | Measure-Object bytes -Sum).Sum
    Write-Host ("  {0,-10} {1,5} files                {2,8:N1} MB" -f "TOTAL", $rows.Count, ($total / 1MB))

    Write-Head "Size distribution"
    $buckets = @(
        @{ n = "over 50 MB";   min = 50MB; max = [double]::MaxValue },
        @{ n = "20 to 50 MB";  min = 20MB; max = 50MB },
        @{ n = "10 to 20 MB";  min = 10MB; max = 20MB },
        @{ n = "5 to 10 MB";   min = 5MB;  max = 10MB },
        @{ n = "1 to 5 MB";    min = 1MB;  max = 5MB },
        @{ n = "under 1 MB";   min = 0;    max = 1MB }
    )
    foreach ($b in $buckets) {
        $set = @($rows | Where-Object { $_.bytes -ge $b.min -and $_.bytes -lt $b.max })
        if ($set.Count -eq 0) { continue }
        $sum = ($set | Measure-Object bytes -Sum).Sum
        Write-Host ("  {0,-14} {1,5} files  {2,8:N1} MB" -f $b.n, $set.Count, ($sum / 1MB))
    }

    Write-Head "Twenty largest files"
    $rows | Sort-Object bytes -Descending | Select-Object -First 20 | ForEach-Object {
        Write-Host ("  {0,7:N1} MB  {1}" -f ($_.bytes / 1MB), $_.path)
    }

    Write-Head "Done"
    Write-Host ("Wrote {0} rows to:" -f $rows.Count) -ForegroundColor Green
    Write-Host ("  {0}" -f $outPath) -ForegroundColor Green
    Write-Host ""
    Write-Host "Send that CSV back and the catalogue can be reconciled against it."
}
catch {
    Write-Host ""
    Write-Host "Something went wrong:" -ForegroundColor Red
    Write-Host ("  {0}" -f $_.Exception.Message) -ForegroundColor Red
    Write-Host ""
    Write-Host "Copy the message above and send it over."
    $script:exitCode = 1
}
finally {
    Write-Host ""
    Read-Host "Press Enter to close this window" | Out-Null
}

exit $script:exitCode
