<#
.SYNOPSIS
    SafeFill MinerU 状态检查脚本
.DESCRIPTION
    检查 MinerU 是否已安装，显示安装路径和版本。
    检查顺序:
      1. D:\SafeFill\.venv_mineru\Scripts\mineru.exe (SafeFill 独立环境)
      2. 系统 PATH 中的 mineru
#>

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  SafeFill MinerU 状态检查" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = "D:\SafeFill"
$VenvDir = "$ProjectRoot\.venv_mineru"
$MinerUExe = "$VenvDir\Scripts\mineru.exe"
$PythonExe = "$VenvDir\Scripts\python.exe"

$found = $false

# Check 1: SafeFill venv mineru.exe
Write-Host "  [1] 检查 SafeFill 独立环境..." -ForegroundColor White
if (Test-Path $MinerUExe) {
    Write-Host "  [OK] 已安装: $MinerUExe" -ForegroundColor Green
    try {
        $ver = & $MinerUExe --version 2>&1 | Select-Object -First 1
        Write-Host "  版本: $ver" -ForegroundColor Green
    } catch {
        Write-Host "  版本: (无法获取)" -ForegroundColor Yellow
    }
    $found = $true
} elseif (Test-Path $PythonExe) {
    # Try python -m mineru
    try {
        $ver = & $PythonExe -m mineru --version 2>&1 | Select-Object -First 1
        Write-Host "  [OK] 已安装 (via python -m mineru): $PythonExe" -ForegroundColor Green
        Write-Host "  版本: $ver" -ForegroundColor Green
        $found = $true
    } catch {
        Write-Host "  [MISS] .venv_mineru 存在但 mineru 不可用" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [MISS] .venv_mineru 不存在" -ForegroundColor Yellow
}

# Check 2: System PATH
Write-Host ""
Write-Host "  [2] 检查系统 PATH..." -ForegroundColor White
try {
    $sysMineru = Get-Command mineru -ErrorAction Stop
    Write-Host "  [OK] 系统 PATH: $($sysMineru.Source)" -ForegroundColor Green
    try {
        $sysVer = & mineru --version 2>&1 | Select-Object -First 1
        Write-Host "  版本: $sysVer" -ForegroundColor Green
    } catch {
        Write-Host "  版本: (无法获取)" -ForegroundColor Yellow
    }
    $found = $true
} catch {
    Write-Host "  [MISS] 系统 PATH 中未找到 mineru" -ForegroundColor Yellow
}

Write-Host ""
if ($found) {
    Write-Host "  结论: MinerU 已安装，PDF 旧资料提取功能可用。" -ForegroundColor Green
    Write-Host "  运行 python D:\SafeFill\app\pdf_extract.py 测试 PDF 提取。" -ForegroundColor White
} else {
    Write-Host "  结论: MinerU 未安装。" -ForegroundColor Red
    Write-Host "  PDF 旧资料提取将不可用，但 docx/xlsx 流程不受影响。" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  安装 MinerU:" -ForegroundColor White
    Write-Host "    .\tools\install_mineru.ps1" -ForegroundColor White
    Write-Host "  或参考: https://github.com/opendatalab/MinerU" -ForegroundColor White
}
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
