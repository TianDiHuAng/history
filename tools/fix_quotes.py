# -*- coding: utf-8 -*-
"""fix_quotes.py — 把 JSON 字符串值内部未转义的 ASCII 引号转为中文引号。
用法：python tools/fix_quotes.py data/china/xianqin.json
结构引号（键/值的定界符）保留；内层引号按开/闭交替转成 “ ”。
转换后立即验证 JSON 合法，合法才写回。
"""
import json
import sys

path = sys.argv[1]
s = open(path, encoding="utf-8").read()
out = []
BS = chr(92)  # backslash
STRUCT_NEXT = set(':,}]') | {'\n'}
STRUCT_PREV = set(':,[{')
open_quote = False
inner_open = False
i, n = 0, len(s)
while i < n:
    c = s[i]
    if c == BS:
        out.append(s[i:i + 2])
        i += 2
        continue
    if c == '"':
        nxt = s[i + 1] if i + 1 < n else '\n'
        j = i - 1
        while j >= 0 and s[j] in ' \t':
            j -= 1
        prv = s[j] if j >= 0 else '\n'
        if not open_quote:
            out.append('"')
            open_quote = True
            inner_open = False
        else:
            if nxt in STRUCT_NEXT:
                out.append('"')
                open_quote = False
            else:
                out.append('“' if not inner_open else '”')
                inner_open = not inner_open
    else:
        out.append(c)
    i += 1
res = ''.join(out)
try:
    json.loads(res)
except Exception as e:
    print("still bad:", e)
    sys.exit(1)
open(path, "w", encoding="utf-8").write(res)
print("fixed & saved:", path)
