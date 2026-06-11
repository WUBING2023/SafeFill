---
name: SafeFill-FormReview
description: "Auto-fill new blank forms using vault data, then launch local web review at http://127.0.0.1:8787/"
---

# SafeFill-FormReview

## Skill 名称

SafeFill-FormReview — 填表 + 检查

## 调用前提示

现在进入填表和检查步骤。我会先用 vault 资料填写新表格，再打开本地网页让你直接检查和修改。FormReview 使用 `app\api_assist.py` 公共模块进行 API-first 填表；是否发送由 API 配置控制。

> API-first | 不修改原始表格 | 不修改 vault | 用户配置 API 风险

---

## 主动沟通要求

运行前必须告诉用户：

1. 这一步会读取 `vault\profile.json` 和 `new_forms\`。
2. 会生成草稿、HTML 预览和网页检查界面。
3. 原始空白表不会被修改。

网页启动后必须主动说明：

1. 浏览器将自动打开 `http://127.0.0.1:8787/`；如未打开，可手动访问。
2. 用户需要检查表格内容。
3. 黄色空白格可以手动补充。
4. 修改完成后必须点击”保存检查结果”。
5. 只有保存后，FinalExport 才能读取用户确认内容。

如果用户保存后，必须主动建议下一步：运行 `SafeFill-FinalExport`。

## 适用场景

用户已初始化 vault 资料库，新表格已放入 `new_forms\`，需要一次完成"自动填写草稿 + 网页检查修改"。

## 支持的填写结构

FormReview 内部的 DraftFill 支持以下常见表格结构：

1. 字段在左、空格在右：`姓名 | ____`
2. 字段在上一行、空格在下一行：

   ```
   姓名 | 手机号 | 导师
   ____ | ____   | ____
   ```

3. 同一单元格冒号占位：`姓名：____`、`导师：`
4. 标准字段和 vault `custom_fields` 都可填写，例如民族、政治面貌、导师、学号、爱好。
5. **Word 文本框**：可识别结构、标签，支持写入简单文本框（空/仅标签），已填内容不覆盖。检查页会显示文本框字段状态，但版面以 Word 草稿为准。

安全规则不变：已有内容不覆盖，复杂字段进入网页检查，不直接导出最终版。

## 输入

- `D:\SafeFill\vault\profile.json`
- `D:\SafeFill\new_forms\`（`.docx` / `.xlsx`）

## 输出

- `D:\SafeFill\review_html\`
- `D:\SafeFill\filling_reports\`
- `D:\SafeFill\draft_outputs\`
- `D:\SafeFill\review_results\`

## 允许调用的脚本

```
python D:\SafeFill\app\form_review.py
python D:\SafeFill\app\form_review.py --all          # 处理全部文件
python D:\SafeFill\app\form_review.py --no-open      # 不自动打开浏览器
python D:\SafeFill\app\form_review.py --all --no-open
```

**默认只处理 new_forms 中最新修改的一个文件。** 如需批量处理全部文件，使用 `--all`。

内部调用：
1. `fill_form_draft.py`（生成草稿 + HTML）
2. `review_server.py`（启动网页检查）

## 运行前检查

1. `vault\profile.json` 是否存在
2. `new_forms\` 中是否有 `.docx` / `.xlsx`
3. API 默认关闭

## 执行步骤

1. 运行 `fill_form_draft.py`
2. 确认 `review_html\latest_review_html.json` 生成
3. 启动 `review_server.py`（浏览器会自动打开；`--no-open` 可禁用）
4. 自动打开 `http://127.0.0.1:8787/`（默认行为）
5. 用户在网页中查看表格、修改、保存
6. 按 Ctrl+C 停止服务

## 成功标准

- `review_html\latest_review_html.json` 生成
- 网页正常访问
- 用户保存后 `review_results\review_result_*.json` 生成
- review_result 中 mode=html_review

## 失败处理

| 异常 | 处理 |
|------|------|
| `vault\profile.json` 不存在 | 停止，提示先运行 ProfileExtract 和 ProfileSave |
| new_forms 为空 | 停止，提示放入新表格 |
| DraftFill 失败 | 停止，不启动 ReviewUI |

## 禁止事项

- 不得联网
- 不得调用 API
- 不得修改 vault
- 不得修改 new_forms 原始文件

## 安全约束

| 约束项 | 值 |
|--------|-----|
| 允许联网 | 否 |
| 允许调用 API | 否 |
| 允许修改 vault | 否 |
| 允许修改原始文件 | 否 |
| 允许安装依赖 | 否 |
