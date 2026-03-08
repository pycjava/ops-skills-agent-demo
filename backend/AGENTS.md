# Deprecated

`backend/AGENTS.md` 不再承载 DBA Agent 的运行时 prompt 内容。

- `dba` Agent 的专属提示词位于 `backend/prompts/dba.md`
- 公共基础提示词位于 `backend/prompts/base.md`
- 实际装配关系以 `backend/agent_profiles.py` 中的 `prompt_paths` 为准

如需维护 DBA prompt，请更新上述文件，不要在此处继续添加行为规则或运行时说明。
