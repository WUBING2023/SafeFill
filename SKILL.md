# SafeFill

## Skill 名称

SafeFill

## 启动欢迎语

你好，我是 SafeFill，本地安全填表助手。

我会帮助你把常用个人资料整理到本地 vault 资料库里，再用这些资料填写新的 Word / Excel 表格，最后通过本地网页让你检查、修改并确认后导出最终文件。

整个主流程默认不联网：ProfileExtract → ProfileSave → FormReview → FinalExport

**API-first 说明**：
SafeFill 采用 API-first 模式，旧资料、空白表结构和 vault 资料可能发送给用户配置的大模型 API。用户需自行确认 API 服务商、密钥、数据合规和隐私风险。

**安全底线**：
- 不自动提交申报系统
- 不直接修改原始表格
- 不自动写入 vault
- API Key 不写入项目文件
- 所有 API 调用记录可追踪

---

## 适用场景

帮助老师、行政人员、科研人员处理重复填表任务。典型场景：
- 项目申报表（国自然、省自然、社科基金等）
- 人员信息表（年度考核、职称评审、人才项目）
- 成果登记表（论文、专利、获奖）
- 各类审批表和备案表

---

## 当前支持范围

### 支持的格式

| 格式 | 状态 |
|------|------|
| `.docx`（Word 文档） | ✅ 段落、表格、文本框 |
| `.xlsx`（Excel 表格） | ✅ 表格 |
| `.pdf`（旧资料提取） | ✅ 需 MinerU |

### docx 文本框支持

SafeFill 已支持 Word 文本框全流程：
- 旧资料文本框提取
- 空白表文本框识别
- 简单文本框写入
- ReviewUI 文本框状态提示

### 暂不支持的格式

| 格式 | 计划 |
|------|------|
| `.pdf`（可编辑表单） | 后续版本 |
| `.pdf`（扫描件） | 后续版本 |
| 图片表格 | 后续版本 |
| 网页申报系统自动提交 | 暂不支持 |

---

## 总工作流程

```
旧资料 → ProfileExtract 提取候选
        ↓
ProfileSave 用户确认后保存到 vault\profile.json
        ↓
新表格 → FormReview 自动填写 + 本地网页检查 + 用户保存确认
        ↓
FinalExport 导出最终文件
        ↓
Cleaner preview 可选清理临时隐私文件

API 调用由 app\api_assist.py 作为公共模块提供。SafeFill 主流程采用 API-first，不再提供独立 API 预览子 Skill。
```

---

## 命令入口

### 第 1 步：从旧表格提取候选资料

```bash
python D:\SafeFill\app\extract_candidates.py
```

- 前提：将旧的 `.docx` / `.xlsx` 表格副本放入 `D:\SafeFill\input_forms\`
- 输出：`candidate_reviews\` 中的 Markdown 检查文件和 JSON 数据文件
- 联网：否
- 修改原始文件：否

### 第 2 步：保存用户确认资料

```bash
python D:\SafeFill\app\save_confirmed_profile.py
```

- 前提：`candidate_reviews\latest_candidate.json` 已由 ProfileExtract 生成
- 输出：`vault\profile.json`
- 说明：SafeFill 初版只维护一个正式个人信息库，不使用 `person_001/person_002` 多人物编号
- 联网：否
- 修改原始文件：否

### 第 3 步：填表 + 本地网页检查

```bash
python D:\SafeFill\app\form_review.py
```

- 前提：`vault\profile.json` 已存在；新表格 `.docx` / `.xlsx` 副本在 `new_forms\`
- 输出：`review_html\`、`draft_outputs\`、`filling_reports\`、`review_results\`
- 浏览器访问：`http://127.0.0.1:8787/`
- 用户动作：检查网页表格，必要时修改黄色空白格，然后点击“保存检查结果”
- 联网：否
- 修改原始文件：否
- 修改 vault：否

### 第 4 步：导出最终文件

```bash
python D:\SafeFill\app\export_final.py
```

- 前提：`review_results\` 中有用户点击“保存检查结果”后生成的正式 `review_result_*.json`
- 输出：`final_outputs\` 中的最终版文件；`final_reports\` 中的导出报告
- 联网：否
- 修改原始文件：否
- 修改草稿文件：否
- 修改 vault：否

### 第 5 步（可选）：隐私清理预览

```bash
python D:\SafeFill\app\cleaner.py preview
```

- 用途：预览可清理的旧表、候选文件、草稿、网页检查结果等过程产物
- 默认保留：`vault\` 和 `final_outputs\`
- 删除必须由用户明确确认：`python D:\SafeFill\app\cleaner.py clean --confirm CLEAN`

### API 配置检查

```bash
python D:\SafeFill\app\api_assist.py check
```

- API 调用由 `app\api_assist.py` 公共模块统一管理
- API Key 只能通过环境变量设置，不写入文件
- 所有 API 调用记录在 `api_logs\` 可追踪

---

## 安全原则

1. **API-first**：主流程默认使用大模型 API。user_accepts_api_data_risk 设为 true 后生效。
2. **API 数据由用户负责**：用户自行确认 API 服务商、密钥、数据合规和隐私风险。
3. **API Key 不入文件**：仅通过环境变量 `SECURE_FORM_API_KEY` 读取。
4. **所有 API 调用可追踪**：请求和响应记录在 `api_logs\`。
5. **不自动写入 vault**：API 提取的资料仍需用户确认保存。
6. **不自动导出最终文件**：必须经过网页 ReviewUI 用户确认。
7. **不得修改原始文件**：所有修改操作在副本上进行。
8. **不得自动提交申报系统**：不模拟网页表单自动提交。
9. **不得读取项目外的私人文件**：仅限 `D:\SafeFill\` 目录内的操作。

---

## 用户数据目录

以下目录包含用户数据，**禁止删除、禁止打包上传、禁止提交到 Git**：

| 目录 | 数据类型 | 敏感级别 |
|------|----------|----------|
| `vault\` | 用户确认的个人资料库 | **最高** |
| `input_forms\` | 用户导入的旧表格副本 | 高 |
| `new_forms\` | 用户导入的新表格副本 | 高 |
| `candidate_reviews\` | 候选信息（含完整敏感值） | **最高** |
| `draft_outputs\` | 自动填写草稿 | 中 |
| `review_results\` | 用户检查确认结果 | 高 |
| `final_outputs\` | 最终导出文件 | 高 |
| `filling_reports\` | 填写报告 | 中 |
| `final_reports\` | 导出报告 | 中 |
| `api_previews\` | 历史 API preview 目录（已废弃 preview→send 流程），可由 Cleaner 清理 | 中 |
| `api_results\` | API 返回结果 | 中 |
| `logs\` | 操作日志 | 中 |
| `api_logs\` | API 操作日志 | 中 |

---

## Claude Code 执行约束

任何 Claude Code 实例在操作本 Skill 时必须遵守：

1. **不得自由发挥**：严格按照阶段文档执行，不扩大任务范围。
2. **不得扩大阶段范围**：一次只执行一个阶段或用户指定的操作。
3. **不得安装依赖**：除非用户明确同意安装指定包。
4. **不得联网**：除非用户明确要求 API send 且已通过安全闸门。
5. **不得覆盖已有文件**：修改前先备份，见已存在文件先报告。
6. **不得修改核心脚本**：`app\` 中的 `.py` 文件不得随意改动。
7. **不得删除用户数据**：用户数据目录中的任何内容不得删除。
8. **不得把用户数据打包或复制到项目外**。
9. **每阶段结束后必须汇报**：
   - 创建了哪些文件
   - 修改了哪些文件
   - 是否联网
   - 是否调用 API
   - 是否安装依赖
   - 是否修改 vault / 原始文件
10. **必须主动建议下一步**：不能只说“完成”，必须说明用户现在该检查什么、是否需要点击保存、下一步运行哪个 SafeFill 子 Skill。
11. **执行前先读**：`docs\项目阶段总路线图.md`
12. **主动沟通规则**：见 `docs\SafeFill主动沟通规则.md`
