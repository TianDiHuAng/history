# -*- coding: utf-8 -*-
"""check_links.py — 站内链接完整性核验：扫描 site/**/*.html 中的相对链接，验证目标文件存在。
用法：python tools/check_links.py（须先跑 gen_site.py）
只查站内相对链接；外部 http 链接归 linkcheck.py 管。
"""
import glob
import os
import re
import io
import sys
from urllib.parse import unquote

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
ATTR = re.compile(r"""(?:href|src)=['"]([^'"]+)['"]""")
SKIP = ("http://", "https://", "#", "mailto:", "data:")


def main():
    bad = []
    n_links = 0
    for fp in glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True):
        txt = open(fp, encoding="utf-8").read()
        for h in ATTR.findall(txt):
            if any(h.startswith(s) for s in SKIP):
                continue
            n_links += 1
            tgt = os.path.normpath(os.path.join(os.path.dirname(fp), unquote(h.split("#")[0].split("?")[0])))
            if tgt.endswith(os.sep) or tgt.endswith("\\") or os.path.isdir(tgt):
                tgt = os.path.join(tgt, "index.html")
            if not os.path.exists(tgt):
                bad.append((os.path.relpath(fp, SITE).replace("\\", "/"), h))
    seen = set()
    uniq = [b for b in bad if not (b in seen or seen.add(b))]
    print(f"站内链接 {n_links} 个（含重复），断链 {len(uniq)} 个（去重）")
    for f, h in uniq[:30]:
        print(f"  MISS {f} -> {h}")
    return 1 if uniq else 0


if __name__ == "__main__":
    sys.exit(main())
