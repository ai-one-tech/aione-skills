---
name: idea-run-to-openidea
description: 把 IntelliJ IDEA 的 Spring Boot 启动配置（.run/*.run.xml）转换成 OpenIDEA 的 .openidea/run.toml。用户提到 OpenIDEA 识别不了 IDEA 启动配置、要迁移/同步启动配置、run.toml 时使用。
---

# IDEA 启动配置 → OpenIDEA run.toml

OpenIDEA 不读 `.idea/workspace.xml` 和 `.run/*.run.xml`，只读 `.openidea/run.toml`；且**不支持引用 env 文件**，必须把 env 内容内联进 toml。

## 步骤

1. **确认 run.toml 格式**：看 `.openidea/run.toml` 里是否已有用户在 OpenIDEA 手建的示例。没有就让用户先建一个最简 Spring Boot 配置（主类 + 模块），保存后再继续。格式有疑问不要猜，OpenIDEA 对错误字段是静默忽略。
2. **确认 JAVA_HOME**：取示例里 `params.jre` 的值（不要自己猜路径）。
3. **预览**：
   ```
   python3 -I ~/.claude/skills/idea-run-to-openidea/convert.py --project <项目根> --jre <JAVA_HOME> --dry-run
   ```
   输出只列配置名、profile、env 键名和是否含敏感键，不打印取值。
4. **执行**：去掉 `--dry-run`；可用 `--only "名称"` 限定。同名配置会跳过，不覆盖用户手建的条目。
5. **提醒用户**（每次必说）：
   - run.toml 内联了 Nacos 密码等敏感值，`.openidea/.gitignore` 默认不忽略它，建议加 `/run.toml`。
   - 带 prod 的配置会连生产环境，转换前要用户明确要求。
   - XML 里的 profile 与用户手建示例不一致时，以用户手建的为准，并告知差异。

## 字段映射

| IDEA (.run.xml) | run.toml |
|---|---|
| `name` | `name` |
| `ACTIVE_PROFILES` | `args` 里的 `--spring.profiles.active=`、`params.activeProfiles` |
| `SPRING_BOOT_MAIN_CLASS` | `args` 中主类、`params.mainClass` |
| `module name` | `module`、`params.module` |
| `envFilePaths`（读取文件内容） | `env = { K = "V" }` |
| `VM_PARAMETERS` / `PROGRAM_PARAMETERS` | `params.vmOptions` / `params.programArgs` |

固定值：`kind = "spring-boot"`、`debug-adapter = "java-debug"`、`classpath = "${classpath}"`、`command = <JAVA_HOME>/bin/java`；`id` 由配置名哈希生成（`user:` + 9 位）。

## 限制

- 只处理 `SpringBootApplicationConfigurationType`；Application、Maven、JUnit 等类型跳过。
- `$PROJECT_DIR$` 之外的路径变量不展开；env 文件不存在会直接报错退出。
- 未在真实 OpenIDEA 里验证 `id` 的格式要求。
