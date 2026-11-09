---
name: idea-run-to-openidea
description: 把 IntelliJ IDEA 的 Spring Boot 启动配置（.run/*.run.xml）转换成 OpenIDEA 的 .openidea/run.toml。用户提到 OpenIDEA 识别不了 IDEA 启动配置、要迁移/同步启动配置、run.toml 时使用。
---

# IDEA 启动配置 → OpenIDEA run.toml

OpenIDEA 不读 `.idea/workspace.xml` 和 `.run/*.run.xml`，只读 `.openidea/run.toml`；env 文件通过 `env-files = ["/abs/path.env"]` 直接引用，不再内联内容。

## 步骤

1. **确认 run.toml 格式**：
   - `<项目根>/.openidea/run.toml`（与 `.run` 目录同级）**不存在时脚本会自动创建**（含 `.openidea` 目录），无需用户先手建。
   - 已存在则先看里面用户手建的示例，格式以它为准。
   - 字段格式参考 `references/run.toml.example`（mock 脱敏数据）。OpenIDEA 对错误字段是静默忽略，不要猜字段名。
2. **JRE（JAVA_HOME）由脚本自动读取，不要猜路径**，优先级：
   1. `--jre` 显式参数（可选）；
   2. `.run/*.run.xml` 的 `ALTERNATIVE_JRE_PATH`（仅 `ALTERNATIVE_JRE_PATH_ENABLED=true`；值可为路径或 JDK 名称）；
   3. `.idea/misc.xml` 的 `project-jdk-name`，经 IDEA 全局 `jdk.table.xml`（`~/Library/Application Support/JetBrains/*/options/` 或 `~/.config/JetBrains/*/options/`）解析为 `homePath`；
   4. 都读不到则 `command` 与 `params.jre` 留空，预览里会标注 `未找到,留空`，如实告知用户。
3. **预览**：
   ```
   python3 -I ~/.claude/skills/idea-run-to-openidea/convert.py --project <项目根> --dry-run
   ```
   输出只列配置名、profile、JRE 路径及来源、env 键名和是否含敏感键，不打印 env 取值。run.toml 不存在时会提示将新建。
4. **执行**：去掉 `--dry-run`；可用 `--only "名称"` 限定。同名配置会跳过，不覆盖用户手建的条目。
5. **提醒用户**（每次必说）：
   - run.toml 的 `env` 可能含手动设置的敏感值，且 `env-files` 写的是本机绝对路径，`.openidea/.gitignore` 默认不忽略它，建议加 `/run.toml`。
   - 带 prod 的配置会连生产环境，转换前要用户明确要求。
   - XML 里的 profile 与用户手建示例不一致时，以用户手建的为准，并告知差异。

## 字段映射

| IDEA (.run.xml) | run.toml |
|---|---|
| `name` | `name` |
| `ACTIVE_PROFILES` | `args` 里的 `--spring.profiles.active=`、`params.activeProfiles` |
| `SPRING_BOOT_MAIN_CLASS` | `args` 中主类、`params.mainClass` |
| `module name` | `module`、`params.module` |
| `envFilePaths`（env 文件引用） | `env-files = ["<绝对路径>"]`（不读取文件内容） |
| `<envs><env name value/>`（手动单项变量） | `env = { K = "V" }` |
| `VM_PARAMETERS` / `PROGRAM_PARAMETERS` | `params.vmOptions` / `params.programArgs`；同时拆分后放进 `args`（VM 参数在 `-cp` 之前，程序参数在末尾） |

固定值：`kind = "spring-boot"`、`debug-adapter = "java-debug"`、`classpath = "${classpath}"`、`command = <JAVA_HOME>/bin/java`（JAVA_HOME 为空时 `command` 也留空）；`id` 由配置名哈希生成（`user:` + 9 位）。

## 限制

- 只处理 `SpringBootApplicationConfigurationType`；Application、Maven、JUnit 等类型跳过。
- `$PROJECT_DIR$` 之外的路径变量不展开（JRE 路径额外支持 `$USER_HOME$`）；env 文件不存在会直接报错退出。
- JRE 名称只在 JetBrains 全局 `jdk.table.xml` 里查（不含 Android Studio 等其他目录）；名称查不到就留空，留空的 `command` 需用户在 OpenIDEA 里补全。
- 不会读取已有 run.toml 来推断格式或 JRE，同名配置仅按 `name` 跳过。
- 未在真实 OpenIDEA 里验证 `id` 的格式要求。
