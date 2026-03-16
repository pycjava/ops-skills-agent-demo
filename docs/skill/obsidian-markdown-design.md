# Obsidian Markdown Skill 设计说明

## 1. Skill 定位

`obsidian-markdown` 用于创建和编辑 Obsidian Flavored Markdown。它关注的不是“任意 Markdown”，而是：

- wikilinks
- embeds
- callouts
- frontmatter / properties
- tags
- 数学公式
- Obsidian 风格的任务与文档组织

## 2. 设计目标

- 让 Agent 输出的 Markdown 能直接在 Obsidian 中良好工作。
- 避免把 Obsidian 文档误写成普通 Markdown，丢失语义特性。
- 为巡检报告、知识笔记、长期记忆文档提供统一的 Obsidian 风格能力。

## 3. 适用场景

该 Skill 适用于：

- 用户明确提到 Obsidian。
- 需要生成适合知识库沉淀的 Markdown 文档。
- 需要使用 `[[wikilink]]`、callout、frontmatter、embed 等语法。

不适用于：

- 单纯的纯文本回复。
- 不需要 Obsidian 语义的普通代码注释或 README 微调。

## 4. 核心语法域

该 Skill 覆盖的语法域包括：

### 4.1 链接与引用

- `[[Note]]`
- `[[Note|Alias]]`
- `[[Note#Heading]]`
- `[[Note#^block-id]]`

### 4.2 嵌入

- `![[Note]]`
- `![[image.png]]`
- `![[document.pdf#page=3]]`

### 4.3 Callout

- `> [!note]`
- `> [!tip]`
- 可折叠 callout

### 4.4 文档属性

- frontmatter / properties
- 标签
- 任务列表
- 数学公式与代码块

## 5. 标准写作流程

```text
确认目标文档类型
  -> 判断是否需要 frontmatter / tags / wikilinks
  -> 按 Obsidian 语法组织标题、引用、callout
  -> 检查链接、嵌入和代码块是否符合语法
  -> 输出为可直接保存的 Markdown
```

设计重点：

- 先明确文档类型，再选择语法，而不是把所有 Obsidian 特性都堆进去。

## 6. 在本项目中的作用

该 Skill 虽然主要绑定给 `general` Agent，但它对整个项目都很重要，因为：

- 报告类产物最终通常以 Markdown 形式保存。
- `/memories/` 下的很多文档天然适合 Obsidian 风格组织。
- 其他领域 Skill 在需要“保存为 Markdown”时，通常会借鉴该 Skill 的格式约定。

## 7. 与报告类 Skill 的关系

`obsidian-markdown` 本身不定义数据库巡检或管理报告模板，但会影响这些场景的输出方式：

- 当其他 Skill 需要把结果写成 Markdown 文件时，会继承“语法合法、结构清晰、适合知识库阅读”的要求。
- 但如果某个 Skill 已有更强模板约束，应以该模板为准，而不是自由发挥 Obsidian 语法。

## 8. 常见设计原则

- 结构优先于花哨语法。
- 只有在真正有价值时才使用 wikilinks 或 embeds。
- Callout 适用于强调结论、风险或行动建议。
- 若文档要长期维护，应优先加入 frontmatter、标题层次和标签。

## 9. 失败场景与回退

- 若用户只要普通 Markdown，可退回基础 Markdown 风格，不强行加入 Obsidian 特性。
- 若输出目标有固定模板，应优先满足模板，而不是套用通用文档习惯。
- 若文件将被外部系统消费，应谨慎使用仅 Obsidian 可识别的扩展语法。

## 10. 设计取舍

- 使用 Obsidian 特性可以增强知识组织能力，但会降低对纯 Markdown 渲染器的通用性。
- 将该 Skill 作为独立能力保留，能让 Markdown 产物保持一致，但也要求维护者明确区分“普通 Markdown”和“Obsidian Markdown”。
