<#
.SYNOPSIS
  Find the HVC-3500 controller's IP on a directly connected Ethernet adapter.

.DESCRIPTION
  Run in an ELEVATED PowerShell (right-click -> Run as administrator). Uses the
  built-in pktmon capture driver to record every frame arriving on the chosen
  adapter for a few seconds and prints the source MAC / IP / protocol of each
  distinct sender, so you learn which subnet the controller is on without
  touching its settings. Optionally adds a temporary secondary IPv4 address on
  that adapter so the probe can reach it.

.EXAMPLE
  # Windows blocks unsigned .ps1 files by default; bypass for this process only:
  powershell -ExecutionPolicy Bypass -File C:\Users\darkn\Documents\tvac\tools\find_hvc.ps1 -Adapter "Ethernet 3"
  powershell -ExecutionPolicy Bypass -File C:\Users\darkn\Documents\tvac\tools\find_hvc.ps1 -Adapter "Ethernet 3" -AddAddress 172.16.21.50 -PrefixLength 24
#>
param(
    [string]$Adapter = "Ethernet 3",
    [int]$Seconds = 15,
    [string]$AddAddress = "",
    [int]$PrefixLength = 24
)

$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run this script from an elevated (Administrator) PowerShell."
    exit 1
}

$nic = Get-NetAdapter -Name $Adapter -ErrorAction Stop
Write-Host ("Adapter {0}: {1}, {2}, MAC {3}, driver '{4}'" -f $nic.Name, $nic.Status, $nic.LinkSpeed, $nic.MacAddress, $nic.InterfaceDescription)
$myMac = ($nic.MacAddress -replace ':', '-').ToUpper()

# pktmon addresses adapters by its own component id, not the Windows ifIndex.
$comp = $null
pktmon list | ForEach-Object {
    if ($_ -match '^\s*(\d+)\s+\S+\s+(.+?)\s*$' -and $Matches[2] -eq $nic.InterfaceDescription) { $comp = [int]$Matches[1] }
}
if ($null -eq $comp) {
    Write-Warning "Could not map '$($nic.InterfaceDescription)' to a pktmon component; capturing on all adapters."
    $compArg = @()
} else {
    Write-Host "pktmon component id: $comp"
    $compArg = @('--comp', $comp)
}

$etl = Join-Path $env:TEMP "find_hvc.etl"
$txt = "$etl.txt"
Remove-Item $etl, $txt -ErrorAction SilentlyContinue
pktmon stop 2>$null | Out-Null
pktmon filter remove 2>$null | Out-Null
& pktmon start --capture @compArg --pkt-size 128 -f $etl | Out-Null
Write-Host "Capturing all frames on '$Adapter' for $Seconds s ..."
Start-Sleep -Seconds $Seconds
pktmon stop | Out-Null
pktmon format $etl -o $txt | Out-Null

# Decoded frame lines look like:
#   00-0D-22-19-7B-B8 > FF-FF-FF-FF-FF-FF, ethertype ARP (0x0806), length 60: Request who-has 172.16.21.1 tell 172.16.21.74, length 46
#   00-0D-22-19-7B-B8 > 01-00-5E-..., ethertype IPv4 (0x0800), length 90: 172.16.21.74.1234 > 239.255.255.250.1900: UDP, length 48
$senders = @{}
Get-Content $txt | ForEach-Object {
    $line = $_
    if ($line -match '([0-9A-F]{2}(?:-[0-9A-F]{2}){5}) > ([0-9A-F]{2}(?:-[0-9A-F]{2}){5}), ethertype ([A-Za-z0-9]+)') {
        $src = $Matches[1].ToUpper(); $dst = $Matches[2].ToUpper(); $type = $Matches[3]
        if ($src -eq $myMac) { return }          # ignore our own transmissions
        $ips = [regex]::Matches($line, '\b(\d{1,3}\.){3}\d{1,3}\b') | ForEach-Object { $_.Value } | Select-Object -Unique
        $detail = ($line -split 'length \d+: ', 2)[1]
        if ($null -eq $detail) { $detail = '' }
        $key = "$src  $type  ips=[$($ips -join ' ')]  $($detail.Substring(0, [Math]::Min(70, $detail.Length)))"
        if (-not $senders.ContainsKey($key)) { $senders[$key] = 0 }
        $senders[$key]++
    }
}

if ($senders.Count -eq 0) {
    Write-Host "No frames from other devices were decoded. Raw text is at $txt"
} else {
    Write-Host "Frames from other devices (count | source MAC | ethertype | IPs seen | detail):"
    $senders.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object {
        Write-Host ("  {0,5}  {1}" -f $_.Value, $_.Key)
    }
    Write-Host "A Unitronics controller has an OUI of 00-0D-22 (older units) or 00-1F-D4/others; an ARP 'tell X' or an IPv4 source gives its address."
}

if ($AddAddress -ne "") {
    Write-Host "Adding temporary address $AddAddress/$PrefixLength to '$Adapter' (remove later with Remove-NetIPAddress)"
    New-NetIPAddress -InterfaceAlias $Adapter -IPAddress $AddAddress -PrefixLength $PrefixLength -ErrorAction Stop | Out-Null
    Write-Host "Done. Now run:  python -m hvc3500 discover --subnet <first three octets> --port <CPU TCP port>"
}
