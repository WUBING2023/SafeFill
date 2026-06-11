<#
.SYNOPSIS
    SafeFill MinerU 安装脚本
.DESCRIPTION
    安装 MinerU 到独立虚拟环境 D:\SafeFill\.venv_mineru\
    不会影响 SafeFill 主 Python 环境。
    安装过程会联网下载包，请确认网络连接。
.NOTES
    必须由用户手动运行，SafeFill 不会自动调用此脚本。
#>

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  SafeFill MinerU 安装脚本" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [WARN] 此脚本会联网下载 MinerU 及相关依赖。" -ForegroundColor Yellow
Write-Host "  [WARN] 安装位置: D:\SafeFill\.venv_mineru\" -ForegroundColor Yellow
Write-Host "  [WARN] 不会影响 SafeFill 主 Python 环境。" -ForegroundColor Yellow
Write-Host "  [WARN] 安装过程可能需要几分钟。" -ForegroundColor Yellow
Write-Host ""
Write-Host "  如需继续，请输入 INSTALL 后按回车。" -ForegroundColor White
Write-Host "  如需取消，直接按回车或输入其他内容。" -ForegroundColor White
Write-Host ""

$confirm = Read-Host "  >"
if ($confirm -ne "INSTALL") {
    Write-Host ""
    Write-Host "  已取消安装。" -ForegroundColor Gray
    Write-Host ""
    exit 0
}

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\SafeFill"
$VenvDir = "$ProjectRoot\.venv_mineru"
$PythonExe = "$VenvDir\Scripts\python.exe"
$MinerUExe = "$VenvDir\Scripts\mineru.exe"

Write-Host ""
Write-Host "  [1/5] 创建虚拟环境..." -ForegroundColor Cyan
if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
    Write-Host "  [OK] $VenvDir" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] $VenvDir 已存在" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  [2/5] 升级 pip..." -ForegroundColor Cyan
& $PythonExe -m pip install --upgrade pip --quiet
Write-Host "  [OK] pip 已升级" -ForegroundColor Green

Write-Host ""
Write-Host "  [3/5] 安装 uv (加速包安装)..." -ForegroundColor Cyan
& $PythonExe -m pip install uv --quiet
Write-Host "  [OK] uv 已安装" -ForegroundColor Green

Write-Host ""
Write-Host "  [4/5] 安装 MinerU (mineru[all])..." -ForegroundColor Cyan
Write-Host "  这可能需要几分钟，请耐心等待..." -ForegroundColor Yellow
& $PythonExe -m uv pip install -U "mineru[all]"
Write-Host "  [OK] MinerU 包安装完成" -ForegroundColor Green

Write-Host ""
Write-Host "  [5/5] 验证安装..." -ForegroundColor Cyan

$mineruPath = ""
$mineruVersion = ""

# Try mineru.exe first
if (Test-Path $MinerUExe) {
    $mineruPath = $MinerUExe
    try {
        $mineruVersion = & $MinerUExe --version 2>&1 | Select-Object -First 1
    } catch {
        $mineruVersion = "(version check failed)"
    }
} else {
    # Try python -m mineru
    try {
        $testOutput = & $PythonExe -m mineru --version 2>&1 | Select-Object -First 1
        $mineruPath = "$PythonExe -m mineru"
        $mineruVersion = $testOutput
    } catch {
        $mineruVersion = ""
    }
}

if ($mineruVersion) {
    Write-Host "  [OK] MinerU 安装成功!" -ForegroundColor Green
    Write-Host "  路径: $mineruPath" -ForegroundColor Green
    Write-Host "  版本: $mineruVersion" -ForegroundColor Green
    Write-Host ""
    Write-Host "  MinerU 已就绪，PDF 旧资料提取功能可用。" -ForegroundColor Green
    Write-Host "  运行 python D:\SafeFill\app\pdf_extract.py 测试 PDF 提取。" -ForegroundColor White
} else {
    Write-Host "  [FAIL] MinerU 安装验证失败。" -ForegroundColor Red
    Write-Host "  请尝试手动安装:" -ForegroundColor Yellow
    Write-Host "    pip install -U mineru[all]" -ForegroundColor Yellow
    Write-Host "  或参考: https://github.com/opendatalab/MinerU" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  安装完成" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
