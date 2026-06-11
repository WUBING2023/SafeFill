---
name: SafeFill-Cleaner
description: "Preview and clean temporary privacy files — never auto-deletes, requires explicit user confirmation"
---

# SafeFill-Cleaner

## Skill 名称

SafeFill-Cleaner — 隐私清理

## 调用前提示

我会帮你清理旧表和过程产物，降低隐私残留风险。默认不会清理 vault，也不会清理最终输出 final_outputs。先运行 preview 看看有哪些文件，确认后再 clean。

> 不清理 vault | final_outputs 默认保留 | API-first | API Key不入文件

---

## 主动沟通要求

Cleaner 不能默认执行删除。

运行 `preview` 后必须告诉用户：

1. 将清理哪些目录。
2. 大约有多少文件。
3. 哪些目录会保留：`vault\`、`final_outputs\`、`app\`、`skills\`、`docs\`。
4. 如果用户确认清理，再给出 `clean --confirm CLEAN` 命令。

运行 `clean` 前必须确认用户已经明确要求清理。不得因为流程完成就自动清理。

## 适用场景

- 正式测试前
- 一轮填表完成后
- 用户想清理旧表和临时结果
- 防止旧表、草稿、报告残留隐私

## 命令

```
python D:\SafeFill\app\cleaner.py preview
python D:\SafeFill\app\cleaner.py clean --confirm CLEAN
python D:\SafeFill\app\cleaner.py clean --include-final --confirm CLEAN
```

## 默认清理范围

input_forms, new_forms, candidate_reviews, draft_outputs, filling_reports, review_html, review_results, final_reports, api_previews, api_results, api_logs, logs

## 默认不清理

vault, final_outputs, app, skills, docs, deprecated

## 安全约束

| 约束项 | 值 |
|--------|-----|
| 允许联网 | 否 |
| 允许调用 API | 否 |
| 允许清理 vault | 否 |
| 允许安装依赖 | 否 |
