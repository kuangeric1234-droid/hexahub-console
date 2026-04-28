# Custom Skills

Project-specific skill files that override or supplement the external Corey Haines library.

## Override behaviour
A file named `{skill_name}.md` here takes priority over any skill of the same name in `marketing_external/skills/{skill_name}/SKILL.md`. This is the localisation mechanism: drop a replacement file here to swap in a China-native version without touching agent code.

## Format
Follow the structure of skills in `marketing_external/` — markdown with sections for platform overview, core patterns, examples, and compliance notes.

## Current files

| File | Status | Notes |
|---|---|---|
| `xiaohongshu-content.md` | ⚠️ PLACEHOLDER | Needs China-native marketing expertise |
| `wechat-moments-content.md` | ⚠️ PLACEHOLDER | Needs China-native marketing expertise |

⚠️ Placeholders are intentionally minimal. Agents will function but output quality depends on how thorough these files become. Fill them before relying on Chinese-platform agents in production. Consider commissioning a Chinese marketing specialist or building from internal campaign learnings.
