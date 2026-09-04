[CmdletBinding()]
param(
    [string]$RuntimePath = '/home/sipbot/.local/cpython-3.14.7t/bin/python3.14t',
    [string]$ProbePath = '/mnt/c/devel/sip-bot/tools/nogil_probe.py'
)

$ErrorActionPreference = 'Stop'

wsl.exe -d Ubuntu-24.04 -u sipbot -- bash -lc "$RuntimePath -I $ProbePath"
exit $LASTEXITCODE
