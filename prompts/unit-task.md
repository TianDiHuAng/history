# 单元数据编写任务书（供编写代理执行）

本站点数据单元为 JSON 文件，位于 `data/china/`（中国，按朝代）或 `data/world/`（世界，按时期）。每个单元：事件 10–15 个、人物 5–8 个（以 scope.md 各节清单为准，不得增删）。无人值守：不提问，不确定处选保守写法并标"待核实"。

## 工作流程
1. 读 `scope.md` 中分配给你的那一节（清单定稿，事件/人物不得增删；可微调事件标题措辞但年份与内容必须一致）。
2. 读 `sources.json`：只允许引用其中已有的来源 id，不得自创。各单元建议来源见你的派发提示。
3. 读 `tools/check.py` 顶部 docstring 的完整 JSON schema 与校验规则（R1–R10）。
4. 用 Write 写出 `data/china/<unit_id>.json` 或 `data/world/<unit_id>.json`（合法 JSON、UTF-8）。
5. 运行：`cd /d/AI/project/history && PYTHONIOENCODING=utf-8 python -X utf8 tools/check.py --file data/.../<你的文件>`，按报错迭代，直到 errors=0（warnings 读一遍，能消则消）。
6. 完成后向派发方报告（≤200 字）：事件/人物数、check 迭代次数、needs_verification 清单、遗留问题。

## 硬性规则（违反会被 check.py 拒绝）
- **双源规则**：每事件 `sources` ≥2 个不同 id；不足必须 `needs_verification=true` 且 `pending_notes` 写明缺口。人物页来源 ≥1（建议 ≥2）。
- **不编造**：年份、引文、人名、数字（兵力、伤亡、人口、工程规模）一律不得虚构。数字必须正文括注来源；无双重来源移入 `pending_notes`。引文只引你确有把握的原文（如《史记》名句），否则用转述。
- **纪年换算**：`year_note` 写换算依据（例："据《史记·秦始皇本纪》，秦王政二十六年系于前221年"；"约前1300，据夏商周断代工程"；"1843年，公历通行纪年"）。涉及干支、帝号纪年、在位年、异说的必须注明所用体系。
- **争议必须真实**：只写你确知的史学分歧（史书记载差异、现代学界争论），列各方说法+史料依据；不得虚构学者与观点。争议不大的事件写"主要史料记载一致，学界对××的解读有差异/讨论"。
- **key_people** 只能引用本单元 `people` 数组中的 id。人物生卒不确定置 null，display 写"生卒不可考/约××××年"。事件年份与人物生卒矛盾时要么改人物、要么换关键人物、要么说明（如"追述""身后影响"需避免——check 直接报错，请换人或不引用）。
- **计数**：事件 10–15、人物 5–8；人物 id 全站唯一（建议 `<拼音>-<名>`，小写连字符）；事件 id 单元内唯一（建议 `<主题>-<年份或序号>`）。
- **evaluations**：至少 1 条（建议 2–3 条，含传统评价与现代修正；注明出处/依据）。
- **year_display 一致性**：显示年份数字必须与数值年份一致（前221年 ↔ -221）。

## SVG 规范（每事件一图）
- `viewBox` 约 "0 0 760 400"；仅允许元素：svg/g/defs/marker/rect/circle/ellipse/line/polyline/polygon/path/text/tspan/title/desc；禁止 script、image、外链、on* 属性。
- 内容：流程图（marker-end 箭头，按时间/因果步骤）或地图式示意图（方框+连线示意地理/势力关系）。中文标签用通行译名；字号 ≥12；避免文字重叠；元素不越出 viewBox。
- 配色：底 #faf7f0，主色 #2b4a6f，辅色 #8c1f28、#c8a45c；文字 #2c2c28。
- 说明文字放 `<title>` 与页面 figcaption（生成器自动加），SVG 内文字保持简短。

## 文风
说明文、准确克制；无文学修辞、无道德结论；观点放 controversies/evaluations；每段 2–5 句；process 按时间顺序分步（每步 1–2 句）。

## 禁止
- 任何 git 操作；改动 tools/、sources.json、scope.md、prompts/；跨单元改文件；把相邻单元的事件写进本单元。
- 超范围发挥：scope 清单之外的"补充"事件/人物一律不加。
