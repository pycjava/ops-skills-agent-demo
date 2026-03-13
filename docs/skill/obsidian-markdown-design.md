# Obsidian Markdown 技能设计说明

## 概述

`obsidian-markdown` 为 Agent 提供 **Obsidian Flavored Markdown** 的专用语法知识，使其输出的 `.md` 文档可以直接用于 Obsidian 笔记库，而不是停留在普通 Markdown 层面。

这个 skill 主要解决“文档能写出来”和“文档适合 Obsidian 使用”之间的差异，重点补足内部链接、嵌入、属性、标签、Callout、Mermaid 和数学公式等 Obsidian 特有能力。

## 架构

```text
用户："帮我整理成 Obsidian 笔记"
  → Agent 先按 Markdown 组织内容结构
  → 再用 Obsidian 语法补充 wikilink / embed / frontmatter / callout
  → 输出可直接保存为 .md 的笔记内容
```

## 设计要点

- **语法覆盖完整**：同时覆盖 CommonMark、GitHub Flavored Markdown、LaTeX 公式和 Obsidian 扩展语法。
- **知识连接优先**：支持 `[[note]]`、`[[note#heading]]`、`[[note#^block-id]]` 等 wikilink，适合知识库互链。
- **嵌入能力丰富**：支持 `![[note]]`、图片、音频、PDF、块引用和搜索结果嵌入。
- **结构化表达强**：支持 Callout、任务列表、表格、脚注、注释和 Frontmatter 属性。
- **知识管理友好**：通过 tags、properties、内部链接把一篇文档组织成可检索、可导航的 Obsidian 笔记。
- **零脚本依赖**：这是一个纯文档型 skill，不依赖外部脚本或 API，主要提供格式规范与写作约束。

## 适用场景

- 用户明确说要生成 Obsidian 笔记、知识库条目或双向链接文档。
- 需要把分析结果整理成可长期沉淀的 Markdown 页面。
- 需要在 Markdown 中使用 Callout、嵌入、Frontmatter、Mermaid 或公式。

## 目录结构

```text
backend/skills/obsidian-markdown/
└── SKILL.md                    # Obsidian 语法规范与示例
```
