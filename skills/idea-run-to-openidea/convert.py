#!/usr/bin/env python3
"""把 IDEA 的 .run/*.run.xml (Spring Boot 类型) 转成 OpenIDEA 的 .openidea/run.toml。

用法: python3 -I convert.py --project <项目根> [--jre <JAVA_HOME>] [--only 名称] [--dry-run]
- .openidea/run.toml 不存在时自动创建（与 .run 同级）
- JRE 优先级: --jre > run.xml 的 ALTERNATIVE_JRE_PATH > .idea/misc.xml 项目 SDK(经 jdk.table.xml) > 留空
- 已存在同名配置会跳过，不覆盖用户手建的条目
- envFilePaths 指向的 env 文件会被读取，内容内联到 env 表（OpenIDEA 不支持引用 env 文件）
- run.xml 中手动设置的单项环境变量（<envs><env/>）也会转换，同名时覆盖 env 文件中的值（与 IDEA 一致）
- env 取值只写入文件，不打印
"""
import argparse
import hashlib
import re
import shlex
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SECRET = re.compile(r"(PASSWORD|SECRET|TOKEN|KEY)", re.I)


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def read_env(path):
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("\"'")
    return env


def load_jdk_table():
    """读取 IDEA 全局 jdk.table.xml，返回 {JDK 名称: homePath}。"""
    home = Path.home()
    roots = [home / "Library/Application Support/JetBrains", home / ".config/JetBrains"]
    table = {}
    for root in roots:
        for f in sorted(root.glob("*/options/jdk.table.xml")):
            try:
                tree = ET.parse(f).getroot()
            except ET.ParseError:
                continue
            for jdk in tree.iter("jdk"):
                n, h = jdk.find("name"), jdk.find("homePath")
                if n is not None and h is not None:
                    table[n.get("value")] = h.get("value").replace("$USER_HOME$", str(home))
    return table


def project_sdk_name(project):
    misc = project / ".idea" / "misc.xml"
    if not misc.is_file():
        return None
    try:
        for c in ET.parse(misc).getroot().iter("component"):
            if c.get("name") == "ProjectRootManager":
                return c.get("project-jdk-name")
    except ET.ParseError:
        pass
    return None


def resolve_jre(ref, table, project):
    """ref 可能是 JDK 名称或路径；找不到返回空串。"""
    if not ref:
        return ""
    if "/" in ref or "$" in ref:
        p = ref.replace("$USER_HOME$", str(Path.home())).replace("$PROJECT_DIR$", str(project))
        return p.rstrip("/")
    return table.get(ref, "").rstrip("/")


def parse_run_xml(xml_path, project):
    cfg = ET.parse(xml_path).getroot().find("configuration")
    if cfg is None or cfg.get("type") != "SpringBootApplicationConfigurationType":
        return None
    opt = lambda n: next((o.get("value") for o in cfg.findall("option") if o.get("name") == n), None)
    env = {}
    for o in cfg.findall("./option[@name='envFilePaths']/option"):
        p = o.get("value").replace("$PROJECT_DIR$", str(project))
        env_file = Path(p).resolve()
        if not env_file.is_file():
            sys.exit(f"env 文件不存在: {env_file} (来自 {xml_path.name})")
        env.update(read_env(env_file))
    # 手动设置的单项环境变量；IDEA 中优先级高于 env 文件，故后写入覆盖
    manual = {}
    for e in cfg.findall("./envs/env"):
        if e.get("name"):
            manual[e.get("name")] = (e.get("value") or "").replace("$PROJECT_DIR$", str(project))
    env.update(manual)
    module = cfg.find("module")
    return {
        "name": cfg.get("name"),
        "profile": opt("ACTIVE_PROFILES") or "",
        "main": opt("SPRING_BOOT_MAIN_CLASS"),
        "module": module.get("name") if module is not None else "",
        "vm": opt("VM_PARAMETERS") or "",
        "args": opt("PROGRAM_PARAMETERS") or "",
        "alt_jre": opt("ALTERNATIVE_JRE_PATH") if opt("ALTERNATIVE_JRE_PATH_ENABLED") == "true" else None,
        "env": env,
        "env_manual": sorted(manual),
    }


def render(c, jre):
    cp = "${classpath}"
    args = [*shlex.split(c["vm"]), "-cp", cp, c["main"]]
    if c["profile"]:
        args.append(f"--spring.profiles.active={c['profile']}")
    args.extend(shlex.split(c["args"]))
    arglist = ", ".join(f'"{esc(a)}"' for a in args)
    envs = ", ".join(f'{k} = "{esc(v)}"' for k, v in sorted(c["env"].items()))
    cid = "user:" + hashlib.md5(c["name"].encode()).hexdigest()[:9]
    return f'''
[[configurations]]
id = "{cid}"
name = "{esc(c['name'])}"
kind = "spring-boot"
command = "{jre + '/bin/java' if jre else ''}"
args = [{arglist}]
module = "{c['module']}"
env = {{ {envs} }}
debug-adapter = "java-debug"
params = {{ activeProfiles = "{esc(c['profile'])}", classpath = "{cp}", jre = "{jre}", mainClass = "{c['main']}", module = "{c['module']}", programArgs = "{esc(c['args'])}", vmOptions = "{esc(c['vm'])}" }}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--jre", help="显式指定 JAVA_HOME（可选）；默认从 IDEA 配置读取，读不到则留空")
    ap.add_argument("--only", action="append", help="只转换指定名称，可多次")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    project = Path(a.project).resolve()
    target = project / ".openidea" / "run.toml"
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    exist_names = set(re.findall(r'^name = "(.*)"$', existing, re.M))

    table = load_jdk_table()
    proj_jre = resolve_jre(project_sdk_name(project), table, project)

    out, report = "", []
    for x in sorted((project / ".run").glob("*.run.xml")):
        c = parse_run_xml(x, project)
        if c is None or c["name"].lower().startswith("template"):
            continue
        if a.only and c["name"] not in a.only:
            continue
        if c["name"] in exist_names:
            report.append(f"跳过(已存在): {c['name']}")
            continue
        if a.jre:
            jre, src = a.jre.rstrip("/"), "--jre"
        elif resolve_jre(c["alt_jre"], table, project):
            jre, src = resolve_jre(c["alt_jre"], table, project), "run.xml"
        elif proj_jre:
            jre, src = proj_jre, "项目SDK"
        else:
            jre, src = "", "未找到,留空"
        out += render(c, jre)
        secrets = [k for k in c["env"] if SECRET.search(k)]
        report.append(f"转换: {c['name']} profile={c['profile']} jre={jre or '(空)'}[{src}] env键={sorted(c['env'])}(其中手动设置: {c['env_manual']}) 含敏感键={secrets}")

    print("\n".join(report) or "没有可转换的配置")
    if out and not target.exists():
        print(f"{target} 不存在，{'dry-run 不会实际新建' if a.dry_run else '将新建'}（.openidea 与 .run 同级）")
    if out and not a.dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        sep = "" if not existing or existing.endswith("\n") else "\n"
        target.write_text(existing + sep + out, encoding="utf-8")
        print(f"已写入 {target}")


main()
