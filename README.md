# AiOne Skills

我日常工作中使用的 Agent Skills，直接取自 `.claude` 目录。小巧、可组合、可按需修改。

## 快速开始

1. 运行 skills 安装器：

```bash
npx skills@latest add ai-one-tech/aione-skills
```

2. 选择想安装的 skills，以及要安装到哪些 Coding Agent。

也可以手动安装：把 `skills/<name>/` 整个目录复制到项目的 `.claude/skills/`（或用户级的 `~/.claude/skills/`）下即可。

## 目录结构

```
skills/
└── <skill-name>/
    ├── SKILL.md      # 必需：frontmatter（name、description）+ 正文
    └── ...           # 可选：脚本、参考文档等 skill 依赖的辅助文件
```

每个 skill 一个目录，入口是 `SKILL.md`。`description` 决定 Agent 何时触发该 skill，因此要写清楚「做什么」与「什么时候用」。

## Skills 清单

### 开发工具

- **[idea-run-to-openidea](./skills/idea-run-to-openidea/SKILL.md)** — 把 IntelliJ IDEA 的 Spring Boot 启动配置（`.run/*.run.xml`）转换成 OpenIDEA 的 `.openidea/run.toml`，内联 env 文件内容，并提醒敏感信息与生产环境风险。

## 新增 Skill

1. 在 `skills/` 下新建 `<skill-name>/SKILL.md`，frontmatter 至少包含 `name` 和 `description`。
2. 正文保持精简：只写 Agent 不知道、又容易做错的内容（步骤、字段映射、限制）。
3. 把 skill 添加到上面的「Skills 清单」，格式：`- **[name](./skills/name/SKILL.md)** — 一句话说明`。

## 许可证

[Apache License 2.0](./LICENSE)
