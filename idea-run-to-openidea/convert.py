#!/usr/bin/env python3
"""把 IDEA 的 .run/*.run.xml (Spring Boot 类型) 转成 OpenIDEA 的 .openidea/run.toml。

用法: python3 -I convert.py --project <项目根> --jre <JAVA_HOME> [--only 名称] [--dry-run]
- 已存在同名配置会跳过，不覆盖用户手建的条目
- envFilePaths 指向的 env 文件会被读取，内容内联到 env 表（OpenIDEA 不支持引用 env 文件）
- 输出时密码类取值打码，只写入文件，不打印
"""
import argparse
import hashlib
import re
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
    module = cfg.find("module")
    return {
        "name": cfg.get("name"),
        "profile": opt("ACTIVE_PROFILES") or "",
        "main": opt("SPRING_BOOT_MAIN_CLASS"),
        "module": module.get("name") if module is not None else "",
        "vm": opt("VM_PARAMETERS") or "",
        "args": opt("PROGRAM_PARAMETERS") or "",
        "env": env,
    }


def render(c, jre):
    cp = "${classpath}"
    args = ["-cp", cp, c["main"]]
    if c["profile"]:
        args.append(f"--spring.profiles.active={c['profile']}")
    arglist = ", ".join(f'"{esc(a)}"' for a in args)
    envs = ", ".join(f'{k} = "{esc(v)}"' for k, v in sorted(c["env"].items()))
    cid = "user:" + hashlib.md5(c["name"].encode()).hexdigest()[:9]
    return f'''
[[configurations]]
id = "{cid}"
name = "{esc(c['name'])}"
kind = "spring-boot"
command = "{jre}/bin/java"
args = [{arglist}]
module = "{c['module']}"
env = {{ {envs} }}
debug-adapter = "java-debug"
params = {{ activeProfiles = "{esc(c['profile'])}", classpath = "{cp}", jre = "{jre}", mainClass = "{c['main']}", module = "{c['module']}", programArgs = "{esc(c['args'])}", vmOptions = "{esc(c['vm'])}" }}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--jre", required=True, help="JAVA_HOME，如 /root/.vfox/.../java-11.0.31-amzn")
    ap.add_argument("--only", action="append", help="只转换指定名称，可多次")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    project = Path(a.project).resolve()
    target = project / ".openidea" / "run.toml"
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    exist_names = set(re.findall(r'^name = "(.*)"$', existing, re.M))

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
        out += render(c, a.jre.rstrip("/"))
        secrets = [k for k in c["env"] if SECRET.search(k)]
        report.append(f"转换: {c['name']} profile={c['profile']} env键={sorted(c['env'])} 含敏感键={secrets}")

    print("\n".join(report) or "没有可转换的配置")
    if out and not a.dry_run:
        target.parent.mkdir(exist_ok=True)
        sep = "" if not existing or existing.endswith("\n") else "\n"
        target.write_text(existing + sep + out, encoding="utf-8")
        print(f"已写入 {target}")


main()
