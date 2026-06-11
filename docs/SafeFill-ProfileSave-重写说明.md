# SafeFill-ProfileSave v2 重写说明

## 旧逻辑问题

1. 无重复检测：用户多次运行保存同一份 `confirmed_profile.json` 会生成 `person_001.json`、`person_002.json`、`person_003.json`
2. 未归档：保存后 `confirmed_profile.json` 留在原地，下次运行又生成新文件

## 新逻辑

### 保存前检查

1. `confirmed_profile.json` 是否存在 → JSON 是否合法 → 是否有 `confirmed: true` 字段
2. 字段名是否在允许列表中
3. 与已有 `person_*.json` 比较

### 重复检测规则

- name + major + department 都相同 → 重复
- name + research_area 都相同 → 重复
- 所有字段值都匹配某个已有 profile → 重复

### 重复时

- 不新增 person 文件
- 终端提示与哪个文件重复
- 日志记录

### 非重复时

1. 生成 `person_XXX.json`
2. 归档 `confirmed_profile.json` → `saved_confirmed_profiles\confirmed_profile_saved_时间戳.json`

## 测试结果

当前 `person_001.json` 和 `person_002.json` 内容相同，`confirmed_profile.json` 与 `person_001.json` 重复。v2 正确检测并停止。
