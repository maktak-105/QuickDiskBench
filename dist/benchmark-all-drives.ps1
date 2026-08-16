[CmdletBinding()]
param(
    [int]$SizeMiB = 256,
    [ValidateRange(1,9)][int]$Passes = 1,
    [switch]$Raw,
    [string]$OutputDirectory = '.\\results'
)

$ErrorActionPreference = 'Stop'
$exe = Join-Path (Get-Location) 'QuickDiskBench_cli.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "QuickDiskBench_cli.exe not found: $exe" }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$all = [System.Collections.Generic.List[object]]::new()

# 固定ボリュームを列挙。USB等も固定ディスクとして公開されていれば対象になる。
$volumes = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name.Length -eq 1 } | Sort-Object Name
if (-not $volumes) { $root=(Get-Location).Path.Substring(0,1)+[char]92; $volumes=@([pscustomobject]@{Name=$root.Substring(0,1);Root=$root}) }

foreach ($v in $volumes) {
    $drive = $v.Root
    $safe = $v.Name
    $csv = Join-Path ([IO.Path]::GetTempPath()) ("QuickDiskBench-{0}-{1}.csv" -f $safe, $stamp)
    $kind = 'Fixed volume'
    Write-Host "Starting $drive"
    $args = @('--drive', $drive, '--size', $SizeMiB, '--passes', $Passes, '--csv', $csv)
    if ($Raw) { $args += '--raw' }
    & $exe @args
    if ($LASTEXITCODE -ne 0) { Write-Warning "Benchmark failed for $drive"; continue }
    if (Test-Path -LiteralPath $csv) {
        Import-Csv -LiteralPath $csv | ForEach-Object {
            $_ | Add-Member NoteProperty Drive $drive -Force
            $_ | Add-Member NoteProperty Device $kind -Force
            $all.Add($_)
        }
        Remove-Item -LiteralPath $csv -Force -ErrorAction SilentlyContinue
    }
}

$summary = Join-Path $OutputDirectory "summary-$stamp.csv"
$all | Select-Object Drive,Device,test,mean_mbs,stddev_mbs,mean_iops | Export-Csv -LiteralPath $summary -NoTypeInformation -Encoding UTF8
Write-Host "Completed: $summary"
