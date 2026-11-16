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
import shutil
import html
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")


def esc(s):
    return html.escape(str(s if s is not None else ""))


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
        ("compare/", "中外对照"), ("sources/", "来源"),
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
<title>{esc(title)} · 中外历史脉络库</title>
<link rel="stylesheet" href="{rel(depth)}assets/style.css">
</head>
<body>
<header class="site"><span class="brand">中外历史脉络库</span>
<nav>{' | '.join(links)}</nav></header>
<main>'''


def footer():
    return ('''
<p class="meta" style="margin-top:44px">年份均为公元纪年（公元前用负数表示转换）；关键事实以两个独立来源互相印证为标准，未达标者在页内标注"待核实"。</p>
</main>
<footer class="site">本站为静态资料库，内容仅供学习参考，不构成学术结论；引用请核对原始文献。</footer>
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
<figure>{ev.get('svg','')}<figcaption>{esc(ev['title'])}示意图（示意性质，非精确地图/比例）</figcaption></figure>
<h2>七、待核实</h2>
<div class="pending"><p>{esc(pending)}</p></div>
<h2>参考来源</h2>
{src_list_html(ev.get('sources') or [], srcmap, depth)}
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
    body = f"""
<h1>{esc(p.get('name',''))}</h1>
<p class="crumb"><a href="{rel(depth)}{'china/' if unit['region']=='china' else 'world/'}">{esc('中国' if unit['region']=='china' else '世界')}</a> /
<a href="{rel(depth)}{'china' if unit['region']=='china' else 'world'}/{unit['unit_id']}/">{esc(unit['title'])}</a> / 人物</p>
<h2>生卒年</h2>
<p class="kv"><b>生：</b>{esc(str(bd))}{esc(p.get('birth_note') or '')}
&nbsp;&nbsp;<b>卒：</b>{esc(str(dd))}{esc(p.get('death_note') or '')}</p>
<h2>年谱</h2>
<ul class="tight">{chrono}</ul>
<h2>主要事迹</h2>
<ul class="tight">{deeds}</ul>
<h2>评价分歧</h2>
{evals}
<h2>参考来源</h2>
{src_list_html(p.get('sources') or [], srcmap, depth)}
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
    evs = "".join(
        f"<tr><td class='year'>{esc(ev['year_display'])}</td>"
        f"<td><a href='{rel(depth)}events/{uid}-{ev['id']}.html'>{esc(ev['title'])}</a>"
        f"{'<span class=\"tag warn\">待核实</span>' if ev.get('needs_verification') else ''}</td>"
        f"<td>{esc(ev.get('location',''))}</td></tr>"
        for ev in unit["events"])
    ppl = "".join(
        f"<tr><td><a href='{rel(depth)}people/{p['id']}.html'>{esc(p['name'])}</a></td>"
        f"<td>{esc(str(p.get('birth_display') or '生卒不可考'))}—{esc(str(p.get('death_display') or '卒年不可考'))}</td></tr>"
        for p in unit["people"])
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
        rows = []
        for ev in sorted(u["events"], key=lambda e: e["year"]):
            tag = '<span class="tag warn">待核实</span>' if ev.get("needs_verification") else ""
            rows.append(f"<div class='tl-item'><span class='tl-year'>{esc(ev['year_display'])}</span>"
                        f"<a href='{rel(depth)}events/{u['unit_id']}-{ev['id']}.html'>{esc(ev['title'])}</a>{tag}</div>")
        items.append(f"<div class='tl'>{''.join(rows)}</div>")
    body = f"<h1>{cn}时间线</h1><p class='meta'>按年份先后排列；点击事件查看详情。</p>" + "".join(items)
    return header(f"{cn}时间线", depth, active=f"{cn}时间线") + body + footer()


def compare_page(china_units, world_units, depth):
    rows = {}
    for u in china_units:
        for ev in u["events"]:
            rows.setdefault(ev["year"], ["", ""])
            rows[ev["year"]][0] += ("" if not rows[ev["year"]][0] else "<br>") + \
                f"<a href='{rel(depth)}events/{u['unit_id']}-{ev['id']}.html'>{esc(ev['title'])}</a>"
    for u in world_units:
        for ev in u["events"]:
            rows.setdefault(ev["year"], ["", ""])
            rows[ev["year"]][1] += ("" if not rows[ev["year"]][1] else "<br>") + \
                f"<a href='{rel(depth)}events/{u['unit_id']}-{ev['id']}.html'>{esc(ev['title'])}</a>"
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
    n_ev = sum(len(u["events"]) for u in china_units + world_units)
    n_pe = sum(len(u["people"]) for u in china_units + world_units)
    body = f"""
<h1>中外历史脉络库</h1>
<p>一部按"时期—事件—人物"组织的静态历史资料库：中国部分按朝代（先秦至清），世界部分按五大时期（古代文明、古典时代、中世纪、近代早期、近现代）。
每个事件页固定包含时间地点、背景、经过、结果、史料与史学争议、示意图、待核实七个部分。</p>
<div class="grid">
<div class="card"><h3><a href="china/">中国部分</a></h3><p>{len(china_units)} 个单元 · {sum(len(u['events']) for u in china_units)} 事件 · {sum(len(u['people']) for u in china_units)} 人物</p></div>
<div class="card"><h3><a href="world/">世界部分</a></h3><p>{len(world_units)} 个时期 · {sum(len(u['events']) for u in world_units)} 事件 · {sum(len(u['people']) for u in world_units)} 人物</p></div>
<div class="card"><h3><a href="timeline/china.html">中国时间线</a></h3><p>自前2070年至1912年</p></div>
<div class="card"><h3><a href="timeline/world.html">世界时间线</a></h3><p>自约前3500年至1991年</p></div>
<div class="card"><h3><a href="compare/">中外同期对照表</a></h3><p>同年事件并排对照（不做因果解释）</p></div>
<div class="card"><h3><a href="sources/">来源列表</a></h3><p>原典 · 学术著作 · 权威百科 · 官方机构</p></div>
</div>
<h2>阅读须知</h2>
<ul class="tight">
<li>年份一律换算为公元纪年，公元前以"前××××年"表示；换算依据见各事件页"时间"一节括注。</li>
<li>关键年份与事实须由两个独立来源印证；不足者在页面上以"待核实"标注并列出缺口。</li>
<li>争议性事件列明各方说法与史料依据，本站不代读者下结论。</li>
<li>示意图为示意性质，非精确地图或比例。</li>
<li>共 {n_ev} 个事件页、{n_pe} 个人物页。</li>
</ul>
"""
    return header("中外历史脉络库", 0, active="首页") + body + footer()


def main():
    srcdoc = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
    srcmap = {s["id"]: s for s in srcdoc["sources"]}

    units = {}
    for fp in sorted(glob.glob(os.path.join(ROOT, "data", "*", "*.json"))):
        doc = json.load(open(fp, encoding="utf-8"))
        doc["_pmap"] = {p["id"]: p for p in doc.get("people") or []}
        units[doc["unit_id"]] = doc
    china = sorted([u for u in units.values() if u["region"] == "china"], key=lambda u: u["start_year"])
    world = sorted([u for u in units.values() if u["region"] == "world"], key=lambda u: u["start_year"])

    if os.path.isdir(SITE):
        shutil.rmtree(SITE)

    write("index.html", index_page(china, world, 0))
    write("china/index.html", unit_list_page(china, "china", "中国部分（按朝代）", 1))
    write("world/index.html", unit_list_page(world, "world", "世界部分（按时期）", 1))
    write("timeline/china.html", timeline_page(china, "china", 1))
    write("timeline/world.html", timeline_page(world, "world", 1))
    write("compare/index.html", compare_page(china, world, 1))
    write("sources/index.html", sources_page(srcdoc, 1))

    for u in china + world:
        depth = 2 if u["region"] == "china" else 2
        write(f"{u['region']}/{u['unit_id']}/index.html", unit_page(u, srcmap, depth))
        for ev in u["events"]:
            page, _tag = event_page(u, ev, srcmap, depth)
            write(f"events/{u['unit_id']}-{ev['id']}.html", page)
        for p in u["people"]:
            write(f"people/{p['id']}.html", person_page(u, p, srcmap, depth))

    shutil.copy(os.path.join(ROOT, "assets", "style.css"),
                os.path.join(SITE, "assets", "style.css"))

    n_files = sum(len(fs) for _, _, fs in os.walk(SITE))
    print(f"site/ 生成完毕：{len(china)} 中国单元, {len(world)} 世界单元, {n_files} 个文件")


if __name__ == "__main__":
    main()
