# SafeFill 子 Skill 运行顺序

## 主流程

```
SafeFill-ProjectGuard        ← 安全检查（每次开始前）
        ↓
SafeFill-ProfileExtract      ← 从旧表格提取候选资料
        ↓
SafeFill-ProfileSave         ← 用户确认后保存到 vault\profile.json
        ↓
SafeFill-FormReview          ← 填表 + 网页检查（合并 DraftFill + ReviewUI）
        ↓
SafeFill-FinalExport         ← 导出最终文件
        ↓
SafeFill-Cleaner preview     ← 可选：预览可清理的临时隐私文件
```

## API 调用

API 调用由 `app\api_assist.py` 公共模块提供。SafeFill 主流程采用 API-first，API 配置检查：

```bash
python D:\SafeFill\app\api_assist.py check
```

## 数据流

```
input_forms\          旧表格（用户放入）
    ↓ [SafeFill-ProfileExtract]
candidate_reviews\    候选信息
    ↓ [SafeFill-ProfileSave 询问用户确认]
vault\profile.json     唯一正式个人信息库
    ↓ [SafeFill-FormReview]
new_forms\            新表格（用户放入）
    ↓ [SafeFill-FormReview]
review_html\          HTML 预览
draft_outputs\        草稿文件（内部过程产物）
filling_reports\      填写报告（内部过程产物）
    ↓ [网页保存]
review_results\       检查结果
    ↓ [SafeFill-FinalExport]
final_outputs\        最终文件
```

## 每个子 Skill 的入口命令

| 子 Skill | 命令 |
|----------|------|
| SafeFill-ProjectGuard | `python D:\SafeFill\app\project_guard.py` |
| SafeFill-ProfileExtract | `python D:\SafeFill\app\extract_candidates.py` |
| SafeFill-ProfileSave | `python D:\SafeFill\app\save_confirmed_profile.py` |
| SafeFill-FormReview | `python D:\SafeFill\app\form_review.py` |
| SafeFill-FinalExport | `python D:\SafeFill\app\export_final.py` |
| SafeFill-Cleaner | `python D:\SafeFill\app\cleaner.py preview` |

> `fill_form_draft.py` 和 `review_server.py` 是 FormReview 内部脚本，不建议用户单独调用。

## 主动沟通要求

每一步完成后都必须主动建议下一步，不能只输出日志：

| 当前步骤完成 | 必须建议 |
|--------------|----------|
| ProjectGuard | 根据体检结果建议 Extract / Save / FormReview / FinalExport / Cleaner preview |
| ProfileExtract | 建议 ProfileSave，并提醒候选信息还未写入 vault |
| ProfileSave | 建议放入新表并运行 FormReview |
| FormReview | 提醒用户在网页检查并点击“保存检查结果”，保存后建议 FinalExport |
| FinalExport | 建议打开最终文件检查，并可选 Cleaner preview |
| Cleaner preview | 询问是否确认清理，不得自动 clean |

## 前提条件

每个子 Skill 运行前必须确认：

1. 上游子 Skill 的输出目录存在且包含所需文件
2. `SafeFill-ProjectGuard` 检查通过
3. `api_config.json` 中 `enabled: false`（除非有意开启 API）
