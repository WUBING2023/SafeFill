# SafeFill Word 文本框支持

> **状态：已完成** ✅
>
> 完成范围：旧资料文本框提取 → 空白表文本框识别 → 简单文本框写入 → ReviewUI 文本框状态展示 → FinalExport 流程验证通过

## 概述

SafeFill 通过直接解析 docx 内部 XML（`word/document.xml`），支持从 Word **文本框 / 形状**中提取信息、识别结构、写入简单文本框。

很多简历模板和申报表使用文本框存放内容，此前 python-docx 无法处理。现在无需额外依赖即可支持。

## 第 1 步：ProfileExtract — 从旧资料文本框提取文字 ✅

运行 `extract_candidates.py` 时自动检测旧资料中的文本框，提取其中文字用于个人信息候选。

日志：`[LOG] INFO: 检测到 2 个 Word 文本框`
来源标注：`文本框 1`、`文本框 2`

## 第 2 步：FormReview — 识别空白表文本框结构 ✅

运行 `form_review.py` 时自动检测空白表中的文本框，将其加入 `form_structure` 交给 API-first 填表计划。

报告中标注：`检测到 N 个文本框，当前仅识别结构暂不自动写入，请人工检查`

## 第 3 步：FormReview — 写入简单文本框 ✅

API-first 填表计划支持写入**简单文本框**（空文本框或仅含标签的文本框）。

### 写入规则

| 条件 | 行为 |
|------|------|
| 文本框为空 | ✅ 写入 |
| 文本框仅含标签（如 `个人简介：`） | ✅ 覆盖写入 |
| 文本框仅含标签+占位符（如 `个人简介：____`） | ✅ 覆盖写入 |
| 文本框已有真实长内容 | ❌ 跳过，不覆盖 |
| 文本框内容不是目标 label | ❌ 跳过 |

### API fill_plan 格式

```json
{
  "target": {"type": "docx_textbox", "textbox_index": 1},
  "field_label": "个人简介",
  "field_key": "biography",
  "value": "..."
}
```

写入后报告标注 `Textbox[N]`。

## 支持范围

| 文本框类型 | XML 节点 | 提取 | 识别结构 | 写入 |
|-----------|----------|:---:|:---:|:---:|
| 标准 Word 文本框 | `w:txbxContent` | ✅ | ✅ | ✅ |
| VML 文本框（旧版） | `v:textbox` | ✅ | ✅ | ✅ |
| WordProcessingShape | `wps:txbx` | ✅ | ✅ | ✅ |

## 第 4 步：ReviewUI — 展示文本框字段状态 ✅

ReviewUI 检查页面会显示"Word 文本框字段"区域：
- 已写入的文本框显示绿色标记
- 需检查的文本框显示黄色标记
- 网页不还原 Word 文本框真实版面，请打开草稿 Word 文件复核

## 限制

| 项目 | 说明 |
|------|------|
| 从文本框提取文字 | ✅ |
| 识别文本框结构 | ✅ |
| 写入简单文本框 | ✅ 空/仅标签的文本框 |
| 写入已有内容的文本框 | ❌ 禁止覆盖 |
| 复杂文本框排版还原 | ❌ 暂不支持 |
| 图片中的文字 | ❌ 需 OCR / MinerU |
| 原始文件修改 | 否，只修改草稿副本 |

## 技术实现

- `extract_docx_textboxes()` — `app\extract_candidates.py`
- `extract_docx_textbox_structure()` — `app\fill_form_draft.py`
- `write_docx_textbox()` — `app\fill_form_draft.py`
- 通过 `zipfile` + `xml.etree.ElementTree` 解析，无需额外依赖
