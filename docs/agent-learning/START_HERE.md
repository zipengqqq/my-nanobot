# START HERE

如果你是一个新会话中的 AI coding agent，并且用户要继续这个“基于 `nanobot` 学 agent，并把 `my_agent` 从最小同构版推进到完整 agent 框架”的任务，请先按顺序阅读下面 3 份文件：

1. [architecture-map.md](/Users/penn/work/nanobot/docs/agent-learning/architecture-map.md)
2. [build-plan.md](/Users/penn/work/nanobot/docs/agent-learning/build-plan.md)
3. [progress-log.md](/Users/penn/work/nanobot/docs/agent-learning/progress-log.md)

读取后再继续工作。

## 你必须遵守的规则

1. 这 3 份文件是当前学习路线和架构边界的事实来源。
2. 不要跳过它们，直接自由发挥实现一个 agent。
3. 如果用户没有明确改变方向，就按 `build-plan.md` 的 phase 顺序推进。
4. 每完成一个阶段或一个重要节点，都要更新 `progress-log.md`。

## 当前状态

- 当前任务方向：基于 `nanobot` 架构，把 `my_agent` 发展成完整 agent 框架
- 当前方法：保留第一阶段已经验证完成的核心主链路，在此基础上进入第二阶段产品化扩展
- 当前进度：
  - 第一阶段已完成：最小同构版 `Phase 0-6`
  - 当前已不再是“最小 CLI agent 练手项目”，而是“完整 agent 框架的起始版本”
- 当前补充文档：
  - [phase6-nanobot-comparison.md](/Users/penn/work/nanobot/docs/agent-learning/phase6-nanobot-comparison.md)
- 当前下一步：如果要继续，不要再按“最小 agent 补课”思路零散加功能，而要先判断该工作属于第二阶段的哪一类能力建设：
  - 工具体系
  - 统一入口 / API
  - runtime 可观测性
  - memory / compaction
  - 多渠道 / MCP / subagent 等产品能力
