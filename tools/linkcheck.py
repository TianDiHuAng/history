# -*- coding: utf-8 -*-
"""linkcheck.py — 核验 sources.json：JSON 合法、>=100 条、id 唯一、URL 可达。

用法：python tools/linkcheck.py [--timeout 15] [--only-dead]
将 link_ok=true/false 写回 sources.json（url 失败则尝试 url2）。
"""
import json
import sys
import io
import ssl
import urllib.request
import urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = "sources.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) history-site linkcheck"}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE  # 仅核验可达性，不做证书校验


def enc(u):
    """对非 ASCII 字符做百分号编码，保留其余结构。"""
    return urllib.parse.quote(u, safe=":/?#[]@!$&'()*+,;=%")


def fetch(url, timeout):
    """返回 (状态, 说明)。状态: True=可达, 'blocked'=反爬拦截(服务器可达但拒绝脚本), False=死链。"""
    u = enc(url)
    blocked_codes = (401, 403, 405, 406, 429, 503)
    last = None
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(u, headers=UA, method=method)
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                if r.status < 400:
                    return True, f"HTTP {r.status} via {method}"
                last = f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            if e.code in blocked_codes:
                last = f"blocked HTTP {e.code}"
            else:
                return False, f"HTTPError {e.code}"
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:120]}"
    if last and last.startswith("blocked"):
        return "blocked", last
    return False, last


def main():
    timeout = 15
    only_dead = "--only-dead" in sys.argv
    if "--timeout" in sys.argv:
        timeout = float(sys.argv[sys.argv.index("--timeout") + 1])

    with open(ROOT, "r", encoding="utf-8") as f:
        doc = json.load(f)
    srcs = doc["sources"]
    print(f"sources.json 解析成功，共 {len(srcs)} 条")

    if len(srcs) < 100:
        print(f"!! 条目数 {len(srcs)} < 100")
        return 1
    ids = [s["id"] for s in srcs]
    if len(ids) != len(set(ids)):
        print("!! id 有重复")
        return 1

    dead, offline, alive, blocked = [], [], 0, 0
    for s in srcs:
        if s.get("url") is None:
            s["link_ok"] = None
            offline.append(s["id"])
            continue
        ok, msg = fetch(s["url"], timeout)
        if ok is False and s.get("url2"):
            ok2, msg2 = fetch(s["url2"], timeout)
            if ok2:
                ok, msg = ok2, msg2 + " (url2)"
        s["link_ok"] = ok
        if ok is True:
            alive += 1
            if not only_dead:
                print(f"  OK  {s['id']}: {msg}")
        elif ok == "blocked":
            blocked += 1
            if not only_dead:
                print(f"  BLK {s['id']}: {msg}")
        else:
            dead.append((s["id"], s["url"], msg))
            print(f"  DEAD {s['id']}: {msg}")

    with open(ROOT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print(f"\n汇总：共 {len(srcs)} 条 | 在线可达 {alive} | 反爬拦截 {blocked} | 离线文献 {len(offline)} | 失败 {len(dead)}")
    if dead:
        print("失败清单：")
        for i, u, m in dead:
            print(f"  - {i}: {u} ({m})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
