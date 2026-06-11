# SafeFill

一个完全本地化、默认离线的表格半自动填写工具。帮你从以前填过的旧表格中提取个人信息，保存到本地加密资料库，再用资料库自动填写新表格。

## 这个工具做什么

> 如果你每年要填几十份差不多的表格（项目申报表、人员信息表、考核表……），每次都要重复写姓名、身份证号、单位、学历、职称……这个工具可以帮你省掉 80% 的重复劳动。

**核心思路**：从你确认过的旧表格中提取信息 → 保存到本地资料库 → 新表格自动填写 → 你在浏览器里检查 → 导出最终文件。

**安全第一**：全程本地运行，默认不联网。你的资料只在你自己的电脑上。

## 一句话安全原则

> **你的身份证号、手机号、住址、证件照永远不会离开你的电脑。**

## 支持格式

### 旧资料输入

| 格式 | 支持范围 |
|------|----------|
| .docx | 段落、表格、Word 文本框 |
| .xlsx | 表格 |
| .pdf | 需 MinerU |

### 待填写空白表

| 格式 | 支持范围 |
|------|----------|
| .docx | 表格、上下行结构、简单 Word 文本框 |
| .xlsx | 表格 |
| .pdf | 暂不支持填写 |

> PDF 旧资料提取需要安装 [MinerU](https://github.com/opendatalab/MinerU)。安装脚本：`.\tools\install_mineru.ps1`（需联网）。不安装时 docx/xlsx 流程不受影响。详见 `docs\MinerU安装说明.md`。

## 第一次使用（完整流程）

1. **准备旧表格**：把以前填过的 .docx / .xlsx 表格复制到 `input_forms\`
2. **提取信息**：运行 `python app\extract_candidates.py`
3. **检查确认**：打开 `candidate_reviews\` 中的 Markdown 文件检查
4. **保存资料**：运行 `python app\save_confirmed_profile.py`，按提示确认是否写入 `vault\profile.json`
5. **放入新表**：把要填的新表格复制到 `new_forms\`
6. **填表检查**：运行 `python app\form_review.py`，浏览器会自动打开 `http://127.0.0.1:8787/`（如未打开请手动访问）
7. **保存网页检查结果**：在网页中检查、修改并点击“保存检查结果”
8. **导出最终**：运行 `python app\export_final.py`，在 `final_outputs\` 中取文件
9. **可选清理**：运行 `python app\cleaner.py preview` 预览可清理的临时隐私文件

## 日常使用流程

如果资料库已经建好，日常只需要：

1. 新表格放入 `new_forms\`
2. 运行 `form_review.py` 自动填写，浏览器会自动打开网页检查
3. 在网页点击“保存检查结果”
4. 运行 `export_final.py` 导出最终文件

## 输出文件在哪

| 阶段 | 输出目录 | 内容 |
|------|----------|------|
| 提取候选 | `candidate_reviews\` | 候选信息检查文件 |
| 保存资料 | `vault\profile.json` | 你的唯一正式个人资料库 |
| 自动填写 | `draft_outputs\` + `filling_reports\` | 草稿 + 报告 |
| 网页检查 | `review_results\` | 确认结果 |
| 最终导出 | `final_outputs\` + `final_reports\` | 最终文件 + 报告 |

## API 使用

SafeFill 支持 API-first：提取旧资料和理解空白表格时，可以优先交给大模型处理。上传到 GitHub 后，用户下载项目不需要把 API Key 写进项目文件。

SafeFill 会自动识别这些环境变量：

- `SAFEFILL_API_KEY` / `SECURE_FORM_API_KEY`
- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`
- 可选：`SAFEFILL_API_ENDPOINT`、`OPENAI_BASE_URL`、`DEEPSEEK_BASE_URL`
- 可选：`SAFEFILL_API_MODEL`、`OPENAI_MODEL`、`DEEPSEEK_MODEL`

用户只需要在本机设置环境变量，并确认 `SAFEFILL_ACCEPT_API_RISK=true`，即可让 SafeFill 自动找到 API。API Key 不会保存到项目文件中。

检查命令：

```powershell
python D:\SafeFill\app\api_assist.py check
```

详见 `docs\第5阶段使用说明.md`。

## 遇到问题看哪些文档

| 问题 | 文档 |
|------|------|
| 不知道怎么开始 | `docs\正式Skill使用说明.md` |
| 想知道每步运行什么命令 | `docs\命令入口清单.md` |
| 安全相关 | `docs\安全设计.md` |
| API 相关 | `docs\第5阶段API安全设计.md` |
| 我的数据在哪里 | `docs\用户数据保护说明.md` |

## 重要提醒

- ⚠️ **不要把 `vault\`、`input_forms\`、`new_forms\` 目录发给别人**——里面可能包含你的个人信息。
- ⚠️ **备份时注意**——`vault\` 中的 JSON 文件包含完整敏感信息（身份证号、手机号等）。
- ⚠️ **API 会发送资料给大模型服务商**——启用前请确认你接受对应服务商的数据使用风险。
