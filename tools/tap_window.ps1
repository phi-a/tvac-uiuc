# Click at client-area coordinates inside a window (e.g. tap the HMI via a VNC viewer),
# optionally hold the button, then screenshot the window afterwards.
#   powershell -ExecutionPolicy Bypass -File tools\tap_window.ps1 -X 178 -Y 300 -Out after.png
#   powershell -ExecutionPolicy Bypass -File tools\tap_window.ps1 -X 780 -Y 15 -HoldMs 2500 -Out uniapps.png
param(
    [string]$Process = "vncviewer64",
    [Parameter(Mandatory)][int]$X,
    [Parameter(Mandatory)][int]$Y,
    [int]$HoldMs = 120,
    [int]$SettleMs = 1500,
    [string]$Out = ""
)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinTap {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, int dx, int dy, uint data, UIntPtr extra);
}
"@
$p = Get-Process $Process -ErrorAction Stop | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { throw "no window for process $Process - refusing to click" }
[void][WinTap]::ShowWindow($p.MainWindowHandle, 9)
[void][WinTap]::SetForegroundWindow($p.MainWindowHandle)
Start-Sleep -Milliseconds 500
# Validate the client area BEFORE clicking, so a bad handle never sends a click to the desktop.
$r = New-Object WinTap+RECT
[void][WinTap]::GetClientRect($p.MainWindowHandle, [ref]$r)
$w = $r.R - $r.L; $h = $r.B - $r.T
if ($w -le 0 -or $h -le 0) { throw "window '$($p.MainWindowTitle)' has no client area ($w x $h) - refusing to click" }
if ($X -lt 0 -or $Y -lt 0 -or $X -ge $w -or $Y -ge $h) { throw "($X,$Y) is outside the ${w}x${h} client area - refusing to click" }
$pt = New-Object WinTap+POINT
[void][WinTap]::ClientToScreen($p.MainWindowHandle, [ref]$pt)
$sx = $pt.X + $X; $sy = $pt.Y + $Y
[void][WinTap]::SetCursorPos($sx, $sy)
Start-Sleep -Milliseconds 150
[WinTap]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)   # left down
Start-Sleep -Milliseconds $HoldMs
[WinTap]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)   # left up
Write-Output "tapped client ($X,$Y) = screen ($sx,$sy), held $HoldMs ms"
Start-Sleep -Milliseconds $SettleMs
if ($Out -ne "") {
    & "$PSScriptRoot\shot_window.ps1" -Process $Process -Out $Out
}
