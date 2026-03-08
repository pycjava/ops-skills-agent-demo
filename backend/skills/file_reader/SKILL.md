---
name: file_reader
description: "读取指定路径的本地文件内容并返回。支持文本文件，最大 100KB。"
parameters:
  properties:
    path:
      type: string
      description: "要读取的项目内文件路径，使用相对于 backend/ 的路径或 glob 返回的 '/...' 虚拟路径，例如 'metric_data/instance_data_cpu.json' 或 '/metric_data/instance_data_cpu.json'"
  required:
    - path
---

# 文件读取器

读取本地文件的内容。用户可能会要求你查看特定文件的内容。

## 用法

- 优先使用相对于 `backend/` 的项目路径
- 如果路径来自 `glob` 返回结果，可以直接复用 `/...` 形式的虚拟路径
- 不要使用 Windows 绝对路径、`~` 路径、`/backend/...` 或 `/memories/../...`
- 自动处理中文编码
- 文件大小限制为 100KB

## 使用提示

- 当用户提到"读取"、"查看"、"打开"某个文件时使用
- 如果文件是代码文件，读取后可以结合你的知识进行解释
