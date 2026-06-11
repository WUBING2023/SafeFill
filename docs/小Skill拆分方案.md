# SafeFill 子 Skill 拆分方案

## 拆分目标

将当前单体 `D:\SafeFill\app\` 中的脚本拆分为 8 个独立子 Skill，每个子 Skill 只做一件事、只读自己的输入目录、只写自己的输出目录。

## 子 Skill 总览

| 子 Skill | 对应脚本 | 职责 |
|----------|----------|------|
| SafeFill-ProjectGuard | （新增） | 安全检查、目录结构验证、API 状态检查 |
| SafeFill-ProfileExtract | `extract_candidates.py` | 从 `input_forms\` 的旧表格提取候选资料 |
| SafeFill-ProfileSave | `save_confirmed_profile.py` | 把 `confirmed_profile.json` 保存到 `vault\` |
| SafeFill-DraftFill | `fill_form_draft.py` | 用资料库自动填写 `new_forms\` 中的新表格 |
| SafeFill-ReviewUI | `review_server.py` | 启动本地网页检查服务 |
| SafeFill-FinalExport | `export_final.py` | 根据 `review_result` 导出最终文件 |
| API 公共模块 | `api_assist.py` | 公共 API 模块，不作为独立 Skill 运行 |
| SafeFill-Orchestrator | （SKILL.md） | 总控，只指导流程，不直接处理文件 |

## 计划目录结构

```
D:\SafeFill\
├── skills\
│   ├── SafeFill-ProjectGuard\
│   │   └── SKILL.md
│   ├── SafeFill-ProfileExtract\
│   │   └── SKILL.md
│   ├── SafeFill-ProfileSave\
│   │   └── SKILL.md
│   ├── SafeFill-DraftFill\
│   │   └── SKILL.md
│   ├── SafeFill-ReviewUI\
│   │   └── SKILL.md
│   ├── SafeFill-FinalExport\
│   │   └── SKILL.md
│   ├── (API 公共模块 app\api_assist.py — 不作为独立 Skill)
│   └── SafeFill-Orchestrator\
│       └── SKILL.md
├── app\          （核心脚本，子 Skill 调用入口）
├── vault\        （用户资料库）
├── docs\         （本文档）
└── ...
```

## 各子 Skill 职责边界

### SafeFill-ProjectGuard

**只检查，不处理数据。**

- 检查 `D:\SafeFill\` 目录结构是否完整
- 检查 `vault\profiles\profile_template.json` 是否存在
- 检查 `api_config.json` 中 `enabled` 和 `dry_run` 状态
- 检查 `input_forms\` / `new_forms\` 中是否有文件
- 检查是否存在疑似用户隐私数据残留
- **不修改任何文件**

### SafeFill-ProfileExtract

**只读 input_forms\，只写 candidate_reviews\。**

- 读取 `input_forms\` 中的 `.docx` / `.xlsx`
- 提取候选个人信息
- 生成 `candidate_review_*.md` 和 `candidate_review_*.json`
- 生成 `confirmed_profile_template_*.json`
- **不修改原始文件**
- **不写入 vault**

### SafeFill-ProfileSave

**只读 candidate_reviews\，只写 vault\profiles\。**

- 读取 `candidate_reviews\confirmed_profile.json`
- 校验字段名和值
- 跳过未知字段、空字段、未确认字段
- 保存为 `vault\profiles\person_xxx.json`
- **不覆盖已有 profile**

### SafeFill-DraftFill

**只读 vault\ + new_forms\，只写 draft_outputs\ + filling_reports\。**

- 读取 `vault\profiles\person_001.json`
- 读取 `new_forms\` 中的 `.docx` / `.xlsx`
- 生成草稿到 `draft_outputs\`
- 生成填写报告到 `filling_reports\`
- **不修改原始文件**
- **不修改 vault**

### SafeFill-ReviewUI

**只读 filling_reports\，只写 review_results\。**

- 启动 `http://127.0.0.1:8787/`
- 用户通过浏览器检查、修改、补充字段
- 保存 `review_result_*.json` 到 `review_results\`
- **不修改草稿文件**
- **不修改 vault**

### SafeFill-FinalExport

**只读 review_results\ + draft_outputs\，只写 final_outputs\ + final_reports\。**

- 读取 `review_result_*.json`
- 读取 `draft_outputs\` 中的草稿
- 生成最终文件到 `final_outputs\`
- 生成导出报告到 `final_reports\`
- **不修改原始文件**
- **不修改 vault**

### API 公共模块

`app\api_assist.py` 是公共 API 模块，不作为独立 Skill 运行。SafeFill 主流程采用 API-first，ProfileExtract 和 FormReview 可直接调用配置的大模型 API。
- **不修改任何表格文件**

### SafeFill-Orchestrator

**只读文档和元数据，不处理文件。**

- 说明完整工作流程
- 指引用户按顺序执行子 Skill
- 说明每个子 Skill 的输入输出
- **不执行任何脚本**
- **不访问任何数据文件**

## 输入输出契约

详见 `小Skill输入输出契约.md`。核心原则：

1. 每个子 Skill 只读自己的输入目录
2. 每个子 Skill 只写自己的输出目录
3. 子 Skill 之间通过文件传递数据，不直接调用
4. 上游子 Skill 的输出 = 下游子 Skill 的输入
