# -*- coding: utf-8 -*-
"""graph_core.py — 关系图谱核心：确定性力导向布局 + 零 JS 的 SVG 网络图。

供 gen_site.py 调用，输出两类图：
  1. overview_svg()   全站总览：18 个单元节点（大小=条目数），实线=时间顺序相邻，虚线=中外同期并存
  2. unit_graph_svg() 单元关系图：主事件（圆）×人物（胶囊）二部网络，边=key_people 关联

所有节点可点击（SVG <a href>），悬停有 <title> 提示——纯 SVG 原生能力，零 JS。
布局用固定随机种子的 Fruchterman–Reingold 简化实现，同一数据重复生成结果一致。
"""
import math
import random

NAVY = "#1c3a5c"    # 事件节点 / 中国单元
GOLD = "#5b8db8"    # 人物节点 / 世界单元
EDGE = "#a8c0d4"    # 人物关联边
CHAIN = "#8fb0c9"   # 时间链 / 总览实线
INK = "#1e2d3d"
MUTED = "#5b7a96"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def force_layout(n, edges, W, H, iters=260, seed=7):
    """Fruchterman–Reingold 简化实现：全对斥力 + 边弹簧引力 + 向心重力，温度退火。
    返回 n 个 [x, y]。"""
    rnd = random.Random(seed)
    pos = []
    for i in range(n):
        ang = 2 * math.pi * i / n
        pos.append([W / 2 + (W * 0.33) * math.cos(ang),
                    H / 2 + (H * 0.33) * math.sin(ang)])
    k = math.sqrt(W * H / max(n, 1)) * 0.85   # 理想间距
    t = min(W, H) * 0.12
    disp = [[0.0, 0.0] for _ in range(n)]
    for _ in range(iters):
        for i in range(n):
            disp[i][0] = disp[i][1] = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                dx = pos[i][0] - pos[j][0]
                dy = pos[i][1] - pos[j][1]
                d = math.sqrt(dx * dx + dy * dy) + 1e-9
                f = k * k / d
                fx, fy = f * dx / d, f * dy / d
                disp[i][0] += fx; disp[i][1] += fy
                disp[j][0] -= fx; disp[j][1] -= fy
        for a, b in edges:
            dx = pos[a][0] - pos[b][0]
            dy = pos[a][1] - pos[b][1]
            d = math.sqrt(dx * dx + dy * dy) + 1e-9
            f = d * d / k
            fx, fy = f * dx / d, f * dy / d
            disp[a][0] -= fx; disp[a][1] -= fy
            disp[b][0] += fx; disp[b][1] += fy
        for i in range(n):
            disp[i][0] += (W / 2 - pos[i][0]) * 0.03
            disp[i][1] += (H / 2 - pos[i][1]) * 0.03
        for i in range(n):
            dx, dy = disp[i][0], disp[i][1]
            d = math.sqrt(dx * dx + dy * dy) + 1e-9
            lim = min(d, t)
            pos[i][0] = min(max(pos[i][0] + dx / d * lim, 34), W - 34)
            pos[i][1] = min(max(pos[i][1] + dy / d * lim, 30), H - 30)
        t *= 0.965
    return pos


def _clip(t, n):
    return t if len(t) <= n else t[:n] + "…"


def overview_svg(china, world, depth):
    """全站总览：单元级网络图。节点大小=条目数；实线=同区域时间相邻；虚线=中外年代重叠。"""
    W, H = 940, 560
    nodes = []   # (unit, label)
    counts = []
    for u in china + world:
        n_ev = len(u.get("events") or []) + len((u.get("_extra") or {}).get("extra_events") or [])
        n_pe = len(u.get("people") or []) + len((u.get("_extra") or {}).get("extra_people") or [])
        nodes.append(u)
        counts.append(n_ev + n_pe)
    n = len(nodes)
    idx = {u["unit_id"]: i for i, u in enumerate(nodes)}
    edges = []
    for lst in (china, world):
        for a, b in zip(lst, lst[1:]):
            edges.append((idx[a["unit_id"]], idx[b["unit_id"]], "chain"))
    # 中外同期并存：年代区间重叠即连虚线
    for a in china:
        for b in world:
            sa, ea = a.get("start_year"), a.get("end_year")
            sb, eb = b.get("start_year"), b.get("end_year")
            if None in (sa, ea, sb, eb):
                continue
            if sa <= eb and sb <= ea:
                edges.append((idx[a["unit_id"]], idx[b["unit_id"]], "overlap"))
    pos = force_layout(n, [(a, b) for a, b, _ in edges], W, H,
                       iters=320, seed=sum(ord(c) for c in "overview") % 997)
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}' font-family='sans-serif'>"]
    # 边
    for a, b, kind in edges:
        dash = " stroke-dasharray='6 5'" if kind == "overlap" else ""
        col = EDGE if kind == "overlap" else CHAIN
        out.append(f"<line x1='{pos[a][0]:.1f}' y1='{pos[a][1]:.1f}' x2='{pos[b][0]:.1f}' y2='{pos[b][1]:.1f}' "
                   f"stroke='{col}' stroke-width='1.3' opacity='.8'{dash}/>")
    # 节点
    for i, u in enumerate(nodes):
        x, y = pos[i]
        r = 9 + math.sqrt(counts[i]) * 1.05
        col = NAVY if u["region"] == "china" else GOLD
        href = f"{'../' * depth}{u['region']}/{u['unit_id']}/"
        tip = (f"{u['title']}：事件 {counts[i]} 条"
               f"（{u.get('start_year')}—{u.get('end_year')}）")
        out.append(f"<a href='{href}'><circle cx='{x:.1f}' cy='{y:.1f}' r='{r:.1f}' fill='{col}' opacity='.92'>"
                   f"<title>{esc(tip)}</title></circle>"
                   f"<text x='{x:.1f}' y='{y + r + 13:.1f}' text-anchor='middle' font-size='11.5' fill='{INK}'>"
                   f"{esc(_clip(u['title'], 9))}</text></a>")
    # 图例
    lx, ly = 16, H - 56
    out.append(f"<rect x='{lx - 8}' y='{ly - 18}' width='300' height='66' rx='6' fill='#ffffff' stroke='{EDGE}'/>")
    out.append(f"<circle cx='{lx + 8}' cy='{ly - 2}' r='7' fill='{NAVY}'/><text x='{lx + 22}' y='{ly + 2}' font-size='11' fill='{INK}'>中国单元（大小=条目数）</text>")
    out.append(f"<circle cx='{lx + 8}' cy='{ly + 18}' r='7' fill='{GOLD}'/><text x='{lx + 22}' y='{ly + 22}' font-size='11' fill='{INK}'>世界单元（大小=条目数）</text>")
    out.append(f"<line x1='{lx + 170}' y1='{ly - 2}' x2='{lx + 206}' y2='{ly - 2}' stroke='{CHAIN}' stroke-width='1.6'/>"
               f"<text x='{lx + 212}' y='{ly + 2}' font-size='11' fill='{INK}'>时间顺序相邻</text>")
    out.append(f"<line x1='{lx + 170}' y1='{ly + 18}' x2='{lx + 206}' y2='{ly + 18}' stroke='{EDGE}' stroke-width='1.6' stroke-dasharray='6 5'/>"
               f"<text x='{lx + 212}' y='{ly + 22}' font-size='11' fill='{INK}'>中外同期并存（年代区间重叠）</text>")
    out.append("</svg>")
    return "".join(out)


def unit_graph_svg(unit, depth):
    """单元二部关系图：主事件（左列圆点，按年代竖排）×人物（右列胶囊），连线=key_people。
    双列结构布局（二部图标准画法）：零重叠、可读性稳定，不受稀疏/稠密影响。
    返回 (svg, 统计dict)。延伸事件无人物关联字段，不入图（在图注说明）。"""
    uid = unit["unit_id"]
    base = f"{'../' * depth}"
    events = unit.get("events") or []
    people = list(unit.get("people") or []) + list((unit.get("_extra") or {}).get("extra_people") or [])

    n_rows = max(len(events), len(people), 6)
    row_h = 32
    top, bottom_pad = 74, 58
    H = top + n_rows * row_h + bottom_pad
    W = 940
    x_ev, x_pe = 330, 610

    ev_pos = {}
    for i, ev in enumerate(events):
        ev_pos[ev["id"]] = top + (i + 0.5) * (n_rows * row_h) / max(len(events), 1)
    pe_pos = {}
    for i, p in enumerate(people):
        pe_pos[p["id"]] = top + (i + 0.5) * (n_rows * row_h) / max(len(people), 1)

    deg_ev, deg_pe = {}, {}
    edges = []
    for ev in events:
        for pid in ev.get("key_people") or []:
            if pid in pe_pos:
                edges.append((ev["id"], pid))
                deg_ev[ev["id"]] = deg_ev.get(ev["id"], 0) + 1
                deg_pe[pid] = deg_pe.get(pid, 0) + 1

    out = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}' font-family='sans-serif'>"]
    # 连线（先画，被节点覆盖端点）
    for eid, pid in edges:
        y1, y2 = ev_pos[eid], pe_pos[pid]
        w = 1.0 + 0.45 * deg_pe.get(pid, 1)
        out.append(f"<line x1='{x_ev}' y1='{y1:.1f}' x2='{x_pe - 24}' y2='{y2:.1f}' "
                   f"stroke='{EDGE}' stroke-width='{w:.1f}' opacity='.7'/>")
    # 列头
    out.append(f"<text x='{x_ev}' y='40' text-anchor='middle' font-size='13' font-weight='bold' fill='{NAVY}'>主事件（按年代）</text>")
    out.append(f"<text x='{x_pe}' y='40' text-anchor='middle' font-size='13' font-weight='bold' fill='{NAVY}'>人物</text>")
    out.append(f"<line x1='60' y1='52' x2='{W - 60}' y2='52' stroke='{EDGE}'/>")
    # 事件节点（圆 + 左侧标签）
    for ev in events:
        y = ev_pos[ev["id"]]
        d = deg_ev.get(ev["id"], 0)
        r = 5 + min(d, 6) * 1.5
        tip = f"{ev.get('year_display', '')} · {ev['title']}"
        href = f"{base}events/{uid}-{ev['id']}.html"
        out.append(f"<a href='{href}'><circle cx='{x_ev}' cy='{y:.1f}' r='{r:.1f}' fill='{NAVY}' opacity='.93'>"
                   f"<title>{esc(tip)}</title></circle>"
                   f"<text x='{x_ev - r - 8:.1f}' y='{y + 3.5:.1f}' text-anchor='end' font-size='10' fill='{INK}'>"
                   f"{esc(_clip(ev['title'], 12))}</text></a>")
    # 人物节点（胶囊 + 名字内嵌）
    for p in people:
        y = pe_pos[p["id"]]
        name = p["name"]
        bd, dd = p.get("birth_display") or "", p.get("death_display") or ""
        tip = name + (f"（{bd}—{dd}）" if bd or dd else "")
        href = f"{base}people/{p['id']}.html"
        d = deg_pe.get(p["id"], 0)
        w = len(name) * 10.5 + 14 + min(d, 6) * 2
        h = 19
        out.append(f"<a href='{href}'><rect x='{x_pe - w / 2:.1f}' y='{y - h / 2:.1f}' width='{w:.1f}' height='{h}' "
                   f"rx='9.5' fill='{GOLD}' opacity='.95'><title>{esc(tip)}</title></rect>"
                   f"<text x='{x_pe:.1f}' y='{y + 3.5:.1f}' text-anchor='middle' font-size='10' fill='#ffffff'>"
                   f"{esc(name)}</text></a>")
    # 图例（底部独立条，不压节点）
    ly = H - 30
    out.append(f"<circle cx='80' cy='{ly - 4}' r='6.5' fill='{NAVY}'/><text x='94' y='{ly}' font-size='11' fill='{INK}'>主事件（大小=关联人物数）</text>")
    out.append(f"<rect x='300' y='{ly - 12}' width='20' height='14' rx='7' fill='{GOLD}'/><text x='328' y='{ly}' font-size='11' fill='{INK}'>人物（主人物＋其他重要人物）</text>")
    out.append(f"<line x1='560' y1='{ly - 4}' x2='600' y2='{ly - 4}' stroke='{EDGE}' stroke-width='1.4'/><text x='608' y='{ly}' font-size='11' fill='{INK}'>人物参与事件（key_people）</text>")
    out.append("</svg>")
    stats = {"events": len(events), "people": len(people), "edges": len(edges),
             "isolated_events": sum(1 for e in events if e["id"] not in deg_ev)}
    return "".join(out), stats
