---
name: SafeFill-ProjectGuard
description: "SafeFill project safety guard — checks directories, scripts, API status, and flow state before any action"
---

# SafeFill-ProjectGuard

## Skill 名称

SafeFill-ProjectGuard — 项目安全守卫

## 调用前提示

我会先做一次只读体检，帮你看看 SafeFill 项目现在是否安全、流程走到哪一步、下一步该做什么。

这一步不会修改任何资料，也不会运行填表或导出脚本。它只检查目录、脚本、API 状态和流程残留。

> API-first | API Key不入文件 | 不修改 vault | 不修改表格 | 不删除文件

---

## 主动沟通要求

运行前必须先用普通中文欢迎用户，并说明 SafeFill 的主流程：

`ProfileExtract → ProfileSave → FormReview → FinalExport`

运行后必须主动判断当前状态，并给出一个明确的下一步。不得只输出体检日志。

如果发现流程已经完成，必须提醒用户：

1. 先检查 `final_outputs\` 中的最终文件。
2. 可选运行 `SafeFill-Cleaner preview` 查看临时隐私文件。
3. Cleaner 不会默认执行删除，清理必须由用户确认。

## 适用场景

每次运行 SafeFill 任何业务 Skill 之前，或用户要求检查项目状态时。

## 输入

- `D:\SafeFill\` 整个项目目录（只读）

## 输出

- `D:\SafeFill\docs\guard_check_report.md`（可选）

## 允许调用的脚本

无。本 Skill 只做只读检查，不调用任何业务脚本。

## 运行前检查

无需前置条件。

## 执行步骤

### 1. 核心脚本完整性

```
python -c "import os; scripts=['extract_candidates.py','save_confirmed_profile.py','fill_form_draft.py','review_server.py','form_review.py','export_final.py','api_assist.py','project_guard.py','cleaner.py']; missing=[s for s in scripts if not os.path.exists(f'D:\\SafeFill\\app\\{s}')]; print('ALL_OK' if not missing else 'MISSING: '+','.join(missing))"
```

### 2. API 状态检查

- 读取 `app\api_config.json`（如果存在）
- 检查 `enabled`、`api_first`、`user_accepts_api_data_risk`、`endpoint`、`model`、API Key 环境变量
- 如果 `api_first=true` 且 `user_accepts_api_data_risk=true`，向用户报告 API-first 已启用
- 如果 `enabled=true` 但 `api_first=false`，向用户报告 API 配置异常

### 3. 测试数据残留检查

- 检查 `vault\profile.json` 内容是否包含"测试人员""测试大学""哈利波特""110101"等已知测试数据片段
- 旧版 `vault\profiles\person_*.json` 只作为历史残留检查，不作为正式资料库
- 检查 `input_forms\` 中是否有 `test_` 前缀文件
- 检查 `new_forms\` 中是否有 `test_` 前缀文件

### 4. 目录状态检查

| 目录 | 检查内容 |
|------|----------|
| `vault\` | `profile.json` 是否存在 |
| `input_forms\` | 是否有 `.docx` / `.xlsx` 文件 |
| `new_forms\` | 是否有 `.docx` / `.xlsx` 文件 |
| `filling_reports\` | 是否有 `filling_report_*.json` |
| `review_results\` | 是否有 `review_result_*.json` |

### 5. 旧名残留检查

- 搜索 `docs\` 和根 `.md` 文件中是否存在"本地安全填表助手""SecureForm"等旧项目名
- 搜索是否有旧项目绝对路径残留（当前项目路径应为 `D:\SafeFill\`）

## 成功标准

- 所有核心脚本存在
- API 默认关闭（或用户已知晓开启状态）
- ControlCenter / ReviewUI / FormReview 均支持 `--no-open` 参数和自动打开浏览器
- 发现测试数据残留时报告但不自动清理
- 发现旧名残留时列出文件

## 失败处理

| 异常情况 | 处理 |
|----------|------|
| 核心脚本缺失 | 报告缺失文件，停止流程 |
| API enabled=true | 警告用户，不阻止 |
| 测试数据残留 | 报告位置，建议归档或清理 |
| 目录缺失 | 报告，不自动创建 |

## 禁止事项

- 不得修改用户数据
- 不得运行填表脚本
- 不得删除文件
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
[SafeFill-ProjectGuard 完成]
- 核心脚本：全部存在 / 缺失: xxx
- API 状态：api_first=true/false, user_accepts_api_data_risk=true/false
- 测试数据残留：无 / 有(n 处)
- 目录状态：正常 / 异常
- 旧名残留：无 / 有(n 处)
- 当前流程状态：待提取 / 待保存 / 待网页检查 / 待最终导出 / 已完成
- 建议下一步：只给一个明确动作和原因
```
