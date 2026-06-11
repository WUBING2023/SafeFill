# SafeFill-FinalExport html_review 支持说明

## 目标

SafeFill-FinalExport 支持 ReviewUI v2 生成的 `mode=html_review` 结果。用户在网页中直接编辑表格后，FinalExport 根据 `review_result_*.json` 中的 `tables` 内容导出最终 Word 或 Excel 文件。

## 输入

- `D:\SafeFill\review_results\review_result_*.json`
- `D:\SafeFill\draft_outputs\` 中的草稿文件

`html_review` 结构示例：

```json
{
  "mode": "html_review",
  "source_file": "D:\\SafeFill\\new_forms\\表格.docx",
  "draft_file": "D:\\SafeFill\\draft_outputs\\表格_自动填写草稿.docx",
  "html_file": "D:\\SafeFill\\review_html\\表格.html",
  "tables": [
    {
      "table_index": 1,
      "rows": [
["姓名", "示例用户", "性别", "男"]
      ]
    }
  ]
}
```

## 导出规则

1. `draft_file` 必须在 `D:\SafeFill\draft_outputs\` 内。
2. 先复制草稿到 `final_outputs\`，只修改最终文件副本。
3. `.docx` 使用 Word 表格索引和行列位置逐格写入。
4. `.xlsx` 使用工作表行列位置逐格写入。
5. 行列超出实际表格范围时跳过并写入最终报告。
6. 合并单元格中非左上角单元格会跳过并记录原因。

## 输出

- `D:\SafeFill\final_outputs\*_最终版.docx/.xlsx`
- `D:\SafeFill\final_reports\final_report_*.json`
- `D:\SafeFill\final_reports\final_report_*.md`

最终报告会记录：

- `mode=html_review`
- 使用的 `review_result`
- 使用的 `draft_file`
- 最终输出文件
- 写入单元格数量
- 跳过单元格数量和原因
- 原始文件、草稿、vault 均未修改

## 兼容性

没有 `mode=html_review` 的旧 `review_result` 继续走原有字段确认导出逻辑。

## 安全边界

- 不修改 `new_forms\` 原始文件。
- 不修改 `draft_outputs\` 草稿文件。
- 不修改 `vault\`。
- 不联网。
- API 由用户自行配置。
- 不删除旧报告或旧最终文件。
