# SafeFill PDF 旧资料提取支持

## 概述

SafeFill v2.0 支持从 `.pdf` 格式的旧资料中提取个人信息。PDF 提取依赖 [MinerU](https://github.com/opendatalab/MinerU)，一个开源的 PDF 解析工具。

## 前提条件

1. 安装 MinerU CLI（用户自行安装，SafeFill 不会自动安装）。
2. MinerU 安装后，`mineru --version` 应可执行。

## 使用方法

### 1. 把 PDF 旧资料放入 input_forms

```
input_forms\
  旧资料1.pdf
  旧资料2.docx
  旧资料3.xlsx
```

### 2. 运行 ProfileExtract

```bash
python D:\SafeFill\app\extract_candidates.py
```

ProfileExtract 会自动：
- 扫描 `input_forms\*.pdf`
- 检查 MinerU 是否可用
- 调用 MinerU 提取 PDF 文本
- 将提取的文本发送给 API 或本地解析

### 3. 手动提取 PDF（可选）

```bash
python D:\SafeFill\app\pdf_extract.py
```

输出目录：`pdf_extract_outputs\`

## 输出结构

```
pdf_extract_outputs\
  旧资料1_pdf_20260610_120000\
    (MinerU 原始输出)
    extracted_text.txt       ← 提取的纯文本（最多 30000 字符）
    extract_meta.json        ← 提取元数据
```

## 限制

| 项目 | 限制 |
|------|------|
| 单 PDF 最大提取 | 30000 字符（超过截断） |
| 仅支持旧资料 | ✅ |
| 支持填写 PDF 空白表 | ❌ 暂不支持 |
| 扫描件 / 图片 PDF | 取决于 MinerU 能力 |
| 原始 PDF 被修改 | 否 |

## 未安装 MinerU 时的行为

- ProfileExtract 不会崩溃。
- 报告中注明：「PDF 未处理：MinerU 未安装」。
- docx/xlsx 流程正常继续。

## 安装 MinerU 参考

请参考 MinerU 官方文档：
https://github.com/opendatalab/MinerU

常见安装方式：

```bash
pip install magic-pdf
```

安装后验证：

```bash
mineru --version
```

## 安全

- PDF 原始二进制 **不会** 发送给 API。
- 只发送提取后的**纯文本**。
- 提取文本仍受 API 安全闸门保护（敏感字段脱敏、用户确认等）。
- `pdf_extract_outputs\` 已加入 `.gitignore`，不会被提交到 Git。
