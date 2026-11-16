# -*- coding: utf-8 -*-
"""gen_readme_images.py — 从 data/ 统计生成 README 可视化图片（SVG）。
输出到 assets/img/。纯确定性生成，随数据重跑更新。
"""
import json
import glob
import os
import io
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "img")
NAVY, RED, GOLD, MUTED, BG, INK = "#2b4a6f", "#8c1f28", "#c8a45c", "#7a7468", "#faf7f0", "#2c2c28"

units = {}
for fp in sorted(glob.glob(os.path.join(ROOT, "data", "*", "*.json"))):
    norm = fp.replace("\\", "/")
    if "/enrich/" in norm or "/themes/" in norm:
        continue
    d = json.load(open(fp, encoding="utf-8"))
    units[d["unit_id"]] = d


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unit_title(uid):
    d = units.get(uid, {})
    return esc(d.get("title", uid))


def save(name, svg):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", name)


# ---------- 图1：各单元条目规模（主事件+延伸事件+人物 堆叠条） ----------
def img_units():
    order_ch = ["china-xianqin", "china-chunqiu-zhanguo", "china-qin", "china-xihan",
                "china-donghan", "china-sanguo-liangjin-nanbeichao", "china-sui", "china-tang",
                "china-wudai-shiguo", "china-song", "china-yuan", "china-ming", "china-qing"]
    order_wo = ["world-ancient", "world-classical", "world-medieval", "world-early-modern", "world-modern"]
    rows = []
    for uid in order_ch + order_wo:
        d = units[uid]
        ev = len(d.get("events", []))
        xev = len(d.get("extra_events", []))
        pe = len(d.get("people", [])) + len(d.get("extra_people", []))
        rows.append((uid, ev, xev, pe))
    W, LH, PAD, LBL = 780, 30, 74, 300
    H = PAD * 2 + LH * len(rows)
    maxv = max(sum(r[1:]) for r in rows)
    scale = (W - LBL - 30) / maxv
    svg = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}' font-family='sans-serif'>",
           f"<rect width='{W}' height='{H}' fill='#ffffff'/>",
           f"<text x='{W/2}' y='30' text-anchor='middle' font-size='17' fill='{INK}'>各单元条目规模（事件 / 延伸事件 / 人物）</text>"]
    y = PAD + 6
    for uid, ev, xev, pe in rows:
        total = ev + xev + pe
        y0 = y
        w1, w2, w3 = ev * scale, xev * scale, pe * scale
        svg.append(f"<rect x='{LBL}' y='{y0}' width='{w1:.1f}' height='18' fill='{NAVY}'/>")
        svg.append(f"<rect x='{LBL+w1:.1f}' y='{y0}' width='{w2:.1f}' height='18' fill='{GOLD}'/>")
        svg.append(f"<rect x='{LBL+w1+w2:.1f}' y='{y0}' width='{w3:.1f}' height='18' fill='{RED}'/>")
        t = unit_title(uid)
        if len(t) > 11:
            t = t[:11] + "…"
        svg.append(f"<text x='{LBL-8}' y='{y0+14}' text-anchor='end' font-size='12' fill='{INK}'>{t}</text>")
        svg.append(f"<text x='{LBL+w1+w2+w3+6:.1f}' y='{y0+14}' font-size='11' fill='{MUTED}'>{total}</text>")
        y += LH
    lx = PAD + 6
    for col, label in ((NAVY, "关键事件"), (GOLD, "延伸事件"), (RED, "人物")):
        svg.append(f"<rect x='{lx}' y='{H-18}' width='12' height='12' fill='{col}'/>")
        svg.append(f"<text x='{lx+16}' y='{H-8}' font-size='11' fill='{INK}'>{label}</text>")
        lx += 92
    svg.append("</svg>")
    save("units-scale.svg", "\n".join(svg))


# ---------- 图2：事件年代分布（世纪直方图，中国vs世界） ----------
def img_centuries():
    buckets = collections.Counter()

    def bucket(y):
        if y < 0:
            return -(((-y + 199) // 200)) * 200  # 200年粗桶（公元前）
        return (y // 100) * 100  # 100年桶（公元后）

    labels = {}
    for uid, d in units.items():
        region = d["region"]
        xs = [(e["year"], False) for e in d.get("events", [])]
        xs += [(e["year"], True) for e in d.get("extra_events", [])]
        for y, _ in xs:
            b = bucket(y)
            buckets[(b, region)] += 1
            if b not in labels:
                labels[b] = b
    keys = sorted(set(b for b, _ in buckets))
    # 聚合稀疏的公元前桶到500年粒度，公元后用200年粒度
    agg = collections.Counter()
    disp = {}
    for (b, region), n in buckets.items():
        if b < 0:
            g = -(((-b + 499) // 500)) * 500
        else:
            g = (b // 200) * 200
        agg[(g, region)] += n
        if g not in disp:
            disp[g] = g
    groups = sorted(set(g for g, _ in agg))
    W, H, PAD = 780, 400, 60
    CH = H - PAD * 2 - 30
    gw = (W - PAD * 2) / len(groups)
    maxv = max(agg.values())
    svg = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}' font-family='sans-serif'>",
           f"<rect width='{W}' height='{H}' fill='#ffffff'/>",
           f"<text x='{W/2}' y='28' text-anchor='middle' font-size='17' fill='{INK}'>事件条目的年代分布（中国 vs 世界，含延伸条目）</text>",
           f"<line x1='{PAD}' y1='{H-40}' x2='{W-PAD+6}' y2='{H-40}' stroke='{MUTED}'/>"]
    for i, g in enumerate(groups):
        x = PAD + i * gw
        ch = agg.get((g, "china"), 0)
        wo = agg.get((g, "world"), 0)
        total = ch + wo
        h_ch = ch / maxv * CH
        h_wo = wo / maxv * CH
        if ch:
            svg.append(f"<rect x='{x+3:.1f}' y='{H-40-h_ch:.1f}' width='{gw*0.42:.1f}' height='{h_ch:.1f}' fill='{NAVY}'/>")
        if wo:
            svg.append(f"<rect x='{x+3+gw*0.45:.1f}' y='{H-40-h_wo:.1f}' width='{gw*0.42:.1f}' height='{h_wo:.1f}' fill='{GOLD}'/>")
        lbl = f"前{-g//100 if g<0 else g}"
        if g < 0:
            lbl = f"前{-g//100+1}世纪前" if g % 500 == -500 else f"约前{-g}"
        else:
            lbl = f"{g}年"
        step = max(1, len(groups) // 14)
        if i % step == 0:
            svg.append(f"<text x='{x+gw/2:.1f}' y='{H-24}' text-anchor='middle' font-size='10' fill='{MUTED}'>{lbl}</text>")
        if total:
            svg.append(f"<text x='{x+gw/2:.1f}' y='{H-46-max(0,(h_ch)):.1f}' text-anchor='middle' font-size='9' fill='{MUTED}'>{total}</text>")
    lx = PAD
    for col, label in ((NAVY, "中国"), (GOLD, "世界")):
        svg.append(f"<rect x='{lx}' y='{H-18}' width='12' height='12' fill='{col}'/>")
        svg.append(f"<text x='{lx+16}' y='{H-8}' font-size='11' fill='{INK}'>{label}</text>")
        lx += 70
    svg.append("</svg>")
    save("centuries-distribution.svg", "\n".join(svg))


# ---------- 图3：站点结构 ----------
def img_sitemap():
    boxes = [
        ("首页", 300, 30, NAVY),
        ("中国 13单元", 80, 110, None), ("世界 5时期", 300, 110, None),
        ("中国时间线", 520, 110, None), ("世界时间线", 640, 110, None),
        ("单元页（线索/分期/变化）", 40, 190, "#efe4cf"),
        ("延伸事件 179", 200, 190, "#efe4cf"),
        ("专题 81", 360, 190, "#efe4cf"),
        ("其他人物 116", 480, 190, "#efe4cf"),
        ("事件页 418", 80, 270, None),
        ("人物页 137", 200, 270, None),
        ("中外对照 418", 320, 270, None),
        ("世纪总览", 440, 270, None),
        ("事件索引 418", 560, 270, None),
        ("人物索引 253", 680, 270, None),
        ("来源列表 169", 320, 340, "#efe4cf"),
    ]
    W, H = 780, 400
    svg = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}' font-family='sans-serif'>",
           f"<rect width='{W}' height='{H}' fill='#ffffff'/>",
           f"<text x='{W/2}' y='24' text-anchor='middle' font-size='16' fill='{INK}'>站点结构（584 个静态文件）</text>"]
    for label, x, y, color in boxes:
        w = max(120, len(label) * 13 + 24)
        fill = color or "#ffffff"
        stroke = NAVY if color in (None, "#efe4cf") else "#ffffff"
        svg.append(f"<rect x='{x}' y='{y}' width='{w}' height='40' rx='6' fill='{fill}' stroke='{NAVY}'/>")
        tc = "#ffffff" if color == NAVY else INK
        svg.append(f"<text x='{x+w/2}' y='{y+24}' text-anchor='middle' font-size='12' fill='{tc}'>{esc(label)}</text>")
    for x1, y1, x2, y2 in ((350, 70, 140, 110), (350, 70, 360, 110), (350, 70, 580, 110), (350, 70, 700, 110)):
        svg.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{MUTED}'/>")
    svg.append("</svg>")
    save("site-map.svg", "\n".join(svg))


img_units()
img_centuries()
img_sitemap()
print("done ->", OUT)
