@echo off
setlocal
title Sustainability Document Hub - file inventory
echo.
echo  Sustainability Document Hub - file inventory
echo  ===========================================
echo.
set "HUBLIB=%~1"
if not defined HUBLIB set "HUBLIB=%~dp0"
set "HUBOUT=%~dp0"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=powershell.exe"
echo  Looking near : %HUBLIB%
echo  Writing to   : %HUBOUT%files_present.csv
echo  PowerShell   : %PS%
echo.
"%PS%" -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Continue'; $start=$env:HUBLIB; if(-not $start){$start=$PWD.Path}; $dir=$start; $libs=@(); for($i=0;$i -lt 6 -and $dir;$i++){$hits=@(Get-ChildItem -LiteralPath $dir -Directory -ErrorAction SilentlyContinue | Where-Object {$_.Name -match '^Docs[0-9]*$'}); if($hits.Count -gt 0){$libs=$hits; break}; $p=Split-Path -Parent $dir; if($p -eq $dir){break}; $dir=$p}; if($libs.Count -eq 0){Write-Host 'Could not find the Docs folders automatically.' -ForegroundColor Yellow; Write-Host 'Paste the full path to the folder that CONTAINS Docs and Docs2, then press Enter.'; $t=(Read-Host 'Path').Trim().Trim([char]34).Trim(); if($t -and (Test-Path -LiteralPath $t)){$libs=@(Get-ChildItem -LiteralPath $t -Directory | Where-Object {$_.Name -match '^Docs[0-9]*$'})} else {Write-Host 'That path does not exist.' -ForegroundColor Red}}; if($libs.Count -eq 0){Write-Host 'No library folders found. Nothing was written.' -ForegroundColor Red; return}; Write-Host ('Found: ' + (($libs | ForEach-Object {$_.Name}) -join ', ')) -ForegroundColor Cyan; $rows=New-Object System.Collections.ArrayList; foreach($d in $libs){$b=$d.FullName.TrimEnd([char]92); Write-Host ('Scanning ' + $d.Name + ' ...'); Get-ChildItem -LiteralPath $b -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object {$_.FullName -notmatch '[\\/]\.git[\\/]' -and $_.Name -ne '.nojekyll'} | ForEach-Object {[void]$rows.Add([pscustomobject]@{repo=$d.Name; path=$_.FullName.Substring($b.Length+1).Replace([char]92,'/'); bytes=$_.Length})}}; if($rows.Count -eq 0){Write-Host 'Folders found but no files in them.' -ForegroundColor Red; return}; $outdir=$env:HUBOUT; if(-not $outdir){$outdir=$PWD.Path}; $out=Join-Path $outdir 'files_present.csv'; $rows | Sort-Object repo,path | Export-Csv -LiteralPath $out -NoTypeInformation -Encoding UTF8; Write-Host ''; Write-Host 'Per repository' -ForegroundColor Cyan; foreach($g in ($rows | Group-Object repo | Sort-Object Name)){$s=($g.Group | Measure-Object bytes -Sum).Sum; $pdf=@($g.Group | Where-Object {$_.path -like '*.pdf'}).Count; Write-Host ('  {0,-8} {1,5} files  {2,4} pdf  {3,9:N1} MB' -f $g.Name,$g.Count,$pdf,($s/1MB))}; $tb=($rows | Measure-Object bytes -Sum).Sum; Write-Host ('  {0,-8} {1,5} files            {2,9:N1} MB' -f 'TOTAL',$rows.Count,($tb/1MB)); Write-Host ''; Write-Host 'Size bands' -ForegroundColor Cyan; foreach($bk in @(@(50MB,[double]::MaxValue,'over 50 MB'),@(20MB,50MB,'20 to 50 MB'),@(10MB,20MB,'10 to 20 MB'),@(5MB,10MB,'5 to 10 MB'),@(1MB,5MB,'1 to 5 MB'),@(0,1MB,'under 1 MB'))){$set=@($rows | Where-Object {$_.bytes -ge $bk[0] -and $_.bytes -lt $bk[1]}); if($set.Count -gt 0){$s=($set | Measure-Object bytes -Sum).Sum; Write-Host ('  {0,-13} {1,5} files  {2,9:N1} MB' -f $bk[2],$set.Count,($s/1MB))}}; Write-Host ''; Write-Host 'Twenty largest files' -ForegroundColor Cyan; $rows | Sort-Object bytes -Descending | Select-Object -First 20 | ForEach-Object {Write-Host ('  {0,7:N1} MB  {1}' -f ($_.bytes/1MB), $_.path)}; Write-Host ''; Write-Host ('Wrote ' + $rows.Count + ' rows to:') -ForegroundColor Green; Write-Host ('  ' + $out) -ForegroundColor Green"
echo.
echo  ------------------------------------------------------------
echo   PowerShell finished with exit code %ERRORLEVEL%
echo   Read the messages above. This window will not close itself.
echo  ------------------------------------------------------------
echo.
pause
endlocal
