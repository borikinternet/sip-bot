param(
    [string]$Distro = "Debian-Bookworm-FS",
    [string]$MicroSipRoot = "$env:LOCALAPPDATA\Programs\MicroSIP-Workshop"
)

$ErrorActionPreference = "Stop"

$templatePath = Join-Path $PSScriptRoot "..\..\config\workshops\freeswitch\microsip\MicroSIP.ini.template"
$templatePath = (Resolve-Path -LiteralPath $templatePath).Path

$pbxHost = (& wsl.exe -d $Distro -- hostname -I) -replace "`0", ""
$pbxHost = ($pbxHost -split "\s+" | Where-Object { $_ -match "^\d+\.\d+\.\d+\.\d+$" } | Select-Object -First 1)
if (-not $pbxHost) {
    throw "Could not determine the IPv4 address of WSL distro '$Distro'."
}

$profiles = @(
    @{
        Directory = "Caller-1000"
        Extension = "1000"
        DisplayName = "Workshop caller 1000"
        InstanceId = "freeswitch-workshop-caller-1000"
        SourcePort = "5062"
        RtpPortMin = "40000"
        RtpPortMax = "40100"
    },
    @{
        Directory = "Agent-1001"
        Extension = "1001"
        DisplayName = "Workshop agent 1001"
        InstanceId = "freeswitch-workshop-agent-1001"
        SourcePort = "5064"
        RtpPortMin = "40200"
        RtpPortMax = "40300"
    }
)

$template = Get-Content -LiteralPath $templatePath -Raw
foreach ($profile in $profiles) {
    $directory = Join-Path $MicroSipRoot $profile.Directory
    $executable = Join-Path $directory "MicroSIP.exe"
    if (-not (Test-Path -LiteralPath $executable)) {
        throw "MicroSIP executable is missing: $executable"
    }

    Get-Process MicroSIP -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $executable } |
        Stop-Process -Force

    $content = $template
    $content = $content.Replace("@PBX_HOST@", $pbxHost)
    $content = $content.Replace("@EXTENSION@", $profile.Extension)
    $content = $content.Replace("@DISPLAY_NAME@", $profile.DisplayName)
    $content = $content.Replace("@INSTANCE_ID@", $profile.InstanceId)
    $content = $content.Replace("@SOURCE_PORT@", $profile.SourcePort)
    $content = $content.Replace("@RTP_PORT_MIN@", $profile.RtpPortMin)
    $content = $content.Replace("@RTP_PORT_MAX@", $profile.RtpPortMax)

    $iniPath = Join-Path $directory "MicroSIP.ini"
    [System.IO.File]::WriteAllText($iniPath, $content, [System.Text.UTF8Encoding]::new($false))
    Write-Output "$($profile.Extension): $iniPath -> $pbxHost"
}
