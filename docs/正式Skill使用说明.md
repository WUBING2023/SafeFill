# 正式 Skill 使用说明

> 本文档面向不会代码的用户。每一步都写清楚了"文件放哪→运行什么→在哪看结果→怎么判断成功"。

---

## 一、项目目录一览

| 目录 | 用途 | 你需不需要动 |
|------|------|-------------|
| `input_forms\` | 放旧表格的地方 | ✅ 放文件 |
| `new_forms\` | 放新表格的地方 | ✅ 放文件 |
| `candidate_reviews\` | 候选信息检查文件 | ✅ 查看和编辑 |
| `vault\profiles\` | 你的个人资料库 | ⚠️ 不要乱动 |
| `draft_outputs\` | 自动填写草稿 | ✅ 查看 |
| `review_results\` | 网页检查结果 | ✅ 保存时自动生成 |
| `final_outputs\` | 最终填好的文件 | ✅ 取走使用 |
| `filling_reports\` | 填写报告 | ✅ 查看 |
| `final_reports\` | 导出报告 | ✅ 查看 |
| `app\` | 程序代码 | ❌ 不要动 |
| `docs\` | 说明文档 | ✅ 查看 |
| `logs\` | 操作日志 | ❌ 不用管 |
| `api_previews\` | 历史 API preview（已废弃） | 可由 Cleaner 清理 |
| `api_results\` | API 调用 trace | ⚠️ 审计用 |

---

## 二、第一次初始化流程

### 2.1 放旧表格

把以前填过的 `.docx` / `.xlsx` 表格**复制**到：
```
D:\SafeFill\input_forms\
```
> 只放副本，不要放原件。

### 2.2 运行提取

```
python D:\SafeFill\app\extract_candidates.py
```

### 2.3 查看候选信息

打开文件夹：
```
D:\SafeFill\candidate_reviews\
```

用记事本打开最新的 `candidate_review_*.md` 文件。

逐项检查：
- ✅ 信息准确的 → 保留
- ❌ 信息不对的 → 记住，下一步修正
- ⚠️ 标记"需确认"的 → 仔细看

### 2.4 创建确认文件

在 `candidate_reviews\` 中新建 `confirmed_profile.json`。

参照 `candidate_review_*.json` 中的格式，把确认的信息写入，确保 `"confirmed": true`。

### 2.5 保存到资料库

```
python D:\SafeFill\app\save_confirmed_profile.py
```

成功后，你的资料保存在：
```
D:\SafeFill\vault\profiles\person_001.json
```

---

## 三、日常填表流程

### 3.1 放新表格

把要填的新 `.docx` / `.xlsx` 表格复制到：
```
D:\SafeFill\new_forms\
```

### 3.2 生成草稿

```
python D:\SafeFill\app\fill_form_draft.py
```

草稿在：`D:\SafeFill\draft_outputs\`

### 3.3 网页检查

启动服务：
```
python D:\SafeFill\app\review_server.py
```

浏览器打开：`http://127.0.0.1:8787/`

在网页中：
1. 选报告
2. 逐项检查已填写字段 → 接受 / 修改 / 清空 / 拒绝
3. 补充未填写字段
4. 可选勾选"保存到资料库"
5. 点击"保存检查结果"

完成后按 `Ctrl+C` 停止服务。

### 3.4 导出最终文件

```
python D:\SafeFill\app\export_final.py
```

最终文件在：`D:\SafeFill\final_outputs\`

打开最终文件检查一遍，确认无误即可使用。

---

## 四、常见问题

| 问题 | 解决方法 |
|------|----------|
| 提示"没有发现可处理文件" | 确认文件已放入对应目录（input_forms 或 new_forms） |
| 提示"person_001.json 不存在" | 先完成初始化流程 |
| 端口 8787 被占用 | 工具会自动尝试 8788 |
| 某个字段没填上 | 在网页检查步骤手动补充 |
| 网页打不开 | 确认地址是 `http://127.0.0.1:8787/` |
| 不知道怎么编辑 JSON | 用记事本打开，参照已有格式修改 |
| API 需要开启吗 | 绝大多数情况不需要 |

---

## 五、安全提醒

1. 你的身份证号、手机号、地址等完整数据存储在 `vault\` 和 `candidate_reviews\` 中（JSON 文件）。
2. Markdown 报告中的敏感信息已脱敏处理。
3. 不要把这些目录发给别人或上传到网盘。
4. 备份时注意 `vault\` 中的 JSON 文件包含完整敏感信息。
5. API 默认关闭，需要你手动配置才会启用。
