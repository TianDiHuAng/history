# -*- coding: utf-8 -*-
"""check.py — 中外历史脉络库数据校验器（阶段2）

用法：
  python tools/check.py            # 校验 data/ 下全部单元 JSON
  python tools/check.py --file data/china/qin.json   # 只报告指定文件的问题（仍加载全局上下文）
退出码：0=无 error（warning 不影响）；1=有 error。

数据 schema（每单元一个 JSON 文件，位于 data/china/ 或 data/world/）：
{
  "unit_id": str, 全局唯一, 建议形如 "china-qin" / "world-classical"
  "region": "china" | "world"
  "title": str
  "period_display": str            # 如 "前221年—前207年"
  "start_year": int, "end_year": int   # 负数=公元前
  "overview": {
      "main_threads": [str, ...],      # 线索 ≥1
      "sub_periods": [{"name": str, "range_display": str, "desc": str}, ...],  # 分期 ≥1
      "key_changes": [str, ...]        # 重要变化 ≥1
  },
  "events": [{
      "id": str (unit 内唯一),
      "title": str,
      "year": int, "end_year": int|null,     # 负数=公元前
      "year_display": str, "end_year_display": str|null,
      "year_note": str,                # 换算依据（公元前/干支/帝号纪年须写明依据）
      "location": str,
      "key_people": [person_id, ...],  # 必须引用本单元 people[].id（可为空数组）
      "background": str,               # 背景与起因
      "process": [str, ...],           # 经过（按时间顺序）≥1
      "outcome": str,                  # 结果与影响
      "controversies": [{"issue": str, "views": [{"holder": str, "basis": str}, ...]}, ...],  # ≥1
      "svg": str,                      # 内联 SVG（流程图或地图式示意图）
      "sources": [source_id, ...],     # 对应 sources.json；<2 个则必须 needs_verification
      "needs_verification": bool,
      "pending_notes": str             # 待核实（needs_verification=true 时必须非空）
  }, ...],
  "people": [{
      "id": str, 全局唯一,
      "name": str,
      "birth_year": int|null, "death_year": int|null,
      "birth_display": str, "death_display": str,   # 不可考时写"生卒不可考/约…"并给 note
      "birth_note": str, "death_note": str,         # 换算依据或存疑说明
      "chronology": [{"year": int, "display": str, "text": str}, ...],  # 年谱 ≥1
      "deeds": [str, ...],             # 主要事迹 ≥1
      "evaluations": [{"holder": str, "view": str, "basis": str}, ...], # 评价分歧 ≥1
      "sources": [source_id, ...]
  }, ...]
}

校验规则（对应任务书硬性规则）：
 R1 年份合法（含公元前负数表示）；R2 事件按 year 升序；R3 人物生卒年与事件年份矛盾检测；
 R4 来源引用合法且双源规则；R5 重复检测；R6 SVG 合法性；R7 计数（事件10-15、人物5-8）；
 R8 展示年份与数值年份一致；R9 全局 id 唯一；R10 完整性（必填字段/非空）。
"""
import json
import re
import sys
import io
import glob
import os
import argparse
import xml.etree.ElementTree as ET

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_GLOBS = ["data/china/*.json", "data/world/*.json"]
ENRICH_GLOB = "data/enrich/*.json"
THEMES_GLOB = "data/themes/*.json"
GLOSSARY_GLOB = "data/glossary/*.json"
SOURCES_FILE = "sources.json"

ALLOWED_SVG_TAGS = {
    "svg", "g", "defs", "marker", "rect", "circle", "ellipse", "line", "polyline",
    "polygon", "path", "text", "tspan", "title", "desc"
}
FORBIDDEN_SVG_TAGS = {"script", "foreignObject", "iframe", "image", "object", "embed", "a"}
EVENT_MIN, EVENT_MAX = 10, 15
PEOPLE_MIN, PEOPLE_MAX = 5, 8


class Rep:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, where, msg):
        self.errors.append(f"[E] {where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"[W] {where}: {msg}")


def year_valid(y):
    return isinstance(y, int) and not isinstance(y, bool) and -6000 <= y <= 2100


def display_year_matches(display, year):
    """display 中出现的第一个数字应等于 abs(year)。"""
    if not isinstance(display, str) or not display:
        return False
    m = re.search(r"\d+", display)
    if not m:
        return False
    return int(m.group()) == abs(int(year))


def check_svg(svg, rep, where):
    if not isinstance(svg, str) or len(svg) < 80:
        rep.err(where, "SVG 缺失或过短（每事件须一图）")
        return
    if len(svg) > 40000:
        rep.err(where, f"SVG 过大（{len(svg)} 字符 > 40000）")
        return
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as e:
        rep.err(where, f"SVG XML 解析失败: {e}")
        return
    tag = root.tag.split("}")[-1]
    if tag != "svg":
        rep.err(where, f"根元素不是 <svg> 而是 <{tag}>")
        return
    if not root.get("viewBox"):
        rep.err(where, "SVG 缺少 viewBox 属性")
        return
    low = svg.lower()
    for bad in FORBIDDEN_SVG_TAGS:
        if f"<{bad}" in low:
            rep.err(where, f"SVG 含禁用元素 <{bad}>")
            return
    if "<script" in low or "javascript:" in low:
        rep.err(where, "SVG 含脚本内容")
        return
    # 遍历检查 on* 事件属性与外链
    for el in root.iter():
        t = el.tag.split("}")[-1]
        if t in FORBIDDEN_SVG_TAGS:
            rep.err(where, f"SVG 含禁用元素 <{t}>")
            return
        if t not in ALLOWED_SVG_TAGS:
            rep.err(where, f"SVG 使用了不推荐元素 <{t}>（白名单外）")
            return
        for k, v in (el.attrib or {}).items():
            kk = k.split("}")[-1].lower()
            if kk.startswith("on"):
                rep.err(where, f"SVG 含事件属性 {k}")
                return
            if kk in ("href", "xlink:href") and ("http" in str(v).lower() or "url(" in str(v).lower()):
                rep.err(where, "SVG 含外部链接引用")
                return
    for text in root.itertext():
        if "http" in text.lower():
            rep.warn(where, "SVG 文本中出现 URL，请确认是否必要")


def require(cond, rep, where, msg):
    if not cond:
        rep.err(where, msg)


def check_unit(doc, all_docs, src_ids, src_dead, rep):
    uid = doc.get("unit_id", "?")
    where = f"unit:{uid}"
    # ---- 元信息 ----
    for k in ("unit_id", "region", "title", "period_display", "overview", "events", "people"):
        require(k in doc, rep, where, f"缺少必填字段 {k}")
    if doc.get("region") not in ("china", "world"):
        rep.err(where, f"region 必须为 china/world，现为 {doc.get('region')}")
    sy, ey = doc.get("start_year"), doc.get("end_year")
    require(year_valid(sy), rep, where, f"start_year 非法: {sy}")
    require(year_valid(ey), rep, where, f"end_year 非法: {ey}")
    if year_valid(sy) and year_valid(ey) and sy > ey:
        rep.err(where, f"start_year({sy}) > end_year({ey})")

    ov = doc.get("overview") or {}
    for k in ("main_threads", "sub_periods", "key_changes"):
        require(bool(ov.get(k)), rep, where, f"overview.{k} 缺失或为空（总览页需含线索/分期/重要变化）")
    for sp in ov.get("sub_periods") or []:
        require(isinstance(sp, dict) and sp.get("name") and sp.get("range_display") and sp.get("desc"),
                rep, where, f"overview.sub_periods 项缺少 name/range_display/desc: {sp}")

    events = doc.get("events") or []
    people = doc.get("people") or []

    # ---- R7 计数 ----
    if not (EVENT_MIN <= len(events) <= EVENT_MAX):
        rep.err(where, f"事件数 {len(events)} 不在 [{EVENT_MIN},{EVENT_MAX}]")
    if not (PEOPLE_MIN <= len(people) <= PEOPLE_MAX):
        rep.err(where, f"人物数 {len(people)} 不在 [{PEOPLE_MIN},{PEOPLE_MAX}]")

    # ---- 人物 ----
    pids = {}
    for p in people:
        pw = f"{where}/person:{p.get('id', '?')}"
        for k in ("id", "name", "birth_display", "death_display", "chronology", "deeds", "evaluations", "sources"):
            require(k in p, rep, pw, f"人物缺少必填字段 {k}")
        pid = p.get("id")
        if pid:
            pids[pid] = p
        by, dy = p.get("birth_year"), p.get("death_year")
        if by is not None:
            require(year_valid(by), rep, pw, f"出生年非法: {by}")
            require(display_year_matches(p.get("birth_display"), by), rep, pw,
                    f"birth_display({p.get('birth_display')}) 与 birth_year({by}) 不一致")
        else:
            bd = p.get("birth_display", "")
            require("不可考" in bd or "?" in bd or "约" in bd or "不详" in bd,
                    rep, pw, f"出生年未给定时，birth_display 须标注'不可考/约/不详'：{bd}")
        if dy is not None:
            require(year_valid(dy), rep, pw, f"卒年非法: {dy}")
            require(display_year_matches(p.get("death_display"), dy), rep, pw,
                    f"death_display({p.get('death_display')}) 与 death_year({dy}) 不一致")
        else:
            dd = p.get("death_display", "")
            require("不可考" in dd or "?" in dd or "约" in dd or "不详" in dd,
                    rep, pw, f"卒年未给定时，death_display 须标注'不可考/约/不详'：{dd}")
        if by is not None and dy is not None and by > dy:
            rep.err(pw, f"出生年({by}) > 卒年({dy})")
        require(isinstance(p.get("birth_note"), str) and isinstance(p.get("death_note"), str),
                rep, pw, "birth_note/death_note 须为字符串（可为空串但须存在）")
        chr_ = p.get("chronology") or []
        require(len(chr_) >= 1, rep, pw, "年谱 chronology 至少 1 条")
        for c in chr_:
            cy = c.get("year")
            require(year_valid(cy), rep, pw, f"年谱年份非法: {cy}")
            if year_valid(cy):
                if by is not None and cy < by - 2:
                    rep.err(pw, f"年谱年份 {cy} 早于出生年 {by}（若为追述须在 text 说明）")
                if dy is not None and cy > dy + 2:
                    rep.err(pw, f"年谱年份 {cy} 晚于卒年 {dy}（身后事项须在 text 说明）")
        require(len(p.get("deeds") or []) >= 1, rep, pw, "主要事迹 deeds 至少 1 条")
        ev2 = p.get("evaluations") or []
        require(len(ev2) >= 1, rep, pw, "评价分歧 evaluations 至少 1 条（含至少两种观点更佳）")
        for e in ev2:
            require(e.get("holder") and e.get("view"), rep, pw, "evaluations 项须含 holder/view")
        check_sources(p.get("sources"), src_ids, src_dead, rep, pw, is_person=True)

    # ---- 事件 ----
    prev_year = None
    seen_titles = {}
    for ev in events:
        ew = f"{where}/event:{ev.get('id', '?')}"
        for k in ("id", "title", "year", "year_display", "year_note", "location", "key_people",
                  "background", "process", "outcome", "controversies", "svg", "sources",
                  "needs_verification", "pending_notes"):
            require(k in ev, rep, ew, f"事件缺少必填字段 {k}")
        y = ev.get("year")
        require(year_valid(y), rep, ew, f"事件年份非法: {y}")
        require(display_year_matches(ev.get("year_display"), y), rep, ew,
                f"year_display({ev.get('year_display')}) 与 year({y}) 不一致")
        require(isinstance(ev.get("year_note"), str) and ev["year_note"].strip(),
                rep, ew, "year_note（换算依据）必须非空")
        if y is not None and y < 0:
            require(re.search(r"据|换算|断代|公元前|公历|通行|通说", ev.get("year_note", "")),
                    rep, ew, "公元前年份的 year_note 应说明换算依据")
        ey2 = ev.get("end_year")
        if ey2 is not None:
            require(year_valid(ey2), rep, ew, f"end_year 非法: {ey2}")
            require(display_year_matches(ev.get("end_year_display"), ey2), rep, ew,
                    f"end_year_display 与 end_year({ey2}) 不一致")
            if y is not None and ey2 < y:
                rep.err(ew, f"end_year({ey2}) < year({y})")
        # R2 顺序
        if y is not None and prev_year is not None and y < prev_year:
            rep.err(ew, f"事件年份 {y} 早于前一事件 {prev_year}（未按时间顺序）")
        if y is not None:
            prev_year = max(prev_year, y) if prev_year is not None else y
        # 事件与单元期界
        if y is not None and year_valid(sy) and year_valid(ey):
            if not (sy - 40 <= y <= ey + 2):
                rep.warn(ew, f"事件年份 {y} 超出单元期界 [{sy},{ey}]，若属跨期背景请在正文说明")
        # key_people 引用
        for kp in ev.get("key_people") or []:
            if kp not in pids:
                rep.err(ew, f"key_people 引用的 {kp} 不在本单元 people 列表")
            else:
                pe = pids[kp]
                by, dy = pe.get("birth_year"), pe.get("death_year")
                if y is not None and by is not None and y < by:
                    rep.err(ew, f"关键人物 {kp} 事件年份 {y} 早于其出生年 {by}（若为追述请改引或说明）")
                if y is not None and dy is not None and y > dy:
                    rep.err(ew, f"关键人物 {kp} 事件年份 {y} 晚于其卒年 {dy}（身后影响请改引或说明）")
        # 必填内容非空
        require(bool(str(ev.get("background") or "").strip()), rep, ew, "background 为空")
        require(len(ev.get("process") or []) >= 1, rep, ew, "process 至少 1 条")
        require(bool(str(ev.get("outcome") or "").strip()), rep, ew, "outcome 为空")
        ctv = ev.get("controversies") or []
        require(len(ctv) >= 1, rep, ew, "controversies（史料来源与史学争议）至少 1 条")
        for c in ctv:
            require(c.get("issue"), rep, ew, "controversies 项须含 issue")
            require(len(c.get("views") or []) >= 1, rep, ew, "controversies.views 至少 1 种说法")
        # 数字类事实须附来源：粗查正文带数量词的数字（年份类数字不触发）
        body = f"{ev.get('background','')}{''.join(ev.get('process') or [])}{ev.get('outcome','')}"
        for m in re.finditer(r"前?\d[\d,\.]{2,}\s*(?:万|亿|%|人以上|余人|余万|余骑|余级|吨)", body):
            num = m.group()
            rep.warn(ew, f"正文中含数量词数字 {num}，请确认已括注来源或移入待核实")
            break
        # 待核实
        nv = ev.get("needs_verification")
        require(isinstance(nv, bool), rep, ew, "needs_verification 须为布尔值")
        pn = ev.get("pending_notes") or ""
        require(isinstance(pn, str), rep, ew, "pending_notes 须为字符串")
        if nv and not pn.strip():
            rep.err(ew, "needs_verification=true 但 pending_notes（待核实）为空")
        check_sources(ev.get("sources"), src_ids, src_dead, rep, ew, is_person=False)
        if len(set(ev.get("sources") or [])) < 2 and not ev.get("needs_verification"):
            rep.err(ew, "事件独立来源不足 2 条（双源规则），须置 needs_verification=true 并写明待核实事项")
        check_svg(ev.get("svg"), rep, ew)
        t = ev.get("title")
        if t:
            key = re.sub(r"\s", "", t)
            if key in seen_titles:
                rep.err(ew, f"单元内事件标题重复: {t}")
            seen_titles[key] = True
    return pids


def check_sources(sources, src_ids, src_dead, rep, where, is_person):
    srcs = sources or []
    require(len(srcs) >= 1, rep, where, "来源 sources 至少 1 条")
    for s in srcs:
        if s not in src_ids:
            rep.err(where, f"来源 id 未在 sources.json 中定义: {s}")
        elif s in src_dead:
            rep.warn(where, f"引用的来源 {s} 链接核验失败（link_ok=false），请在待核实中说明")
    if len(set(srcs)) != len(srcs):
        rep.err(where, "sources 存在重复条目")


def check_enrich(ed, unit, all_extra_pids, all_extra_eids, all_extra_ekeys, src_ids, src_dead, rep, target_only):
    """R11：延伸事件/其他重要人物校验（轻量 schema，服务于"丰富各时期"扩展）。"""
    uid = ed.get("unit_id", "?")
    where = f"enrich:{uid}"
    if unit is None:
        rep.err(where, f"unit_id {uid} 无对应的单元数据文件")
        return
    sy, ey = unit.get("start_year"), unit.get("end_year")
    main_keys = {(e.get("year"), re.sub(r"\s", "", e.get("title", ""))) for e in unit.get("events") or []}
    unit_ekeys = all_extra_ekeys.setdefault(uid, set())
    unit_eids = all_extra_eids.setdefault(uid, set())
    xes = ed.get("extra_events") or []
    require(len(xes) <= 20, rep, where, f"延伸事件数 {len(xes)} 超过 20")
    prev = None
    seen = set()
    for ev in xes:
        ew = f"{where}/extra:{ev.get('id', '?')}"
        for k in ("id", "title", "year", "year_display", "year_note", "desc", "sources", "needs_verification", "pending_notes"):
            require(k in ev, rep, ew, f"延伸事件缺少字段 {k}")
        y = ev.get("year")
        require(year_valid(y), rep, ew, f"年份非法: {y}")
        require(display_year_matches(ev.get("year_display"), y), rep, ew,
                f"year_display({ev.get('year_display')}) 与 year({y}) 不一致")
        require(isinstance(ev.get("year_note"), str) and ev["year_note"].strip(), rep, ew, "year_note 必须非空")
        if y is not None and y < 0:
            require(re.search(r"据|换算|断代|公元前|公历|通行|通说", ev.get("year_note", "")),
                    rep, ew, "公元前年份的 year_note 应说明换算依据")
        require(bool(str(ev.get("desc") or "").strip()), rep, ew, "desc 为空")
        require(isinstance(ev.get("needs_verification"), bool), rep, ew, "needs_verification 须为布尔")
        pn = ev.get("pending_notes") or ""
        if ev.get("needs_verification") and not pn.strip():
            rep.err(ew, "needs_verification=true 但 pending_notes 为空")
        check_sources(ev.get("sources"), src_ids, src_dead, rep, ew, is_person=False)
        if len(set(ev.get("sources") or [])) < 2 and not ev.get("needs_verification"):
            rep.err(ew, "延伸事件来源不足 2 条，须置 needs_verification=true")
        if y is not None and year_valid(sy) and year_valid(ey):
            if not (sy - 40 <= y <= ey + 2):
                rep.warn(ew, f"年份 {y} 超出单元期界 [{sy},{ey}]")
        if y is not None and prev is not None and y < prev:
            rep.err(ew, f"年份 {y} 早于前一延伸事件 {prev}（未按时间顺序）")
        if y is not None:
            prev = y
        t = re.sub(r"\s", "", ev.get("title", ""))
        if (y, t) in main_keys:
            rep.err(ew, f"与主事件重复（{y}, {ev.get('title')}）")
        if (y, t) in unit_ekeys:
            rep.err(ew, f"与其他延伸文件中的条目重复（{y}, {ev.get('title')}）")
        unit_ekeys.add((y, t))
        if ev.get("id") in seen:
            rep.err(ew, "延伸事件 id 重复")
        if ev.get("id") in unit_eids:
            rep.err(ew, f"延伸事件 id 与其他延伸文件重复: {ev.get('id')}（页面文件会互相覆盖）")
        seen.add(ev.get("id"))
        unit_eids.add(ev.get("id"))

    xps = ed.get("extra_people") or []
    require(len(xps) <= 10, rep, where, f"其他人物数 {len(xps)} 超过 10")
    for p in xps:
        pw = f"{where}/xperson:{p.get('id', '?')}"
        for k in ("id", "name", "birth_display", "death_display", "desc", "sources"):
            require(k in p, rep, pw, f"其他人物缺少字段 {k}")
        require(bool(str(p.get("desc") or "").strip()), rep, pw, "desc 为空")
        by, dy = p.get("birth_year"), p.get("death_year")
        if by is not None:
            require(year_valid(by), rep, pw, f"出生年非法: {by}")
            require(display_year_matches(p.get("birth_display"), by), rep, pw,
                    f"birth_display 与 birth_year({by}) 不一致")
        else:
            bd = str(p.get("birth_display") or "")
            require("不可考" in bd or "?" in bd or "约" in bd or "不详" in bd,
                    rep, pw, f"出生年未给定时须标注'不可考/约/不详'：{bd}")
        if dy is not None:
            require(year_valid(dy), rep, pw, f"卒年非法: {dy}")
            require(display_year_matches(p.get("death_display"), dy), rep, pw,
                    f"death_display 与 death_year({dy}) 不一致")
        else:
            dd = str(p.get("death_display") or "")
            require("不可考" in dd or "?" in dd or "约" in dd or "不详" in dd,
                    rep, pw, f"卒年未给定时须标注'不可考/约/不详'：{dd}")
        if by is not None and dy is not None and by > dy:
            rep.err(pw, f"出生年({by}) > 卒年({dy})")
        check_sources(p.get("sources"), src_ids, src_dead, rep, pw, is_person=True)
        if p.get("id") in all_extra_pids:
            rep.err(pw, f"其他人物 id 全局重复: {p.get('id')}")
        all_extra_pids.add(p.get("id"))


def check_themes(td, unit, src_ids, src_dead, rep):
    """R12：专题校验（经济社会文化技术维度，服务于"丰富各时期"）。"""
    uid = td.get("unit_id", "?")
    where = f"themes:{uid}"
    if unit is None:
        rep.err(where, f"unit_id {uid} 无对应的单元数据文件")
        return
    themes = td.get("themes") or []
    require(3 <= len(themes) <= 8, rep, where, f"专题数 {len(themes)} 应在 3—8 之间")
    seen = set()
    for t in themes:
        tw = f"{where}/theme:{t.get('title', '?')}"
        for k in ("title", "text", "sources"):
            require(k in t, rep, tw, f"专题缺少字段 {k}")
        require(bool(str(t.get("title") or "").strip()), rep, tw, "title 为空")
        body = str(t.get("text") or "")
        require(len(body.strip()) >= 40, rep, tw, "text 过短（专题应至少一段实质内容）")
        title = re.sub(r"\s", "", t.get("title", ""))
        if title in seen:
            rep.err(tw, "专题标题重复")
        seen.add(title)
        srcs = t.get("sources") or []
        require(len(srcs) >= 1, rep, tw, "来源至少 1 条")
        for s in srcs:
            if s not in src_ids:
                rep.err(tw, f"来源 id 未在 sources.json 中定义: {s}")
        if len(set(srcs)) < 2 and not t.get("needs_verification"):
            rep.err(tw, "专题来源不足 2 条，须置 needs_verification=true（或补足双源）")
        nv = t.get("needs_verification", False)
        require(isinstance(nv, bool), rep, tw, "needs_verification 须为布尔值")


def check_glossary(gd, unit_by_id, src_ids, src_dead, rep):
    """R13：术语表校验（term/desc/unit_id/sources）。"""
    where = "glossary"
    terms = gd.get("terms") or []
    require(len(terms) >= 20, rep, where, f"术语数 {len(terms)} 少于 20（术语表应成规模）")
    seen = set()
    for t in terms:
        tw = f"{where}/term:{t.get('term', '?')}"
        for k in ("term", "desc", "unit_id", "sources"):
            require(k in t, rep, tw, f"术语缺少字段 {k}")
        require(bool(str(t.get("term") or "").strip()), rep, tw, "term 为空")
        body = str(t.get("desc") or "")
        require(len(body.strip()) >= 20, rep, tw, "desc 过短")
        key = t.get("term")
        if key in seen:
            rep.err(tw, "术语重复")
        seen.add(key)
        u = unit_by_id.get(t.get("unit_id"))
        require(u is not None, rep, tw, f"unit_id 无对应单元: {t.get('unit_id')}")
        srcs = t.get("sources") or []
        require(len(srcs) >= 1, rep, tw, "来源至少 1 条")
        for s in srcs:
            if s not in src_ids:
                rep.err(tw, f"来源 id 未在 sources.json 中定义: {s}")
        if len(set(srcs)) < 2 and not t.get("needs_verification"):
            rep.err(tw, "术语来源不足 2 条，须置 needs_verification=true")
        nv = t.get("needs_verification", False)
        require(isinstance(nv, bool), rep, tw, "needs_verification 须为布尔值")


def check_person_upgrade(up, unit, all_people_by_id, rep):
    """R14：人物升级校验（为其他重要人物补年谱与评价，字段并入原条目）。"""
    uid = up.get("unit_id", "?")
    where = f"upgrade:{uid}"
    if unit is None:
        rep.err(where, f"unit_id {uid} 无对应单元")
        return
    people_by_id = {}
    for p in (unit.get("people") or []) + (unit.get("extra_people") or []):
        people_by_id[p.get("id")] = p
    ups = up.get("upgrades") or []
    require(len(ups) >= 1, rep, where, "upgrades 至少 1 条")
    for u in ups:
        uw = f"{where}/person:{u.get('id', '?')}"
        pid = u.get("id")
        p = people_by_id.get(pid)
        require(p is not None, rep, uw, f"id {pid} 在单元中不存在（升级只能针对已有条目）")
        if p is None:
            continue
        chron = u.get("chronology") or []
        require(len(chron) >= 3, rep, uw, "升级 chronology 至少 3 条")
        by, dy = p.get("birth_year"), p.get("death_year")
        for c in chron:
            cy = c.get("year")
            require(year_valid(cy), rep, uw, f"年谱年份非法: {cy}")
            if year_valid(cy):
                if by is not None and cy < by - 2:
                    rep.err(uw, f"年谱年份 {cy} 早于出生年 {by}")
                if dy is not None and cy > dy + 2:
                    rep.err(uw, f"年谱年份 {cy} 晚于卒年 {dy}")
        evals = u.get("evaluations") or []
        require(len(evals) >= 2, rep, uw, "升级 evaluations 至少 2 种观点")
        for e in evals:
            require(e.get("holder") and e.get("view"), rep, uw, "evaluations 项须含 holder/view")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="只报告该文件的问题（仍加载全部数据做全局检查）")
    args = ap.parse_args()

    rep = Rep()
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        src_doc = json.load(f)
    src_ids = {s["id"] for s in src_doc["sources"]}
    src_dead = {s["id"] for s in src_doc["sources"] if s.get("link_ok") is False}

    files = []
    for g in DATA_GLOBS:
        files.extend(sorted(glob.glob(g)))
    files = [f for f in files if os.path.basename(f) != "_template.json"]
    if not files:
        print("data/ 下暂无单元数据文件（data/china/*.json, data/world/*.json）")
        return 1

    docs, pids_global, uid_seen = {}, set(), {}
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                docs[fp] = json.load(f)
        except Exception as e:
            rep.err(f"file:{fp}", f"JSON 解析失败: {e}")
            continue
        uids = docs[fp].get("unit_id", "")
        if uids in uid_seen:
            rep.err(f"file:{fp}", f"unit_id 重复: {uids}（已在 {uid_seen[uids]} 中定义）")
        uid_seen[uids] = fp
        pids = {p.get("id") for p in docs[fp].get("people") or []}
        dup = pids & pids_global
        if dup:
            rep.err(f"file:{fp}", f"人物 id 与其他单元重复: {sorted(dup)}（全局必须唯一）")
        pids_global |= pids

    for fp, doc in docs.items():
        if args.file and os.path.normpath(fp) != os.path.normpath(args.file):
            # 仍做轻量全局检查，但不报告
            continue
        check_unit(doc, docs, src_ids, src_dead, rep)

    # ---- R11 延伸条目（丰富扩展）校验 ----
    unit_by_id = {d.get("unit_id"): d for d in docs.values()}
    enrich_files = sorted(glob.glob("data/enrich/*.json"))
    all_extra_pids = set(pids_global)
    all_extra_eids = {}
    all_extra_ekeys = {}
    enrich_target = None
    if args.file and "enrich" in args.file.replace("\\", "/"):
        enrich_target = os.path.normpath(args.file)
    for fp in enrich_files:
        if enrich_target is not None and os.path.normpath(fp) != enrich_target:
            continue
        try:
            ed = json.load(open(fp, encoding="utf-8"))
        except Exception as e:
            rep.err(f"file:{fp}", f"JSON 解析失败: {e}")
            continue
        unit = unit_by_id.get(ed.get("unit_id"))
        check_enrich(ed, unit, all_extra_pids, all_extra_eids, all_extra_ekeys, src_ids, src_dead, rep,
                     target_only=(enrich_target is not None))

    # ---- R12 专题校验 ----
    theme_files = sorted(glob.glob("data/themes/*.json"))
    for fp in theme_files:
        if enrich_target is not None:
            continue
        try:
            td = json.load(open(fp, encoding="utf-8"))
        except Exception as e:
            rep.err(f"file:{fp}", f"JSON 解析失败: {e}")
            continue
        check_themes(td, unit_by_id.get(td.get("unit_id")), src_ids, src_dead, rep)

    # ---- R13 术语表 ----
    glossary_files = sorted(glob.glob("data/glossary/*.json"))
    for fp in glossary_files:
        if enrich_target is not None:
            continue
        try:
            gd = json.load(open(fp, encoding="utf-8"))
        except Exception as e:
            rep.err(f"file:{fp}", f"JSON 解析失败: {e}")
            continue
        check_glossary(gd, unit_by_id, src_ids, src_dead, rep)

    # ---- R14 人物升级（enrich2）----
    # 先合并 enrich 数据到 unit 副本（升级条目可指向任何 enrich 层的人物）
    unit_by_id_merged = {}
    for uid, d in unit_by_id.items():
        merged = json.loads(json.dumps(d))
        merged.setdefault("extra_people", [])
        merged.setdefault("extra_events", [])
        for fp2 in enrich_files:
            try:
                ed = json.load(open(fp2, encoding="utf-8"))
            except Exception:
                continue
            if ed.get("unit_id") == uid:
                merged["extra_people"].extend(ed.get("extra_people") or [])
                merged["extra_events"].extend(ed.get("extra_events") or [])
        unit_by_id_merged[uid] = merged
    upgrade_files = sorted(glob.glob("data/enrich2/*.json"))
    for fp in upgrade_files:
        if enrich_target is not None:
            continue
        try:
            ud = json.load(open(fp, encoding="utf-8"))
        except Exception as e:
            rep.err(f"file:{fp}", f"JSON 解析失败: {e}")
            continue
        check_person_upgrade(ud, unit_by_id_merged.get(ud.get("unit_id")), {}, rep)

    # 跨单元重复事件（同 年份+标题）
    seen = {}
    for fp, doc in docs.items():
        for ev in doc.get("events") or []:
            key = (ev.get("year"), re.sub(r"\s", "", ev.get("title", "")))
            if key in seen and seen[key] != fp:
                rep.warn(f"unit:{doc.get('unit_id')}",
                         f"跨单元疑似重复事件（{ev.get('year')}, {ev.get('title')}）也与 {seen[key]} 重复；若为有意的跨视角条目请忽略")
            seen.setdefault(key, fp)

    # 输出
    target = args.file or f"全部文件（{len(docs)} 单元 + {len(enrich_files)} 延伸文件）"
    print(f"=== check.py 校验报告（目标：{target}，共加载 {len(docs)} 个单元）===")
    for w in rep.warnings:
        print(w)
    for e in rep.errors:
        print(e)
    print(f"--- warnings: {len(rep.warnings)} | errors: {len(rep.errors)} ---")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
