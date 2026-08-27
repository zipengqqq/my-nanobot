---
name: skill-creator
description: 创建或更新 AgentSkills。设计、组织或打包包含脚本、参考资料和资源文件的技能时使用。
---

# 技能创建器

本技能提供创建高质量技能的指导。

## 关于技能

技能是模块化、自包含的软件包。它们通过提供专门的知识和工作流程来扩展 Agent 的能力。可以把技能理解为特定领域或任务的“上手指南”：它们将通用 Agent 转化为具备特定流程知识的专用 Agent，而这些知识不可能完全预先存在于任何模型中。

### 技能提供的内容

1. 专用工作流程：适用于特定领域的多步骤过程。
2. 工具集成：处理特定文件格式或 API 的说明。
3. 领域专业知识：公司专属知识、数据结构和业务逻辑。
4. 打包资源：用于复杂或重复任务的脚本、参考资料和资源文件。

## 核心原则

### 保持简洁

上下文窗口是共享的有限资源。技能需要与系统提示词、对话历史、其他技能的元数据以及实际用户请求共同占用上下文窗口。

**默认假设：Agent 已经很聪明。** 只添加 Agent 本身不知道的信息。审视每一段内容：“Agent 真的需要这个解释吗？”“这一段是否值得占用这些 token？”

优先提供简洁示例，不要堆砌冗长解释。

### 设定恰当的自由度

根据任务的脆弱程度和变化范围确定指令的具体程度：

**高自由度（文本说明）**：适用于存在多种合理方案、决策依赖上下文，或主要依靠启发式判断的任务。

**中等自由度（伪代码或带参数的脚本）**：适用于已有推荐模式、允许一定变化，或受配置影响的任务。

**低自由度（具体脚本、少量参数）**：适用于操作脆弱且容易出错、需要一致性，或必须遵循固定顺序的任务。

将 Agent 看作在路径上探索：狭窄且危险的路径需要明确护栏（低自由度），开阔区域则允许多条路线（高自由度）。

### 技能的组成

每个技能都必须有一个 `SKILL.md` 文件，也可以附带打包资源：

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (optional)
    ├── scripts/          - Executable code (Python/Bash/etc.)
    ├── references/       - Documentation intended to be loaded into context as needed
    └── assets/           - Files used in output (templates, icons, fonts, etc.)
```

#### `SKILL.md`（必需）

每个 `SKILL.md` 都包括：

- **Frontmatter**：包含 `name` 和 `description` 字段。这两个字段是 Agent 判断何时使用技能的唯一依据，因此必须清楚、完整地说明技能是什么，以及何时触发。
- **正文**：Markdown 格式的指令和指导。只有在技能触发后才会加载。

#### 打包资源（可选）

##### 脚本（`scripts/`）

适用于需要确定性可靠性或经常重复编写的任务的可执行代码，例如 Python 或 Bash。

- **何时包含**：同一段代码被反复编写，或任务需要确定性可靠性时。
- **示例**：`scripts/rotate_pdf.py`，用于旋转 PDF。
- **优点**：节省 token、行为确定，并且可在不加载进上下文的情况下运行。
- **注意**：仍可能需要阅读脚本，以便修补或适配具体环境。

##### 参考资料（`references/`）

需要时加载到上下文、用于指导 Agent 工作的文档和参考材料。

- **何时包含**：技能工作时需要查阅的文档。
- **示例**：`references/finance.md`（财务数据结构）、`references/mnda.md`（公司保密协议模板）、`references/policies.md`（公司政策）。
- **适用场景**：数据库结构、API 文档、领域知识、公司政策和详细工作流程。
- **优点**：使 `SKILL.md` 保持精简，只在需要时加载资料。
- **最佳实践**：若文件较大（超过 1 万词），应在 `SKILL.md` 中提供 `grep` 搜索模式。说明何时应先使用默认的 `grep(output_mode="files_with_matches")`、`grep(output_mode="count")`、`grep(fixed_strings=true)` 或 `head_limit` / `offset` 分页。
- **避免重复**：信息应只放在 `SKILL.md` 或参考文件之一。除非属于真正核心的内容，否则优先放入参考文件。`SKILL.md` 仅保留必要的流程指令和工作指导，详细参考材料、数据结构和示例放入参考文件。

##### 资源文件（`assets/`）

不应加载到上下文，而应在 Agent 输出中使用的文件。

- **何时包含**：技能需要在最终输出中使用文件时。
- **示例**：`assets/logo.png`（品牌资源）、`assets/slides.pptx`（演示模板）、`assets/font.ttf`（字体）。
- **适用场景**：模板、图像、图标、样板代码、字体和可复制或修改的示例文档。
- **优点**：将输出资源与说明分开，使 Agent 可以使用文件而不占用上下文。

#### 不应放入技能的内容

技能只能包含直接支持其功能的必要文件。不要创建多余文档或辅助文件，包括：

- `README.md`
- `INSTALLATION_GUIDE.md`
- `QUICK_REFERENCE.md`
- `CHANGELOG.md`
- 等。

技能只应保存 AI Agent 完成任务所需的信息。不要包含创建过程、安装步骤、面向用户的说明或其他无关辅助上下文，以免造成冗余和混乱。

### 渐进式加载原则

技能采用三级加载机制，以高效管理上下文：

1. **元数据（`name` 和 `description`）**：始终在上下文中，约 100 词。
2. **`SKILL.md` 正文**：技能触发时加载，少于 5 千词。
3. **打包资源**：按需加载；脚本可不读入上下文而直接执行，因此容量不受限。

`SKILL.md` 正文应保留核心内容，并控制在 500 行以内以避免上下文膨胀。接近该长度时，应拆分到其他文件。拆分后必须从 `SKILL.md` 清楚引用这些文件，并说明何时读取它们。

### 渐进式加载模式

#### 模式 1：高层指南配合参考资料

```markdown
# PDF Processing

## Creating documents

Use docx-js for new documents. See [DOCX-JS.md](DOCX-JS.md).

## Editing documents

For simple edits, modify the XML directly.

**For tracked changes**: See [REDLINING.md](REDLINING.md)
**For OOXML details**: See [OOXML.md](OOXML.md)
```

#### 模式 2：按领域组织

对于支持多个领域的技能，应按领域组织，避免加载无关上下文：

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── reference/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    ├── product.md (API usage, features)
    └── marketing.md (campaigns, attribution)
```

当用户询问销售指标时，只加载 `sales.md`。同样，对于支持多个框架或变体的技能，也应按变体组织：

```
cloud-deploy/
├── SKILL.md (workflow + provider selection)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

当用户选择 AWS 时，只加载 `aws.md`。

#### 模式 3：条件式细节

先展示基本内容，再链接高级内容：

```markdown
# DOCX Processing

## Creating documents

Use docx-js for new documents. See [DOCX-JS.md](DOCX-JS.md).

## Editing documents

For simple edits, modify the XML directly.

**For tracked changes**: See [REDLINING.md](REDLINING.md)
**For OOXML details**: See [OOXML.md](OOXML.md)
```

**重要准则：**

- 不要使用层级过深的参考资料。所有参考文件都应由 `SKILL.md` 直接链接。
- 超过 100 行的参考文件应在顶部包含目录，便于预览时了解全部范围。

## 技能创建流程

技能创建按以下步骤进行：

1. 通过具体示例理解技能。
2. 规划可复用的技能内容（脚本、参考资料和资源）。
3. 初始化技能（运行 `init_skill.py`）。
4. 编辑技能（实现资源并编写 `SKILL.md`）。
5. 打包技能（运行 `package_skill.py`）。
6. 根据实际使用情况迭代。

按顺序执行这些步骤，只有在明确不适用时才跳过。

### 技能命名

- 只使用小写字母、数字和连字符；将用户提供的标题规范化为短横线命名，例如“Plan Mode”使用 `plan-mode`。
- 名称不超过 64 个字符（字母、数字和连字符）。
- 优先使用简短、动词开头且描述动作的名称。
- 按工具添加命名空间可提升清晰度或触发准确性时再使用，例如 `gh-address-comments`、`linear-address-issue`。
- 技能目录名称必须与技能名称完全一致。

### 第 1 步：通过具体示例理解技能

除非技能的使用方式已非常清楚，否则不要跳过本步骤；即使是已有技能，具体示例也仍然有价值。

创建高质量技能前，应通过具体示例清楚理解其用途。示例可由用户直接提供，也可由 Agent 提出并经用户确认。

例如，创建图像编辑器技能时，可以询问：

- “该图像编辑器技能需要支持哪些能力？编辑、旋转，还是其他功能？”
- “能否举例说明你会如何使用该技能？”
- “我设想用户可能会说‘帮我去掉图中的红眼’或‘旋转这个图像’。还有其他希望覆盖的表达吗？”
- “用户说什么样的话时应触发该技能？”

为避免一次提问过多，不要在一条消息中询问太多问题。先问最重要的问题，再根据需要追问。

当技能能够支持的具体用法已足够明确时，结束本步骤。

### 第 2 步：规划可复用的技能内容

要将具体示例转化为高质量技能，请针对每个示例：

1. 思考从零开始如何完成该示例。
2. 识别重复执行这些流程时会有帮助的脚本、参考资料和资源文件。

例如，分析“帮助我旋转这个 PDF”会得到：

1. 旋转 PDF 需要反复编写相似代码。
2. `scripts/rotate_pdf.py` 可保存为可复用脚本。

分析“构建待办应用”或“构建追踪步数的仪表盘”会得到：

1. 前端应用经常需要重复编写样板代码。
2. `assets/hello-world/` 模板可保存样板文件。

分析“今天有多少用户登录 BigQuery？”会得到：

1. 查询 BigQuery 时需要反复了解表结构和关系。
2. `references/schema.md` 可记录表结构。

据此列出要包含的可复用资源：脚本、参考资料和资源文件。

### 第 3 步：初始化技能

此时开始实际创建技能。

仅当正在迭代或打包已有技能时才跳过本步骤；这种情况直接进入下一步。

创建新技能时，必须运行 `init_skill.py`。该脚本会生成包含必要结构的技能目录模板，能提高效率并避免遗漏。

在 nanobot 中，自定义技能应放在活动工作区的 `skills/` 目录下，以便运行时自动发现，例如 `<workspace>/skills/my-skill/SKILL.md`。

用法：

```bash
scripts/init_skill.py <skill-name> --path <output-directory> [--resources scripts,references,assets] [--examples]
```

示例：

```bash
scripts/init_skill.py my-skill --path ./workspace/skills
scripts/init_skill.py my-skill --path ./workspace/skills --resources scripts,references
scripts/init_skill.py my-skill --path ./workspace/skills --resources scripts --examples
```

该脚本会：

- 在指定位置创建技能目录。
- 生成包含正确 frontmatter 和 `TODO` 占位符的 `SKILL.md` 模板。
- 按需创建资源目录。
- 在设置 `--examples` 时加入示例文件。

初始化后，自定义 `SKILL.md` 并添加所需资源。若使用了 `--examples`，应替换或删除占位文件。

### 第 4 步：编辑技能

编辑新生成或已有的技能时，记住它是供另一个 Agent 实例使用的。应包含对该实例有帮助且不显而易见的信息。思考哪些流程知识、领域知识或可复用资源能帮助它完成任务。

#### 学习经过验证的设计模式

根据技能需求查阅下列指南：

- **多步骤过程**：参阅 `references/workflows.md`，了解顺序流程和条件逻辑。
- **特定输出格式或质量标准**：参阅 `references/output-patterns.md`，了解模板和示例模式。

这些文件提供了成熟的技能设计最佳实践。

#### 先实现可复用内容

先实现上一步识别出的 `scripts/`、`references/` 和 `assets/`。这一步可能需要用户提供输入，例如品牌规范技能需要用户提供品牌资源或模板放入 `assets/`，或提供文档放入 `references/`。

新增脚本必须实际运行测试，以确认没有错误且输出符合预期。若有大量相似脚本，测试有代表性的样本即可，在可信度和投入之间取得平衡。

如果使用了 `--examples`，删除所有不需要的占位文件。只创建实际需要的资源目录。

#### 更新 `SKILL.md`

**编写规则：** 始终使用祈使句或不定式形式。

##### Frontmatter

在 YAML frontmatter 中写入 `name` 和 `description`：

- `name`：技能名称。
- `description`：技能的主要触发机制，帮助 Agent 理解其用途和使用时机。
  - 同时包含技能能做什么，以及具体触发场景。
  - 所有“何时使用”的内容都应写在这里，不要只写在正文。正文只有在技能触发后才会加载。
  - `docx` 技能的示例描述：`Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. Use when the agent needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks`

保持 frontmatter 精简。在 nanobot 中，必要时还支持 `metadata` 和 `always`，但没有实际需要时不要添加额外字段。

##### 正文

编写使用技能及其打包资源的说明。

### 第 5 步：打包技能

技能开发完成后，必须打包为可分发的 `.skill` 文件以交付给用户。打包过程会先自动验证技能，确保其符合要求：

```bash
scripts/package_skill.py <path/to/skill-folder>
```

可选地指定输出目录：

```bash
scripts/package_skill.py <path/to/skill-folder> ./dist
```

该脚本将：

1. **自动验证技能**，检查 YAML frontmatter 格式和必填字段、命名规范和目录结构、描述的完整性与质量，以及文件组织和资源引用。
2. **在验证通过后打包技能**，生成以技能名命名的 `.skill` 文件，例如 `my-skill.skill`。该文件是扩展名为 `.skill` 的 zip 文件，保留原有目录结构。

安全限制：只要技能中存在符号链接，打包就会拒绝并失败。

### 第 6 步：迭代

技能经过真实任务的使用后，用户可能会要求改进，尤其是刚使用过时最容易发现问题。

迭代流程：

1. 在真实任务中使用技能。
2. 发现困难或低效之处。
3. 判断应如何更新 `SKILL.md` 或打包资源。
4. 实现并测试改进。
