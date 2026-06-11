# SafeFill MinerU 安装说明

## 为什么需要 MinerU

MinerU 是一个开源的 PDF 解析工具。SafeFill 使用它从 PDF 旧资料中提取文本，用于个人信息候选提取。

**不安装 MinerU 不影响 docx/xlsx 流程。**

## 一键安装（推荐）

打开 PowerShell，运行：

```powershell
.\tools\install_mineru.ps1
```

安装过程：
1. 提示确认（输入 `INSTALL` 继续）
2. 创建独立虚拟环境 `.venv_mineru\`（不影响 SafeFill 主环境）
3. 安装 MinerU 及依赖
4. 验证安装

全程约 3-5 分钟，需要联网。

## 安装位置

| 项目 | 路径 |
|------|------|
| 虚拟环境 | `D:\SafeFill\.venv_mineru\` |
| mineru.exe | `D:\SafeFill\.venv_mineru\Scripts\mineru.exe` |
| Python | `D:\SafeFill\.venv_mineru\Scripts\python.exe` |

## 检查安装状态

```powershell
.\tools\check_mineru.ps1
```

或运行：

```powershell
python D:\SafeFill\app\project_guard.py
```

ProjectGuard 会显示 MinerU 状态和路径。

## MinerU 检测优先级

SafeFill 按以下顺序查找 MinerU：

1. 环境变量 `MINERU_EXE`
2. `.venv_mineru\Scripts\mineru.exe`（SafeFill 独立环境）
3. `.venv_mineru\Scripts\python.exe -m mineru`
4. 系统 PATH 中的 `mineru`

## 手动安装

如果不使用安装脚本：

```powershell
# 1. 创建虚拟环境
python -m venv D:\SafeFill\.venv_mineru

# 2. 激活并安装
D:\SafeFill\.venv_mineru\Scripts\Activate.ps1
pip install -U "mineru[all]"

# 3. 验证
mineru --version
```

或使用系统 pip 直接安装：

```powershell
pip install -U "mineru[all]"
```

## 使用 PDF 提取

安装完成后：

```bash
# 单独提取 PDF
python D:\SafeFill\app\pdf_extract.py

# 或直接运行 ProfileExtract（会自动处理 PDF）
python D:\SafeFill\app\extract_candidates.py
```

输出在 `pdf_extract_outputs\`。

## 卸载 MinerU

删除虚拟环境目录即可：

```powershell
Remove-Item -Recurse -Force D:\SafeFill\.venv_mineru
```

不会影响 SafeFill 任何功能（PDF 提取除外）。

## 安全

- MinerU 安装到**独立虚拟环境**，不影响 SafeFill 主环境。
- `install_mineru.ps1` **必须用户手动运行**，输入 `INSTALL` 确认。
- SafeFill **不会自动安装** MinerU。
- SafeFill **不会调用** MinerU Cloud。
- `.venv_mineru\` 已加入 `.gitignore`。
