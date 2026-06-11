---
name: SafeFill-FinalExport
description: "Export reviewed form data to final .docx/.xlsx files, preserving original table formatting"
---

# SafeFill-FinalExport

## Skill 名称

SafeFill-FinalExport — 最终文件导出

## 调用前提示

现在进入最终导出步骤。我会读取网页保存的 review_result，按你确认的内容生成最终 Word/Excel 文件。这一步复制草稿副本后写入，不会直接修改原始表格或草稿文件。

> 只读正式 review_result | 不修改原始表格 | 不修改草稿 | 不修改 vault | 不联网

---

## 主动沟通要求

运行前必须告诉用户：

1. 只会读取用户在网页点击“保存检查结果”后生成的 `review_result_*.json`。
2. 不会读取未确认的 HTML 当作最终结果。
3. 不会修改原始表格、草稿或 vault。

运行后必须主动告诉用户：

1. 最终文件路径。
2. 写入了多少单元格，跳过了多少单元格。
3. 是否发现未填写的复杂字段。
4. 建议用户打开最终文件检查格式。
5. 如果已完成，提醒可选运行 `SafeFill-Cleaner preview` 查看可清理临时隐私文件。

## 适用场景

`review_results\` 中有检查结果，需要根据用户确认、修改、补充的内容导出最终 `.docx` / `.xlsx` 文件。

## 输入

- `D:\SafeFill\review_results\`（`review_result_*.json`，只读）
- `D:\SafeFill\draft_outputs\`（草稿文件，只读）

## 输出

- `D:\SafeFill\final_outputs\` — `*_最终版.docx/.xlsx`
- `D:\SafeFill\final_reports\` — `final_report_*.json/.md`

## 允许调用的脚本

```
python D:\SafeFill\app\export_final.py
```

**只能调用这一个脚本。**

## 运行前检查

1. `review_results\` 中是否有 `review_result_*.json`
2. `review_result` 中 `draft_file` 路径是否在 `draft_outputs\` 内（路径边界校验）
3. 对应草稿文件是否存在
4. `review_result` 中 `security` 字段确认未联网、未调用 API
5. API 默认关闭

## 执行步骤

1. 确认最新的 `review_result_*.json` 存在
2. 确认其中的 `draft_file` 指向 `draft_outputs\` 内的文件
3. 运行 `export_final.py`
4. 确认 `final_outputs\` 中生成最终文件
5. 确认 `final_reports\` 中生成 JSON 和 Markdown 报告
6. 打开 Markdown 报告展示导出摘要

## 成功标准

- 生成最终 `.docx` / `.xlsx` 文件
- 生成 `final_report_*.json` 和 `final_report_*.md`
- Markdown 报告中敏感信息已脱敏
- 报告中明确标注"修改原始文件：否""修改 vault：否"
- 不修改草稿文件
- 不修改 vault

## 失败处理

| 异常情况 | 处理 |
|----------|------|
| `review_results\` 为空 | 停止，提示先完成 SafeFill-FormReview |
| `draft_file` 路径越界 | 拒绝导出，写安全日志 |
| 草稿文件不存在 | 停止，报告缺失文件 |
| 最终文件名冲突 | 自动加时间戳 |

## 禁止事项

- 不得修改原始文件
- 不得修改草稿文件
- 不得修改 vault
- 不得自动保存 `fields_marked_for_profile_save` 到 vault
- 不得处理 PDF
- 不得联网
- 不得调用 API
- 不得安装依赖

## 安全约束

| 约束项 | 值 |
|--------|-----|
| 允许联网 | 否 |
| 允许调用 API | 否 |
| 允许修改 vault | 否 |
| 允许修改原始文件 | 否 |
| 允许修改草稿文件 | 否 |
| 允许安装依赖 | 否 |

## 完成后汇报模板

```
[SafeFill-FinalExport 完成]
- 最终文件：*_最终版.docx/.xlsx (final_outputs\)
- 最终报告：final_report_*.json/.md (final_reports\)
- 写入字段：n
- 跳过字段：n
- 拒绝字段：n
- 无法定位字段：n
- 是否修改 vault：否
- 是否修改原始文件：否
- 是否修改草稿文件：否
- 是否联网：否
- 主流程闭环完成
```

## html_review 支持

SafeFill-FinalExport 现在支持 ReviewUI v2 生成的 `mode=html_review` 检查结果。

当 `review_result_*.json` 中包含：

```json
{
  "mode": "html_review",
  "tables": []
}
```

FinalExport 会：

1. 读取 `draft_file`。
2. 确认 `draft_file` 位于 `D:\SafeFill\draft_outputs\` 内。
3. 复制草稿到 `final_outputs\`。
4. 将网页编辑后的 `tables` 单元格内容逐格写回最终文件副本。
5. 生成 `final_report_*.json` 和 `final_report_*.md`，并记录 `mode=html_review`。

旧版字段确认模式仍然兼容；没有 `mode=html_review` 时继续走原导出逻辑。
