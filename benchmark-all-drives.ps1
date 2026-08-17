[CmdletBinding()]
param(
    [int]$SizeMiB = 256,
    [ValidateRange(1,9)][int]$Passes = 1,
    [ValidateRange(1,3600)][int]$TimeoutSec = 60,
    [switch]$Raw,
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'results')
)

$ErrorActionPreference = 'Stop'
$exe = Join-Path $PSScriptRoot 'QuickDiskBench_cli.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "QuickDiskBench_cli.exe が見つかりません: $exe" }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$all = [System.Collections.Generic.List[object]]::new()

# 固定ボリュームを列挙。USB等も固定ディスクとして公開されていれば対象になる。
$volumes = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Sort-Object DeviceID
if (-not $volumes) { throw '測定可能な固定ボリュームが見つかりません。' }

foreach ($v in $volumes) {
    $drive = $v.DeviceID + [char]92
    $safe = $v.DeviceID.Replace(':','')
    $base = Join-Path $OutputDirectory ("{0}-{1}" -f $safe, $stamp)
    $log = "$base.log"
    $csv = "$base.csv"
    $kind = '固定ボリューム'
    Write-Host "測定開始: $drive ($kind)"
    $args = @('--drive', $drive, '--size', $SizeMiB, '--passes', $Passes, '--timeout', $TimeoutSec, '--csv', $csv)
    if ($Raw) { $args += '--raw' }
    & $exe @args 2>&1 | Tee-Object -FilePath $log
    if ($LASTEXITCODE -ne 0) { Write-Warning "$drive の測定に失敗しました。ログ: $log"; continue }
    if (Test-Path -LiteralPath $csv) {
        Import-Csv -LiteralPath $csv | ForEach-Object {
            $_ | Add-Member NoteProperty Drive $drive -Force
            $_ | Add-Member NoteProperty Device $kind -Force
            $all.Add($_)
        }
    }
}

$summary = Join-Path $OutputDirectory "summary-$stamp.csv"
$all | Select-Object Drive,Device,test,mean_mbs,stddev_mbs,mean_iops | Export-Csv -LiteralPath $summary -NoTypeInformation -Encoding UTF8
Write-Host "完了: $summary"
