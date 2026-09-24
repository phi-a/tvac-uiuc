# Screenshot the client area of a window by process name.
#   powershell -ExecutionPolicy Bypass -File tools\shot_window.ps1 -Process vncviewer64 -Out hmi.png
param(
    [string]$Process = "vncviewer64",
    [string]$Out = "hmi.png"
)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinShot {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
}
"@
$p = Get-Process $Process -ErrorAction Stop | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { throw "no window for process $Process" }
[void][WinShot]::ShowWindow($p.MainWindowHandle, 9)   # SW_RESTORE
[void][WinShot]::SetForegroundWindow($p.MainWindowHandle)
Start-Sleep -Milliseconds 700
$r = New-Object WinShot+RECT
[void][WinShot]::GetClientRect($p.MainWindowHandle, [ref]$r)
$pt = New-Object WinShot+POINT
[void][WinShot]::ClientToScreen($p.MainWindowHandle, [ref]$pt)
$w = $r.R - $r.L; $h = $r.B - $r.T
if ($w -le 0 -or $h -le 0) { throw "window has no client area ($w x $h)" }
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($pt.X, $pt.Y, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "'$($p.MainWindowTitle)' ${w}x${h} -> $Out"
