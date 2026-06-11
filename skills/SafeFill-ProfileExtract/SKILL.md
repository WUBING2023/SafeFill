---
name: SafeFill-ProfileExtract
description: "Extract candidate personal info from old .docx/.xlsx/.pdf forms into structured review files"
---

# SafeFill-ProfileExtract

## Skill 名称

SafeFill-ProfileExtract — 候选资料提取

## 调用前提示

现在进入资料提取步骤。我会从 input_forms 中的旧表格或简历里提取可能有用的个人信息（姓名、专业、部门、手机号、邮箱等，以及自定义字段）。这一步只是生成候选信息，不会直接写入 vault。你后面还需要检查和确认。

> API-first | 不修改原始旧表 | 不写入 vault | API Key不入文件

---

## 主动沟通要求

运行前必须告诉用户：本步骤只是“提取候选”，不会保存到个人信息库。

运行后必须用普通中文总结：

1. 提取了多少字段。
2. 哪些字段置信度高，哪些字段需要用户复核。
3. 是否识别到自定义字段，例如民族、导师、学号、爱好。
4. 最新候选文件在哪里。
5. 建议下一步：运行 `SafeFill-ProfileSave`，由用户确认是否保存到 `vault\profile.json`。
6. 如果用户觉得“提取太少”，必须解释是文件本身缺少信息，还是提取规则没有覆盖；不能简单说“换文件”。

不得要求用户手动创建 `confirmed_profile.json` 作为必要步骤。

## 激进提取规则

ProfileExtract 允许更积极地提取候选资料，但必须区分置信度：

1. 明确字段名 + 明确值：可标为 high，例如 `民族 | 汉族`、`导师：张三`。
2. 无字段名但格式很强：标为 medium，例如邮箱、手机号、身份证号。
3. 由身份证号推断出生日期：标为 medium。
4. 长文本、课程表字段、疑似混入多字段：不得直接保存为 high。
5. medium/low 字段必须提醒用户确认后再保存。

## 适用场景

用户已把旧表格（以前填过的 `.docx` / `.xlsx`）放入 `input_forms\`，需要从中提取候选个人信息。

## 输入

- `D:\SafeFill\input_forms\`（`.docx` / `.xlsx` / `.pdf` 文件，只读）
- `.docx` 支持：普通段落、表格、文本框/形状文字（v1.4）

## 输出

- `D:\SafeFill\candidate_reviews\`
  - `candidate_review_*.md` — 脱敏检查文件
  - `candidate_review_*.json` — 完整候选数据
  - `confirmed_profile_template_*.json` — 确认模板草稿
  - `latest_candidate.json` — 指向最新候选结果

## 允许调用的脚本

```
python D:\SafeFill\app\extract_candidates.py
```

**只能调用这一个脚本。**

## 运行前检查

1. `input_forms\` 是否存在
2. `input_forms\` 中是否有 `.docx` / `.xlsx` / `.pdf` 文件
3. `.pdf` 需要安装 MinerU；未安装时自动跳过 PDF
4. `vault\` 不在本阶段写入范围
5. API 默认关闭

## 执行步骤

1. 检查 `input_forms\` 中的文件列表
2. 运行 `extract_candidates.py`
3. 确认输出文件生成
4. 打开 `candidate_review_*.md` 展示结果摘要（不展示完整敏感值）
5. 指引用户下一步：检查候选摘要 → 运行 SafeFill-ProfileSave，由用户确认是否保存到 vault

## 成功标准

- 生成至少一个 `candidate_review_*.md`
- 生成至少一个 `candidate_review_*.json`
- 生成 `confirmed_profile_template_*.json`
- 生成或更新 `latest_candidate.json`
- Markdown 中敏感信息已脱敏
- 日志中无完整敏感值

## 失败处理

| 异常情况 | 处理 |
|----------|------|
| `input_forms\` 为空 | 提示用户放入文件，不报错 |
| 无 `.docx` / `.xlsx` / `.pdf` | 提示支持的格式 |
| 文档无法解析 | 跳过该文件，写日志，继续处理其他文件 |
| 提取到 0 个字段 | 提示可能文档结构特殊，建议换更完整的旧资料，或在 ProfileSave 中手动补充资料 |

## 禁止事项

- 不得修改原始文件
- 不得自动保存候选信息到 vault
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
| 允许修改草稿文件 | 不适用 |
| 允许安装依赖 | 否 |

## 完成后汇报模板

```
[SafeFill-ProfileExtract 完成]
- 扫描文件：n 个 (.docx x, .xlsx y)
- 提取字段：n 个 (high x, medium y, low/manual z)
- 输出目录：candidate_reviews\
- 模板草稿：confirmed_profile_template_*.json
- 是否修改 vault：否
- 是否修改原始文件：否
- 建议下一步：SafeFill-ProfileSave 读取最新候选，并让用户确认是否保存到 vault\profile.json
```
