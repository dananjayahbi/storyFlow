# Copy the ready-made Qwen3-TTS GPU environment into StoryFlow.
#
# Django runs on Python 3.14, but `qwen-tts` only supports Python 3.10-3.12.
# The GPU engine therefore lives in its own virtualenv and is launched as a
# child process by backend/core_engine/qwen_tts.py.
#
# This script copies the experiment venv from E:\test_repos\TTS-test instead
# of re-downloading ~5 GB of torch + CUDA wheels.  The copy is relocatable as
# long as the base interpreter recorded in pyvenv.cfg still exists.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_qwen_tts.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\setup_qwen_tts.ps1 -Force
#
param(
    [string]$Source = "E:\test_repos\TTS-test\.venv",
    [string]$Target = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Target) {
    $Target = Join-Path $repoRoot "backend\qwen_tts\.venv"
}

Write-Host "Source : $Source"
Write-Host "Target : $Target"

$sourcePython = Join-Path $Source "Scripts\python.exe"
if (-not (Test-Path $sourcePython)) {
    throw "Source venv not found at '$sourcePython'. Pass -Source <path-to-venv>."
}

if (Test-Path $Target) {
    if (-not $Force) {
        Write-Host "Target already exists - verifying it instead of copying."
        Write-Host "Use -Force to replace it."
    } else {
        Write-Host "Removing existing target ..."
        Remove-Item -Recurse -Force $Target
    }
}

if (-not (Test-Path $Target)) {
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    Write-Host "Copying virtualenv (~5 GB, this can take a few minutes) ..."
    # /E copy subdirs, /NFL /NDL quiet file/dir lists, /NJH /NJS quiet header,
    # /R:1 /W:1 one retry, /MT parallel copy.
    robocopy $Source $Target /E /NFL /NDL /NJH /NJS /NP /R:1 /W:1 /MT:8 | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed with exit code $LASTEXITCODE"
    }
    Write-Host "Copy complete."
}

$targetPython = Join-Path $Target "Scripts\python.exe"
Write-Host "Verifying torch + qwen_tts + CUDA ..."
& $targetPython -c @"
import json, sys
import torch, qwen_tts
print(json.dumps({
    'python': sys.version.split()[0],
    'torch': torch.__version__,
    'cuda': bool(torch.cuda.is_available()),
    'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
}))
"@
if ($LASTEXITCODE -ne 0) {
    throw "Verification failed. The copied venv cannot import torch/qwen_tts."
}

Write-Host ""
Write-Host "Done. Restart the backend, then open Settings -> TTS Engine."
Write-Host "If CUDA shows False, install the CUDA build of torch into $Target."
