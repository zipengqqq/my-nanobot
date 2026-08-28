---
name: memory
description: 使用由 Dream 管理的知识文件构成的双层记忆系统。
always: true
---

# 记忆

## 结构

- `my_agent/storage/SOUL.md`：Bot 的人格和沟通风格。**由 Dream 管理。** 不要编辑。
- `my_agent/storage/USER.md`：用户资料和偏好。**由 Dream 管理。** 不要编辑。
- `my_agent/storage/memory/MEMORY.md`：长期事实（项目背景、重要事件）。**由 Dream 管理。** 不要编辑。
- `my_agent/storage/memory/history.jsonl`：仅追加的 JSONL 文件，不会整文件加载到上下文。优先使用内置 `grep` 工具搜索。

## 搜索过往事件

`my_agent/storage/memory/history.jsonl` 采用 JSONL 格式，每行是一个包含 `cursor`、`timestamp` 和 `content` 的 JSON 对象。

- 宽泛搜索时，先使用 `grep(..., path="my_agent/storage/memory", glob="*.jsonl", output_mode="count")`，或先使用默认的 `files_with_matches` 模式，再展开完整内容。
- 需要精确匹配行时，使用 `output_mode="content"`，并配合 `context_before` / `context_after`。
- 对字面时间戳或 JSON 片段使用 `fixed_strings=true`。
- 使用 `head_limit` / `offset` 对较长的历史记录分页。
- 只有内置搜索无法表达需求时，才将 `exec` 作为最后的兜底方案。

示例（将 `keyword` 替换为实际关键词）：

- `grep(pattern="keyword", path="my_agent/storage/memory/history.jsonl", case_insensitive=true)`
- `grep(pattern="2026-04-02 10:00", path="my_agent/storage/memory/history.jsonl", fixed_strings=true)`
- `grep(pattern="keyword", path="my_agent/storage/memory", glob="*.jsonl", output_mode="count", case_insensitive=true)`
- `grep(pattern="oauth|token", path="my_agent/storage/memory", glob="*.jsonl", output_mode="content", case_insensitive=true)`

## 重要事项

- **不要编辑 `SOUL.md`、`USER.md` 或 `MEMORY.md`。** 它们由 Dream 自动管理。
- 发现过时信息时无需手动修正，Dream 下次运行时会更新。
- 用户可通过 `/dream` 命令手动触发 Dream 整理。
