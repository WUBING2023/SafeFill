---
name: SafeFill-ProfileSave
description: "User-confirmed save of extracted profile data to vault/profile.json with conflict detection and auto-backup"
---

# SafeFill-ProfileSave

## Skill 名称

SafeFill-ProfileSave — 个人信息库保存确认

## 调用前提示

现在进入资料保存步骤。我会读取 SafeFill-ProfileExtract 刚生成的最新候选资料，并询问是否保存到本地个人信息库 `vault\profile.json`。

SafeFill 初版只维护一个个人信息库，不再使用 `person_001.json`、`person_002.json` 这种多人物编号文件。

> 用户确认后写入 vault | 冲突不自动覆盖 | API-first | API Key不入文件

---

## 主动沟通要求

运行前必须告诉用户：

1. 这一步会读取 `candidate_reviews\latest_candidate.json`。
2. 这一步可能修改 `vault\profile.json`，但必须经过用户确认。
3. 如果 vault 已有资料，新提取资料不同，必须展示字段名、vault 原值、新值。
4. 不得替用户选择覆盖、跳过或保存。

运行后必须展示“个人信息表”摘要，字段要完整展示给用户检查；不要只说保存成功。

完成后必须主动建议下一步：

`把要填写的空白表格放入 new_forms\ → 运行 SafeFill-FormReview`

## 适用场景

用户已经运行 SafeFill-ProfileExtract，并希望把最新提取到的资料保存到本地个人信息库。

## 输入

- `D:\SafeFill\candidate_reviews\latest_candidate.json`
- `D:\SafeFill\candidate_reviews\candidate_review_*.json`
- `D:\SafeFill\vault\profile.json`（如果已存在则读取并比较）

## 输出

- `D:\SafeFill\vault\profile.json`
- `D:\SafeFill\vault\backups\profile_backup_*.json`（覆盖前自动备份）

## 允许调用的脚本

```
python D:\SafeFill\app\save_confirmed_profile.py
```

**只能调用这一个脚本。**

## 运行前检查

1. `candidate_reviews\latest_candidate.json` 是否存在。
2. 最新候选 JSON 是否存在。
3. 候选字段是否为空。
4. API 默认关闭。

## 执行步骤

1. 读取 `latest_candidate.json` 指向的最新候选资料。
2. 如果 `vault\profile.json` 不存在，询问用户是否创建个人信息库。
3. 如果 `vault\profile.json` 已存在，对比新旧字段。
4. 对空字段补充、冲突字段覆盖、自定义字段保存，必须按脚本交互或用户明确指令处理。
5. 保存后展示合并后的“个人信息表”。

## 成功标准

- `vault\profile.json` 存在。
- 标准字段和 `custom_fields` 保存正确。
- 覆盖前已备份。
- 冲突字段没有被静默覆盖。
- 保存后展示个人信息表。

## 失败处理

| 异常情况 | 处理 |
|----------|------|
| `latest_candidate.json` 不存在 | 停止，提示先运行 SafeFill-ProfileExtract |
| 候选文件缺失 | 停止，提示重新提取 |
| JSON 格式错误 | 停止，提示文件格式问题 |
| 用户不确认保存 | 停止，不修改 vault |
| 字段冲突 | 展示旧值和新值，等待用户决定 |

## 禁止事项

- 不得使用 `person_001.json`、`person_002.json` 作为正式资料库。
- 不得自动覆盖 `vault\profile.json`。
- 不得替用户确认保存。
- 不得保存空字段覆盖已有值。
- 不得联网。
- 不得调用 API。
- 不得安装依赖。

## 安全约束

| 约束项 | 值 |
|--------|-----|
| 允许联网 | 否 |
| 允许调用 API | 否 |
| 允许修改 vault | 是，仅用户确认后修改 `vault\profile.json` |
| 允许修改原始文件 | 否 |
| 允许修改草稿文件 | 不适用 |
| 允许安装依赖 | 否 |

## 完成后汇报模板

```
[SafeFill-ProfileSave 完成]
- vault 文件：vault\profile.json
- 保存/更新字段：n 个
- 自定义字段：n 个
- 冲突字段：无 / 有(n 个，已按用户选择处理)
- 是否备份旧 vault：是 / 否
- 是否联网：否
- 是否调用 API：否
- 个人信息表：已展示
- 建议下一步：把空白表格放入 new_forms\，然后运行 SafeFill-FormReview
```
