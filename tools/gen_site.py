# -*- coding: utf-8 -*-
"""gen_site.py — 由 data/*.json 生成静态站点 site/

用法：python tools/gen_site.py
输出结构：
  site/index.html                       首页
  site/china/index.html                 中国单元列表
  site/china/<unit>/index.html          单元总览页（线索/分期/重要变化+列表）
  site/world/index.html, site/world/<unit>/index.html
  site/events/<unit>-<event>.html       事件页（固定7节）
  site/people/<person>.html             人物页
  site/timeline/china.html, world.html  时间线
  site/compare/index.html               中外同期对照表
  site/sources/index.html               来源列表
"""
import json
import glob
import os
import re
import shutil
import html
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


def esc(s):
    return html.escape(str(s if s is not None else ""))


def sanitize_svg(svg):
    """保险：修复常见自闭合笔误（'/< → '/><）与未闭合 g 标签（按标签栈补齐）。"""
    if not isinstance(svg, str):
        return svg
    svg = svg.replace("'/<", "'/><").replace("y='0 width='760'", "y='0' width='760'")
    try:
        ET.fromstring(svg)
        return svg
    except Exception:
        pass
    toks = re.findall(r"<[^>]+>|[^<]+", svg)
    out, stack = [], []
    for t in toks:
        if t.startswith("</"):
            name = t[2:-1].strip()
            if stack and stack[-1] == name:
                stack.pop(); out.append(t)
            elif name in stack:
                while stack and stack[-1] != name:
                    out.append("</%s>" % stack.pop())
                stack.pop(); out.append(t)
            else:
                pass
        elif t.startswith("<"):
            m = re.match(r"<([a-zA-Z][a-zA-Z0-9]*)", t)
            if m and not t.rstrip().endswith("/>"):
                stack.append(m.group(1))
            out.append(t)
        else:
            out.append(t)
    while stack:
        out.append("</%s>" % stack.pop())
    return "".join(out)


def cn_year(y):
    """数值年份 → 中文显示（负=公元前）。"""
    if y < 0:
        return f"前{-y}年"
    return f"{y}年" if y != 0 else "公元元年"


def cn_range(a, b):
    return f"{cn_year(a)}—{cn_year(b)}"


def rel(depth):
    return "../" * depth


def write(path, content):
    full = os.path.join(SITE, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return full


def header(title, depth=0, active=""):
    nav_items = [
        ("", "首页"), ("china/", "中国"), ("world/", "世界"),
        ("timeline/china.html", "中国时间线"), ("timeline/world.html", "世界时间线"),
        ("compare/", "中外对照"), ("all-events.html", "事件索引"), ("all-people.html", "人物索引"),
        ("centuries.html", "世纪总览"), ("graph.html", "关系图谱"), ("glossary.html", "术语表"), ("comparative.html", "比较视野"), ("sources/", "来源"),
    ]
    links = []
    for href, label in nav_items:
        cls = ' class="on"' if label == active else ""
        links.append(f'<a href="{rel(depth)}{href}"{cls}>{label}</a>')
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · 镜花水月</title>
<link rel="stylesheet" href="{rel(depth)}assets/style.css">
</head>
<body>
<header class="site"><span class="brand">镜花水月<span class="brand-sub">中外历史脉络库</span></span>
<nav>{' | '.join(links)}</nav></header>
<main>'''


def footer():
    return ('''
<p class="meta" style="margin-top:44px">年份均为公元纪年（公元前用负数表示转换）；关键事实以两个独立来源互相印证为标准，未达标者在页内标注"待核实"。</p>
</main>
<footer class="site"><span class="footer-brand">镜花水月</span> · 静态资料库，内容仅供学习参考，不构成学术结论；引用请核对原始文献。</footer>
</body>
</html>''')


def src_list_html(ids, srcmap, depth):
    items = []
    for sid in ids:
        s = srcmap.get(sid)
        if not s:
            items.append(f"<li>{esc(sid)}（未收录）</li>")
            continue
        mark = {True: '<span class="ok">链接已核验</span>',
                "blocked": '<span class="blk">可达但反爬拦截</span>',
                False: '<span class="bad">链接核验失败</span>',
                None: '<span class="meta">离线文献</span>'}.get(s.get("link_ok"), "")
        link = ""
        if s.get("url"):
            link = f' <a href="{esc(s["url"])}">链接</a>'
        items.append(f"<li>{esc(s['title'])}（{esc(s.get('author',''))}，{esc(s.get('type',''))}）{mark}{link}"
                     + (f"<br><span class='meta'>{esc(s.get('note',''))}</span>" if s.get("note") else ""))
    return f'<ul class="src-list">{"".join(items)}</ul>'


def extra_event_page(unit, ev, srcmap, depth):
    """延伸事件详情页（轻量结构：时间/简介/来源/待核实，无 SVG）。"""
    nv = ev.get("needs_verification")
    pending = (ev.get("pending_notes") or "").strip() or "无特别待核实事项（见上方说明）。"
    body = f"""
<h1>{esc(ev['title'])}</h1>
<p class="crumb"><a href="{rel(depth)}{'china/' if unit['region']=='china' else 'world/'}">{esc('中国' if unit['region']=='china' else '世界')}</a> /
<a href="{rel(depth)}{'china' if unit['region']=='china' else 'world'}/{unit['unit_id']}/">{esc(unit['title'])}</a> / 延伸事件</p>
<h2>时间</h2>
<p class="kv"><b>{esc(ev['year_display'])}</b>{'—' + esc(ev.get('end_year_display') or '') if ev.get('end_year_display') else ''}<span class="meta">（{esc(ev.get('year_note',''))}）</span></p>
<h2>说明</h2>
<p>{esc(ev.get('desc',''))}</p>
<h2>待核实</h2>
<div class="pending"><p>{esc(pending)}</p></div>
<h2>参考来源</h2>
{src_list_html(ev.get('sources') or [], srcmap, depth)}
<p class="meta" style="margin-top:20px">本页为延伸条目（主线之外的补充），单元内其他关键事件见 <a href="{rel(depth)}{'china' if unit['region']=='china' else 'world'}/{unit['unit_id']}/">{esc(unit['title'])} 总览页</a>。</p>
"""
    tag = '<span class="tag warn">待核实</span>' if nv else ""
    return header(ev["title"], depth) + body + footer(), tag


def event_page(unit, ev, srcmap, depth):
    ev_path = f"events/{unit['unit_id']}-{ev['id']}.html"
    nv = ev.get("needs_verification")
    pending = (ev.get("pending_notes") or "").strip() or "无特别待核实事项（年份与关键事实已由两个独立来源印证）。"
    steps = "".join(f"<li>{esc(s)}</li>" for s in ev.get("process") or [])
    people = []
    for pid in ev.get("key_people") or []:
        p = unit["_pmap"].get(pid)
        if p:
            people.append(f'<a href="{rel(depth)}people/{pid}.html">{esc(p["name"])}</a>')
        else:
            people.append(esc(pid))
    ctr = []
    for c in ev.get("controversies") or []:
        views = "".join(
            f"<li><b>{esc(v.get('holder',''))}：</b>{esc(v.get('basis',''))}</li>"
            for v in c.get("views") or [])
        ctr.append(f"<div class='card'><p><b>争议：{esc(c.get('issue',''))}</b></p><ul class='tight'>{views}</ul></div>")
    end_disp = ev.get("end_year_display") or ""
    time_str = esc(ev["year_display"]) + (f"—{esc(end_disp)}" if end_disp else "")
    body = f"""
<h1>{esc(ev['title'])}</h1>
<p class="crumb"><a href="{rel(depth)}china/">中国</a> / <a href="{rel(depth)}{'china' if unit['region']=='china' else 'world'}/">{'中国' if unit['region']=='china' else '世界'}</a> /
<a href="{rel(depth)}{'china' if unit['region']=='china' else 'world'}/{unit['unit_id']}/">{esc(unit['title'])}</a> / 事件</p>
<h2>一、时间、地点、主要人物</h2>
<p class="kv"><b>时间：</b>{time_str}<span class="meta">（{esc(ev.get('year_note',''))}）</span></p>
<p class="kv"><b>地点：</b>{esc(ev.get('location',''))}</p>
<p class="kv"><b>主要人物：</b>{'、'.join(people) if people else '—'}</p>
<h2>二、背景与起因</h2>
<p>{esc(ev.get('background',''))}</p>
<h2>三、经过（按时间顺序）</h2>
<ol class="tight">{steps}</ol>
<h2>四、结果与影响</h2>
<p>{esc(ev.get('outcome',''))}</p>
<h2>五、史料来源与史学争议</h2>
{''.join(ctr) if ctr else '<p class="meta">—</p>'}
<h2>六、示意图</h2>
<figure>{sanitize_svg(ev.get('svg', ''))}<figcaption>{esc(ev['title'])}示意图（示意性质，非精确地图/比例）</figcaption></figure>
<h2>七、待核实</h2>
<div class="pending"><p>{esc(pending)}</p></div>
<h2>参考来源</h2>
{src_list_html(ev.get('sources') or [], srcmap, depth)}
{unit_nav_html(unit, ev, depth)}
"""
    tag = '<span class="tag warn">待核实</span>' if nv else ""
    return header(ev["title"], depth) + body + footer(), tag


def person_page(unit, p, srcmap, depth):
    by, dy = p.get("birth_year"), p.get("death_year")
    bd, dd = p.get("birth_display") or cn_year(by) if by is not None else "生卒不可考", p.get("death_display") or (cn_year(dy) if dy is not None else "卒年不可考")
    chrono = "".join(
        f"<li>{esc(c.get('display') or cn_year(c.get('year', 0)))}——{esc(c.get('text',''))}</li>"
        for c in p.get("chronology") or [])
    deeds = "".join(f"<li>{esc(d)}</li>" for d in p.get("deeds") or [])
    evals = "".join(
        f"<div class='card'><p><b>{esc(e.get('holder',''))}：</b>{esc(e.get('view',''))}</p>"
        f"<p class='meta'>依据：{esc(e.get('basis',''))}</p></div>"
        for e in p.get("evaluations") or [])
    rel_events = "".join(
        f"<li><a href='{rel(depth)}events/{unit['unit_id']}-{ev['id']}.html'>{esc(ev['title'])}</a> "
        f"<span class='meta'>({esc(ev['year_display'])})</span></li>"
        for ev in unit["events"] if p["id"] in (ev.get("key_people") or []))
    rel_html = f"<h2>相关事件</h2><ul class='tight'>{rel_events}</ul>" if rel_events else ""
    desc_html = f"<p>{esc(p.get('desc',''))}</p>" if p.get("desc") else ""
    chrono_html = f"<h2>年谱</h2><ul class='tight'>{chrono}</ul>" if p.get("chronology") else ""
    deeds_html = f"<h2>主要事迹</h2><ul class='tight'>{deeds}</ul>" if p.get("deeds") else ""
    evals_html = f"<h2>评价分歧</h2>{evals}" if p.get("evaluations") else ""
    body = f"""
<h1>{esc(p.get('name',''))}</h1>
<p class="crumb"><a href="{rel(depth)}{'china/' if unit['region']=='china' else 'world/'}">{esc('中国' if unit['region']=='china' else '世界')}</a> /
<a href="{rel(depth)}{'china' if unit['region']=='china' else 'world'}/{unit['unit_id']}/">{esc(unit['title'])}</a> / 人物</p>
<h2>生卒年</h2>
<p class="kv"><b>生：</b>{esc(str(bd))}{esc(p.get('birth_note') or '')}
&nbsp;&nbsp;<b>卒：</b>{esc(str(dd))}{esc(p.get('death_note') or '')}</p>
{desc_html}
{chrono_html}
{deeds_html}
{rel_html}
{evals_html}
<h2>参考来源</h2>
{src_list_html(p.get('sources') or [], srcmap, depth)}
"""
    return header(p.get("name", ""), depth) + body + footer()


def unit_nav_html(unit, ev, depth):
    """事件页底部：本单元前一条/后一条关键事件与延伸条目提示。"""
    evs = unit["events"]
    idx = next((i for i, e in enumerate(evs) if e["id"] == ev["id"]), None)
    parts = []
    if idx is not None:
        if idx > 0:
            prev = evs[idx - 1]
            parts.append(f"<a href='{rel(depth)}events/{unit['unit_id']}-{prev['id']}.html'>← {esc(prev['title'])}（{esc(prev['year_display'])}）</a>")
        if idx < len(evs) - 1:
            nxt = evs[idx + 1]
            parts.append(f"<a href='{rel(depth)}events/{unit['unit_id']}-{nxt['id']}.html'>{esc(nxt['title'])}（{esc(nxt['year_display'])}）→</a>")
    xev = (unit.get("_extra") or {}).get("extra_events") or []
    n_x = len(xev)
    if n_x:
        parts.append(f"<a href='{rel(depth)}{'china' if unit['region']=='china' else 'world'}/{unit['unit_id']}/'>单元另有 {n_x} 条延伸事件与 "
                     f"{len((unit.get('_extra') or {}).get('extra_people') or [])} 位其他人物 →</a>")
    if not parts:
        return ""
    return f"<p class='meta' style='margin-top:26px'>{'　·　'.join(parts)}</p>"


def extra_person_page(unit, p, srcmap, depth):
    """其他重要人物详情页（轻量结构：生卒/简介/来源）。"""
    bd = p.get("birth_display") or "生卒不可考"
    dd = p.get("death_display") or "卒年不可考"
    body = f"""
<h1>{esc(p.get('name',''))}</h1>
<p class="crumb"><a href="{rel(depth)}{'china/' if unit['region']=='china' else 'world/'}">{esc('中国' if unit['region']=='china' else '世界')}</a> /
<a href="{rel(depth)}{'china' if unit['region']=='china' else 'world'}/{unit['unit_id']}/">{esc(unit['title'])}</a> / 其他重要人物</p>
<h2>生卒年</h2>
<p class="kv"><b>生：</b>{esc(str(bd))}{esc(p.get('birth_note') or '')}
&nbsp;&nbsp;<b>卒：</b>{esc(str(dd))}{esc(p.get('death_note') or '')}</p>
<h2>简介</h2>
<p>{esc(p.get('desc',''))}</p>
<h2>参考来源</h2>
{src_list_html(p.get('sources') or [], srcmap, depth)}
<p class="meta" style="margin-top:20px">本页为"其他重要人物"条目，同期关键人物见 <a href="{rel(depth)}{'china' if unit['region']=='china' else 'world'}/{unit['unit_id']}/">{esc(unit['title'])} 总览页</a>。</p>
"""
    return header(p.get("name", ""), depth) + body + footer()


def unit_page(unit, srcmap, depth):
    uid = unit["unit_id"]
    ov = unit.get("overview") or {}
    threads = "".join(f"<li>{esc(t)}</li>" for t in ov.get("main_threads") or [])
    sps = "".join(
        f"<tr><td>{esc(sp.get('name',''))}</td><td>{esc(sp.get('range_display',''))}</td><td>{esc(sp.get('desc',''))}</td></tr>"
        for sp in ov.get("sub_periods") or [])
    changes = "".join(f"<li>{esc(c)}</li>" for c in ov.get("key_changes") or [])
    warn_tag = "<span class='tag warn'>待核实</span>"
    evs = "".join(
        f"<tr><td class='year'>{esc(ev['year_display'])}</td>"
        f"<td><a href='{rel(depth)}events/{uid}-{ev['id']}.html'>{esc(ev['title'])}</a>"
        f"{warn_tag if ev.get('needs_verification') else ''}</td>"
        f"<td>{esc(ev.get('location',''))}</td></tr>"
        for ev in unit["events"])
    ppl = "".join(
        f"<tr><td><a href='{rel(depth)}people/{p['id']}.html'>{esc(p['name'])}</a></td>"
        f"<td>{esc(str(p.get('birth_display') or '生卒不可考'))}—{esc(str(p.get('death_display') or '卒年不可考'))}</td></tr>"
        for p in unit["people"])
    ex = unit.get("_extra") or {}
    xev = ex.get("extra_events") or []
    xpp = ex.get("extra_people") or []
    warn_tag2 = "<span class='tag warn'>待核实</span>"
    xev_rows = "".join(
        f"<tr><td class='year'>{esc(e['year_display'])}</td>"
        f"<td><a href='{rel(depth)}events/{uid}-{e['id']}.html'><b>{esc(e['title'])}</b></a>"
        f"{warn_tag2 if e.get('needs_verification') else ''}<br>"
        f"<span class='meta'>{esc(e.get('desc',''))}</span></td></tr>"
        for e in xev)
    xpp_rows = "".join(
        f"<tr><td><a href='{rel(depth)}people/{p['id']}.html'><b>{esc(p['name'])}</b></a></td>"
        f"<td>{esc(str(p.get('birth_display') or '生卒不可考'))}—{esc(str(p.get('death_display') or '卒年不可考'))}</td>"
        f"<td><span class='meta'>{esc(p.get('desc',''))}</span></td></tr>"
        for p in xpp)
    extra_html = ""
    if xev_rows:
        extra_html += f"<h2>延伸事件（{len(xev)}）</h2><p class='meta'>主线事件之外的补充条目，不计入关键事件清单。</p>"
        extra_html += f"<table><tr><th>年份</th><th>事件与简介</th></tr>{xev_rows}</table>"
    if xpp_rows:
        extra_html += f"<h2>其他重要人物（{len(xpp)}）</h2>"
        extra_html += f"<table><tr><th>人物</th><th>生卒</th><th>简介</th></tr>{xpp_rows}</table>"
    themes = unit.get("_themes") or []
    if themes:
        th_html = []
        for t in themes:
            nv = "<span class='tag warn'>待核实</span>" if t.get("needs_verification") else ""
            srcs = "、".join(f"<a class='meta' href='{rel(depth)}sources/'>{esc(s)}</a>" for s in (t.get("sources") or []))
            th_html.append(f"<h3>{esc(t['title'])}{nv}</h3><p>{esc(t.get('text',''))}</p>"
                           f"<p class='meta'>来源：{srcs}</p>")
        extra_html += f"<h2>专题（{len(themes)}）</h2><p class='meta'>经济、社会、技术、文化与生活维度的补充论述。</p>{''.join(th_html)}"
    body = f"""
<h1>{esc(unit['title'])}<span class="meta" style="font-size:1rem">（{esc(unit.get('period_display',''))}）</span></h1>
<p class="crumb"><a href="{rel(depth)}{'china/' if unit['region']=='china' else 'world/'}">{esc('中国' if unit['region']=='china' else '世界')}</a> / 单元总览</p>
<h2>线索</h2>
<ul class="tight">{threads}</ul>
<h2>分期</h2>
<table><tr><th>分期</th><th>年代</th><th>说明</th></tr>{sps}</table>
<h2>重要变化</h2>
<ul class="tight">{changes}</ul>
<h2>关键事件（{len(unit['events'])}）</h2>
<table><tr><th>年份</th><th>事件</th><th>地点</th></tr>{evs}</table>
{extra_html}
<h2>关键人物（{len(unit['people'])}）</h2>
<table><tr><th>人物</th><th>生卒</th></tr>{ppl}</table>
"""
    return header(f"{unit['title']}（{unit.get('period_display','')}）", depth) + body + footer()


def unit_list_page(units, region, title, depth):
    cn = "中国" if region == "china" else "世界"
    cards = "".join(
        f'<div class="card"><h3><a href="{rel(depth)}{region}/{u["unit_id"]}/">{esc(u["title"])}</a></h3>'
        f'<p class="meta">{esc(u.get("period_display",""))} · 事件 {len(u["events"])} · 人物 {len(u["people"])}</p>'
        f'<p>{esc((u.get("overview") or {}).get("main_threads", [""])[0][:80])}…</p></div>'
        for u in units)
    body = f"<h1>{esc(title)}</h1>{cards}"
    return header(title, depth, active=cn) + body + footer()


def timeline_page(units, region, depth):
    cn = "中国" if region == "china" else "世界"
    items = []
    for u in sorted(units, key=lambda x: x["start_year"]):
        items.append(f"<h2><a href='{rel(depth)}{region}/{u['unit_id']}/'>{esc(u['title'])}</a> "
                     f"<span class='meta'>{esc(u.get('period_display',''))}</span></h2>")
        ex = u.get("_extra") or {}
        merged = [(e["year"], 0, e) for e in u["events"]] + \
                 [(e["year"], 1, e) for e in (ex.get("extra_events") or [])]
        merged.sort(key=lambda t: (t[0], t[1]))
        rows = []
        for y, is_x, ev in merged:
            tag = '<span class="tag warn">待核实</span>' if ev.get("needs_verification") else ""
            if is_x:
                rows.append(f"<div class='tl-item tl-extra'><span class='tl-year'>{esc(ev['year_display'])}</span>"
                            f"<a href='{rel(depth)}events/{u['unit_id']}-{ev['id']}.html'>{esc(ev['title'])}</a>{tag}</div>")
            else:
                rows.append(f"<div class='tl-item'><span class='tl-year'>{esc(ev['year_display'])}</span>"
                            f"<a href='{rel(depth)}events/{u['unit_id']}-{ev['id']}.html'>{esc(ev['title'])}</a>{tag}</div>")
        items.append(f"<div class='tl'>{''.join(rows)}</div>")
    body = (f"<h1>{cn}时间线</h1><p class='meta'>按年份先后排列；主事件可点击查看详情，"
            f"灰色条目为延伸事件（详见单元页）。</p>" + "".join(items))
    return header(f"{cn}时间线", depth, active=f"{cn}时间线") + body + footer()


def compare_page(china_units, world_units, depth):
    rows = {}

    def add(u, ev, col):
        rows.setdefault(ev["year"], ["", ""])
        if ev.get("_is_extra"):
            piece = (f"<span class='xitem'>〔{esc(u['title'])}〕"
                     f"<a href='{rel(depth)}events/{u['unit_id']}-{ev['id']}.html'>{esc(ev['title'])}</a></span>")
        else:
            piece = f"<a href='{rel(depth)}events/{u['unit_id']}-{ev['id']}.html'>{esc(ev['title'])}</a>"
        rows[ev["year"]][col] += ("" if not rows[ev["year"]][col] else "<br>") + piece

    for u in china_units:
        for ev in u["events"]:
            add(u, ev, 0)
        for ev in (u.get("_extra") or {}).get("extra_events") or []:
            ev = dict(ev); ev["_is_extra"] = True
            add(u, ev, 0)
    for u in world_units:
        for ev in u["events"]:
            add(u, ev, 1)
        for ev in (u.get("_extra") or {}).get("extra_events") or []:
            ev = dict(ev); ev["_is_extra"] = True
            add(u, ev, 1)
    trs = []
    for y in sorted(rows):
        c, w = rows[y]
        trs.append(f"<tr><td class='year'>{cn_year(y)}</td><td>{c}</td><td>{w}</td></tr>")
    body = f"""
<h1>中外同期对照表</h1>
<p class="meta">只列同一年代中国与世界各自发生的事件，不表示任何因果或同步关系。年份为公元纪年（前=公元前）。</p>
<table><tr><th>年份</th><th>中国</th><th>世界</th></tr>{''.join(trs)}</table>
"""
    return header("中外同期对照表", depth, active="中外对照") + body + footer()


def sources_page(srcdoc, depth):
    order = {"原典": 0, "学术著作": 1, "权威百科": 2, "官方机构": 3}
    srcs = sorted(srcdoc["sources"], key=lambda s: (order.get(s.get("type"), 9), s["id"]))
    rows = []
    marks = {True: '<span class="ok">已核验</span>', "blocked": '<span class="blk">可达/反爬拦截</span>',
             False: '<span class="bad">失败</span>', None: '<span class="meta">离线</span>'}
    for s in srcs:
        link = f'<a href="{esc(s.get("url") or "")}">{esc((s.get("url") or "")[:60])}</a>' if s.get("url") else "—"
        rows.append(f"<tr><td>{esc(s['id'])}</td><td>{esc(s['title'])}</td><td>{esc(s.get('author',''))}</td>"
                    f"<td>{esc(s.get('type',''))}</td><td>{link}</td><td>{marks.get(s.get('link_ok'),'')}</td></tr>")
    body = f"""
<h1>来源列表</h1>
<p class="meta">共 {len(srcs)} 条。原典=史料原典或其权威译本；学术著作=通史/断代史/专题研究；权威百科=Encyclopaedia Britannica、Wikipedia 等；官方机构=博物馆、UNESCO 等。
"可达/反爬拦截"指链接核验时服务器拒绝脚本访问（链接有效）；"离线"指纸本文献无在线全文。</p>
<table><tr><th>id</th><th>题名</th><th>作者/机构</th><th>类型</th><th>链接</th><th>核验</th></tr>{''.join(rows)}</table>
"""
    return header("来源列表", depth, active="来源") + body + footer()


def index_page(china_units, world_units, depth):
    def cnt(units, ev_key, pe_key):
        e = p = 0
        for u in units:
            e += len(u.get(ev_key) or [])
            p += len(u.get(pe_key) or [])
        return e, p

    ch_e, ch_p = cnt(china_units, "events", "people")
    wo_e, wo_p = cnt(world_units, "events", "people")
    ch_xe = sum(len((u.get("_extra") or {}).get("extra_events") or []) for u in china_units)
    wo_xe = sum(len((u.get("_extra") or {}).get("extra_events") or []) for u in world_units)
    ch_xp = sum(len((u.get("_extra") or {}).get("extra_people") or []) for u in china_units)
    wo_xp = sum(len((u.get("_extra") or {}).get("extra_people") or []) for u in world_units)
    n_ev = ch_e + wo_e + ch_xe + wo_xe
    n_pe = ch_p + wo_p + ch_xp + wo_xp
    n_th = sum(len(u.get("_themes") or []) for u in china_units + world_units)
    body = f"""
<h1>镜花水月 · 中外历史脉络库</h1>
<p>一部按"时期—事件—人物"组织的静态历史资料库：中国部分按朝代（先秦至清），世界部分按五大时期（古代文明、古典时代、中世纪、近代早期、近现代）。
每个关键事件页固定包含时间地点、背景、经过、结果、史料与史学争议、示意图、待核实七个部分。</p>
<div class="grid">
<div class="card"><h3><a href="china/">中国部分</a></h3><p>{len(china_units)} 个单元 · 事件 {ch_e}+{ch_xe} 延伸 · 人物 {ch_p}+{ch_xp}</p></div>
<div class="card"><h3><a href="world/">世界部分</a></h3><p>{len(world_units)} 个时期 · 事件 {wo_e}+{wo_xe} 延伸 · 人物 {wo_p}+{wo_xp}</p></div>
<div class="card"><h3><a href="timeline/china.html">中国时间线</a></h3><p>自前2070年至1912年</p></div>
<div class="card"><h3><a href="timeline/world.html">世界时间线</a></h3><p>自约前3500年至1991年</p></div>
<div class="card"><h3><a href="compare/">中外同期对照表</a></h3><p>同年事件并排对照（不做因果解释）</p></div>
<div class="card"><h3><a href="all-events.html">全站事件索引</a></h3><p>{n_ev} 条按公元纪年排序</p></div>
<div class="card"><h3><a href="all-people.html">人物总索引</a></h3><p>{n_pe} 位按出生年排序</p></div>
<div class="card"><h3><a href="centuries.html">世纪总览</a></h3><p>{n_th} 个专题 · 按世纪粒度汇总</p></div>
<div class="card"><h3><a href="graph.html">关系图谱</a></h3><p>单元网络图 + 事件×人物二部关联（纯 SVG 零 JS）</p></div>
<div class="card"><h3><a href="sources/">来源列表</a></h3><p>原典 · 学术著作 · 权威百科 · 官方机构</p></div>
</div>
<h2>阅读须知</h2>
<ul class="tight">
<li>年份一律换算为公元纪年，公元前以"前××××年"表示；换算依据见各事件页"时间"一节括注。</li>
<li>关键年份与事实须由两个独立来源印证；不足者在页面上以"待核实"标注并列出缺口。</li>
<li>争议性事件列明各方说法与史料依据，本站不代读者下结论。</li>
<li>示意图为示意性质，非精确地图或比例。</li>
<li>共 {n_ev} 条事件（含延伸）、{n_pe} 位人物（含其他重要人物）、{n_th} 个专题。</li>
</ul>
"""
    return header("中外历史脉络库", 0, active="首页") + body + footer()


def all_events_page(china, world, depth):
    entries = []
    for u in china + world:
        region = "中国" if u["region"] == "china" else "世界"
        for ev in u["events"]:
            entries.append((ev["year"], 0, region, u, ev, True))
        for xev in (u.get("_extra") or {}).get("extra_events") or []:
            entries.append((xev["year"], 1, region, u, xev, False))
    entries.sort(key=lambda t: (t[0], t[1]))
    rows = []
    for y, is_x, region, u, ev, has_page in entries:
        tag = "<span class='tag warn'>待核实</span>" if ev.get("needs_verification") else ""
        cls = "" if not is_x else " class='meta'"
        piece = f"<a href='events/{u['unit_id']}-{ev['id']}.html'>{esc(ev['title'])}</a>"
        rows.append(f"<tr><td class='year'>{esc(ev['year_display'])}</td><td>{region}</td>"
                    f"<td>{esc(u['title'])}</td><td{cls}>{piece}{tag}</td></tr>")
    body = f"""
<h1>全站事件索引</h1>
<p class="meta">全部 {len(entries)} 条事件（含延伸条目）按公元纪年排序；黑色为关键事件（有详情页），灰色为延伸条目（点入单元页或延伸页）。</p>
<table><tr><th>年份</th><th>地区</th><th>单元</th><th>事件</th></tr>{''.join(rows)}</table>
"""
    return header("全站事件索引", depth, active="索引") + body + footer()


def centuries_page(china, world, depth):
    """世纪总览：按世纪汇总中国/世界条目数与代表性条目。"""
    rows = {}

    def bucket(y):
        if y < 0:
            c = -(((-y + 99) // 100))  # 前1234 → -13（前13世纪）
            label = f"前{-c}世纪"
        else:
            c = (y + 99) // 100
            label = f"{c}世纪"
        return (c, label)

    def add(u, ev, col, is_extra):
        c, label = bucket(ev["year"])
        key = c
        rows.setdefault(key, {"label": label, "china": [], "world": []})
        mark = "·" if is_extra else ""
        piece = f"{mark}{esc(ev['title'])}" if is_extra else \
            f"<a href='{rel(depth)}events/{u['unit_id']}-{ev['id']}.html'>{esc(ev['title'])}</a>"
        rows[key][col].append((u["title"], piece))

    for u in china:
        for ev in u["events"]:
            add(u, ev, "china", False)
        for ev in (u.get("_extra") or {}).get("extra_events") or []:
            add(u, ev, "china", True)
    for u in world:
        for ev in u["events"]:
            add(u, ev, "world", False)
        for ev in (u.get("_extra") or {}).get("extra_events") or []:
            add(u, ev, "world", True)

    trs = []
    for c in sorted(rows):
        r = rows[c]
        cl = "".join(f"<div class='meta'>〔{esc(t)}〕{p}</div>" for t, p in r["china"][:12])
        wl = "".join(f"<div class='meta'>〔{esc(t)}〕{p}</div>" for t, p in r["world"][:12])
        cn = f"（{len(r['china'])} 条）" if r["china"] else ""
        wn = f"（{len(r['world'])} 条）" if r["world"] else ""
        cl = f"<b>{esc(cn)}</b>" if r["china"] else cl
        cl = f"<b>{cn}</b>{cl}" if r["china"] else "—"
        wl = f"<b>{wn}</b>{wl}" if r["world"] else "—"
        trs.append(f"<tr><td class='year'>{esc(r['label'])}</td><td>{cl}</td><td>{wl}</td></tr>")
    body = f"""
<h1>世纪总览</h1>
<p class="meta">以世纪为粒度汇总全部 {sum(len(r['china']) + len(r['world']) for r in rows.values())} 条条目（含延伸条目）；每格列举至多 12 条，"·"前缀为延伸条目。仅并列，不做因果解释。</p>
<table><tr><th>世纪</th><th>中国</th><th>世界</th></tr>{''.join(trs)}</table>
"""
    return header("世纪总览", depth, active="世纪总览") + body + footer()


def all_people_page(china, world, depth):
    entries = []
    for u in china + world:
        region = "中国" if u["region"] == "china" else "世界"
        for p in u["people"]:
            entries.append((p.get("birth_year") if p.get("birth_year") is not None else 99999, region, u, p, True))
        for xp in (u.get("_extra") or {}).get("extra_people") or []:
            entries.append((xp.get("birth_year") if xp.get("birth_year") is not None else 99999, region, u, xp, True))
    entries.sort(key=lambda t: (t[0], t[3].get("name", "")))
    rows = []
    for by, region, u, p, has_page in entries:
        if has_page:
            name = f"<a href='people/{p['id']}.html'>{esc(p.get('name',''))}</a>"
        else:
            name = f"<span class='meta'>{esc(p.get('name',''))}</span>"
        rows.append(f"<tr><td class='year'>{esc(str(p.get('birth_display') or '生卒不可考'))}</td>"
                    f"<td>{region}</td><td>{esc(u['title'])}</td>"
                    f"<td>{name}<br><span class='meta'>{esc((p.get('desc') or '')[:60])}</span></td></tr>")
    body = f"""
<h1>人物总索引</h1>
<p class="meta">全部 {len(entries)} 位人物（含其他重要人物）按出生年排序（生卒不可考者列末）；黑色有详情页，灰色见单元页"其他重要人物"。</p>
<table><tr><th>生年</th><th>地区</th><th>单元</th><th>人物与简介</th></tr>{''.join(rows)}</table>
"""
    return header("人物总索引", depth, active="人物索引") + body + footer()


def glossary_page(terms, depth):
    rows = []
    for t in terms:
        nv = "<span class='tag warn'>待核实</span>" if t.get("needs_verification") else ""
        srcs = "、".join(f"<a class='meta' href='sources/'>{esc(s)}</a>" for s in (t.get("sources") or []))
        rows.append(f"<tr><td class='year'>{esc(t['term'])}</td>"
                    f"<td>{esc(t.get('desc',''))}{nv}</td>"
                    f"<td class='meta'>{srcs}</td></tr>")
    body = f"""
<h1>术语表</h1>
<p class="meta">全站涉及的制度、组织与技术名词（{len(terms)} 条），按词条音序排列；每条注明所属单元与来源。</p>
<table><tr><th>术语</th><th>释义</th><th>来源</th></tr>{''.join(rows)}</table>
"""
    return header("术语表", depth, active="术语表") + body + footer()


def comparative_page(essays, depth):
    sections = []
    for e in essays:
        srcs = "、".join(f"<a class='meta' href='sources/'>{esc(s)}</a>" for s in (e.get("sources") or []))
        nv = "<span class='tag warn'>待核实</span>" if e.get("needs_verification") else ""
        sections.append(f"<h2>{esc(e['title'])}{nv}</h2><p>{esc(e.get('text',''))}</p>"
                        f"<p class='meta'>参考：{srcs}</p>")
    body = f"""
<h1>比较视野</h1>
<p class="meta">跨文明的比较论述：以主题为纲，探讨不同文明对相似挑战的应对——不做因果解释，仅并列分析框架。</p>
{"".join(sections)}
"""
    return header("比较视野", depth, active="比较视野") + body + footer()


def graph_page(china, world, depth):
    """关系图谱页：全站总览 + 18 单元二部网络图（SVG 由 tools/graph_core.py 生成，零 JS）。"""
    import graph_core
    secs = [f"""
<h1>关系图谱</h1>
<p class="meta">由数据自动生成的可视化网络图（纯 SVG，节点可点击跳转、悬停显示详情，无需脚本）。
总览图用确定性力导向布局，单元图用「事件×人物」双列二部结构——同一数据重复生成结果一致。</p>

<h2>全站总览：单元网络</h2>
<p>18 个单元的宏观结构——节点大小为该单元条目数（事件+人物），<b>实线</b>连接同区域内时间顺序相邻的单元，
<b>虚线</b>连接年代区间重叠的中外单元（同期并存，仅并列，不做因果解释）。</p>
<figure>{graph_core.overview_svg(china, world, depth)}
<figcaption>全站单元网络总览：深蓝=中国单元，浅蓝=世界单元；点击节点进入单元总览页</figcaption></figure>

<h2>单元关系图</h2>
<p>每个单元一张「事件 × 人物」二部图：左列为<b>主事件</b>（按年代竖排，圆点大小=关联人物数），右列为<b>人物</b>（含其他重要人物），
连线表示该人物参与该事件（key_people）。延伸事件没有人物关联字段，不入图，见各单元总览页。</p>
"""]
    tot_e = tot_p = tot_x = 0
    for u in china + world:
        svg, st = graph_core.unit_graph_svg(u, depth)
        tot_e += st["events"]; tot_p += st["people"]; tot_x += len((u.get("_extra") or {}).get("extra_events") or [])
        n_th = len(u.get("_themes") or [])
        caption = (f"{esc(u['title'])}：主事件 {st['events']} · 人物 {st['people']} · 关联边 {st['edges']}"
                   f"（另有延伸事件 {len((u.get('_extra') or {}).get('extra_events') or [])} 条未入图；专题 {n_th} 篇）")
        secs.append(f"""
<h3><a href="{rel(depth)}{u['region']}/{u['unit_id']}/">{esc(u['title'])}</a></h3>
<figure>{svg}<figcaption>{caption}</figcaption></figure>""")
    secs.append(f"""
<h2>统计</h2>
<p>本页共 {1 + len(china) + len(world)} 张网络图，覆盖主事件 {tot_e} 条、人物 {tot_p} 位；
延伸事件 {tot_x} 条因无人物关联数据不入图。</p>
<p class="meta">图谱只呈现数据中已有的结构化关联（key_people 与单元年代区间），不推断未记载的因果或人际网络。</p>
""")
    return header("关系图谱", depth, active="关系图谱") + "".join(secs) + footer()


def main():
    srcdoc = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
    srcmap = {s["id"]: s for s in srcdoc["sources"]}

    units = {}
    for fp in sorted(glob.glob(os.path.join(ROOT, "data", "*", "*.json"))):
        norm = fp.replace("\\", "/")
        if any(f"/{sub}/" in norm for sub in ("enrich", "enrich2", "themes", "glossary", "comparative")):
            continue
        doc = json.load(open(fp, encoding="utf-8"))
        doc["_pmap"] = {p["id"]: p for p in doc.get("people") or []}
        units[doc["unit_id"]] = doc
    # 延伸条目（丰富扩展）：data/enrich/*.json 按 unit_id 合并（支持每单元多个文件）
    for u in units.values():
        u["_extra"] = {"extra_events": [], "extra_people": []}
    for fp in sorted(glob.glob(os.path.join(ROOT, "data", "enrich", "*.json"))):
        ed = json.load(open(fp, encoding="utf-8"))
        u = units.get(ed.get("unit_id"))
        if u is None:
            print(f"!! 延伸文件 {os.path.basename(fp)} 的 unit_id 无对应单元，跳过")
            continue
        u["_extra"]["extra_events"].extend(ed.get("extra_events") or [])
        u["_extra"]["extra_people"].extend(ed.get("extra_people") or [])
    for u in units.values():
        u["_extra"]["extra_events"].sort(key=lambda e: (e.get("year", 0), e.get("id", "")))
    # 专题层：data/themes/*.json 按 unit_id 合并
    for fp in sorted(glob.glob(os.path.join(ROOT, "data", "themes", "*.json"))):
        td = json.load(open(fp, encoding="utf-8"))
        u = units.get(td.get("unit_id"))
        if u is None:
            print(f"!! 专题文件 {os.path.basename(fp)} 的 unit_id 无对应单元，跳过")
            continue
        u["_themes"] = td.get("themes") or []
    # 人物升级层：data/enrich2/*.json 按 id 并入（chronology/evaluations 字段升级）
    comparative = []
    for fp in sorted(glob.glob(os.path.join(ROOT, "data", "comparative", "*.json"))):
        cd = json.load(open(fp, encoding="utf-8"))
        comparative.extend(cd.get("essays") or [])
    glossary = []
    for fp in sorted(glob.glob(os.path.join(ROOT, "data", "enrich2", "*.json"))):
        ud = json.load(open(fp, encoding="utf-8"))
        u = units.get(ud.get("unit_id"))
        if u is None:
            continue
        people_by_id = {p["id"]: p for p in (u.get("people") or []) + ((u.get("_extra") or {}).get("extra_people") or [])}
        for up in ud.get("upgrades") or []:
            p = people_by_id.get(up.get("id"))
            if p is not None:
                p.update({k: v for k, v in up.items() if k != "id"})
    glossary_files = sorted(glob.glob(os.path.join(ROOT, "data", "glossary", "*.json")))
    for fp in glossary_files:
        gd = json.load(open(fp, encoding="utf-8"))
        glossary.extend(gd.get("terms") or [])
    glossary.sort(key=lambda t: t.get("term", ""))
    china = sorted([u for u in units.values() if u["region"] == "china"], key=lambda u: u["start_year"])
    world = sorted([u for u in units.values() if u["region"] == "world"], key=lambda u: u["start_year"])

    if os.path.isdir(SITE):
        shutil.rmtree(SITE)

    write("index.html", index_page(china, world, 0))
    write("all-events.html", all_events_page(china, world, 0))
    write("all-people.html", all_people_page(china, world, 0))
    write("centuries.html", centuries_page(china, world, 0))
    write("graph.html", graph_page(china, world, 0))
    write("glossary.html", glossary_page(glossary, 0))
    write("comparative.html", comparative_page(comparative, 0))
    write("china/index.html", unit_list_page(china, "china", "中国部分（按朝代）", 1))
    write("world/index.html", unit_list_page(world, "world", "世界部分（按时期）", 1))
    write("timeline/china.html", timeline_page(china, "china", 1))
    write("timeline/world.html", timeline_page(world, "world", 1))
    write("compare/index.html", compare_page(china, world, 1))
    write("sources/index.html", sources_page(srcdoc, 1))

    for u in china + world:
        # 单元页在 {region}/{unit}/ 两层深 → depth=2；事件/人物页在 events/、people/ 一层深 → depth=1
        write(f"{u['region']}/{u['unit_id']}/index.html", unit_page(u, srcmap, 2))
        for ev in u["events"]:
            page, _tag = event_page(u, ev, srcmap, 1)
            write(f"events/{u['unit_id']}-{ev['id']}.html", page)
        for p in u["people"]:
            write(f"people/{p['id']}.html", person_page(u, p, srcmap, 1))
        for xp in (u.get("_extra") or {}).get("extra_people") or []:
            if xp.get("chronology"):
                write(f"people/{xp['id']}.html", person_page(u, xp, srcmap, 1))
            else:
                write(f"people/{xp['id']}.html", extra_person_page(u, xp, srcmap, 1))
        for xev in (u.get("_extra") or {}).get("extra_events") or []:
            xpage, _ = extra_event_page(u, xev, srcmap, 1)
            write(f"events/{u['unit_id']}-{xev['id']}.html", xpage)

    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "assets", "style.css"),
                os.path.join(SITE, "assets", "style.css"))

    n_files = sum(len(fs) for _, _, fs in os.walk(SITE))
    print(f"site/ 生成完毕：{len(china)} 中国单元, {len(world)} 世界单元, {n_files} 个文件")


if __name__ == "__main__":
    main()
