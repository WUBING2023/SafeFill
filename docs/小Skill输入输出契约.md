# SafeFill 子 Skill 输入输出契约

## 契约原则

1. 子 Skill 之间**不直接调用**，通过文件传递数据
2. 上游输出 = 下游输入
3. 只读输入目录，只写输出目录
4. 不跨目录读写
5. 每个子 Skill 必须主动说明当前步骤、结果和建议下一步

---

## SafeFill-ProjectGuard

| 属性 | 值 |
|------|-----|
| 输入 | 整个 `D:\SafeFill\` 目录结构 |
| 输出 | 终端输出（检查结果），不写文件 |
| 检查项 | 目录完整性、模板存在性、API 状态、隐私数据残留 |
| 后续 | 通过后进入 SafeFill-ProfileExtract |

---

## SafeFill-ProfileExtract

| 属性 | 值 |
|------|-----|
| 输入目录 | `input_forms\`（`.docx` / `.xlsx`） |
| 输出目录 | `candidate_reviews\` |
| 输出文件 | `candidate_review_*.md`、`candidate_review_*.json`、`confirmed_profile_template_*.json`、`latest_candidate.json` |
| 给下游的约定 | JSON 包含 `field_key`、`value`、`quality`、`confirmed` 字段 |
| 依赖 | 无 |

---

## SafeFill-ProfileSave

| 属性 | 值 |
|------|-----|
| 输入目录 | `candidate_reviews\` |
| 输入文件 | `latest_candidate.json` 指向的最新候选 JSON |
| 输出目录 | `vault\` |
| 输出文件 | `profile.json` |
| 给下游的约定 | 只维护一个正式个人信息表；标准字段和 `custom_fields` 都可供填表使用 |
| 依赖 | SafeFill-ProfileExtract（需要最新候选信息） |

---

## SafeFill-FormReview（合并 DraftFill + ReviewUI）

| 属性 | 值 |
|------|-----|
| 输入目录 1 | `vault\`（只读） |
| 输入目录 2 | `new_forms\`（`.docx` / `.xlsx`） |
| 输入文件 | `profile.json` |
| 输出目录 | `review_html\` + `draft_outputs\` + `filling_reports\` + `review_results\` |
| 输出文件 | `review_html\latest_review_html.json`、`*_自动填写草稿.docx/.xlsx`、`filling_report_*_*.json/.md`、`review_result_*.json` |
| 给下游的约定 | review_result 支持 mode=html_review，包含 tables |
| 依赖 | SafeFill-ProfileSave（需要 `vault\profile.json`） |
| 内部脚本 | `fill_form_draft.py` + `review_server.py`（不建议用户单独调用） |

---

## SafeFill-FinalExport

| 属性 | 值 |
|------|-----|
| 输入目录 1 | `review_results\`（只读） |
| 输入目录 2 | `draft_outputs\`（只读） |
| 输入文件 | `review_result_*.json` + 对应草稿文件 |
| 输出目录 1 | `final_outputs\` |
| 输出目录 2 | `final_reports\` |
| 输出文件 | `*_最终版.docx/.xlsx`、`final_report_*.json/.md` |
| 给下游的约定 | 最终文件可直接使用；报告包含导出统计和安全确认 |
| 依赖 | SafeFill-FormReview（需要 review_result） |

---

## API 公共模块

API 调用由 `app\api_assist.py` 公共模块统一管理。SafeFill 主流程采用 API-first。
API 配置检查：`python D:\SafeFill\app\api_assist.py check`

相关的 I/O 目录（仍保留）：
- `api_logs\` — API 调用日志
- `api_previews\` — 历史预览文件（已废弃 preview→send 流程）
- `api_results\` — API 返回结果

---

## SafeFill-Cleaner

| 属性 | 值 |
|------|-----|
| 输入 | 过程目录，如 `input_forms\`、`candidate_reviews\`、`draft_outputs\`、`review_html\`、`review_results\` |
| 输出 | 预览报告；确认后清理过程产物 |
| 职责 | 降低隐私残留风险 |
| 安全约束 | 默认不清理 `vault\` 和 `final_outputs\`；无参数不扫描、不删除；clean 必须 `--confirm CLEAN` |

## SafeFill-FinalExport 对 html_review 的输入输出补充

输入：

- `review_results\review_result_*.json`
- 当 `mode=html_review` 时，必须包含 `draft_file` 和 `tables`。
- `draft_file` 必须位于 `draft_outputs\` 内。

输出：

- `final_outputs\*_最终版.docx/.xlsx`
- `final_reports\final_report_*.json/.md`

规则：

- `html_review` 模式按网页编辑后的表格行列内容导出。
- 旧字段确认模式继续兼容。
- 不修改原始文件。
- 不修改草稿文件。
- 不修改 vault。
- API-first。用户自行承担 API 数据风险。
