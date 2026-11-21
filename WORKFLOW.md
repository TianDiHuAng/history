# 通用知识脉络库工作流 — 可复刻到任意知识域

> 从「中外历史脉络库」项目（487事件/315人物/81专题/96术语/8比较视野，833文件，49 commits）提炼的完整工作流。
> 换成地理、哲学、法学、音乐、医学……任何知识域只需替换内容，架构与流程不变。

---

## 第〇步：理解核心设计理念

**为什么不用 WordPress/Hugo/Notion 而要手写？**

```
JSON 数据层（结构化、可机检）
    ↓ check.py 校验（年份/逻辑/来源/一致性——机器拒绝坏数据）
    ↓ gen_site.py 渲染（确定性输出，数据改了重跑就行）
    ↓ site/ 纯 HTML+CSS（零 JS，可离线，可部署 GitHub Pages）
```

核心价值：
1. **数据与呈现分离**——改数据重跑即可，不用手改 HTML
2. **机器校验强制诚实**——双源规则、待核实、争议并列不是靠自觉，是靠代码拒绝
3. **可扩展**——每加一个新维度（专题/术语/比较）只需新增一个 JSON 层 + 一段渲染逻辑
4. **可复刻**——换内容域只改 JSON 和校验规则，生成器几乎不用动

---

## 第一步：定义 scope（半天）

写一份 `scope.md`，列出所有单元及其入选条目清单。这是全项目的编辑基准线。

```markdown
# scope.md — 入选清单

## 单元划分
按 [你的知识域] 的自然分类划单元（如地理按大洲/气候带，哲学按流派/时代）

### U1 [单元名]（年代/范围）
- 事件/概念/条目 10–15 条（写明名称+一句话说明）
- 人物/代表 5–8 位（写明生卒/活跃期）
- 每条标明 ★争议 或 ▲待核实（如果能预判）
```

**关键决策**（写入 DECISIONS.md）：
- 单元怎么分？（地理按洲/国/气候带？哲学按流派/时代/地域？）
- 什么算"关键条目"？（入选标准）
- 覆盖范围下限（哪些不收）
- 争议条目的处理原则（并列各方说法，不替读者下结论）

---

## 第二步：设计数据 schema（半天）

每单元一个 JSON 文件，包含四层数据。以下是可直接复用的模板：

### 2a. 主事件层（每单元 10–15 条，每条完整七节）

```json
{
  "unit_id": "geo-asia",
  "region": "asia",
  "title": "亚洲",
  "start_year": null,
  "end_year": null,
  "events": [{
    "id": "geo-asia-himalaya",
    "title": "喜马拉雅山脉的形成",
    "year": null,
    "year_display": "约5000万年前",
    "year_note": "据板块构造理论推算（约数）",
    "location": "喜马拉雅山脉",
    "key_people": [],
    "background": "背景描述（2-4句）",
    "process": ["步骤1", "步骤2", "步骤3"],
    "outcome": "结果与影响",
    "controversies": [{
      "issue": "争议问题名",
      "views": [{"holder": "持方A", "basis": "依据A"}, {"holder": "持方B", "basis": "依据B"}]
    }],
    "svg": "<svg xmlns='...' viewBox='0 0 760 400'>...</svg>",
    "sources": ["source_id_1", "source_id_2"],
    "needs_verification": false,
    "pending_notes": ""
  }],
  "people": [{
    "id": "geo-asia-person-xx",
    "name": "人名",
    "birth_year": null,
    "death_year": null,
    "birth_display": "生卒不可考或具体年",
    "death_display": "卒年不可考或具体年",
    "birth_note": "", "death_note": "",
    "chronology": [{"year": null, "display": "约...", "text": "事迹"}],
    "deeds": ["事迹1", "事迹2"],
    "evaluations": [{"holder": "评价者", "view": "观点", "basis": "依据"}],
    "sources": ["source_id_1"]
  }]
}
```

### 2b. 来源层 sources.json（全局一个文件）

```json
{
  "sources": [
    {"id": "source_id", "title": "来源名", "author": "作者/机构",
     "type": "原典/学术著作/权威百科/官方机构",
     "url": "https://...", "url2": "备用URL或null",
     "link_ok": null, "note": "说明"}
  ]
}
```

### 2c. 扩展层（按需逐步添加）

| 层 | 目录 | 文件 schema | 校验规则 |
|---|---|---|---|
| 延伸事件 | `data/enrich/` | `{unit_id, extra_events:[{id,title,year,year_display,year_note,desc,sources,needs_verification,pending_notes}], extra_people:[...]}` | R11 |
| 人物升级 | `data/enrich2/` | `{unit_id, upgrades:[{id, chronology:[...], evaluations:[...]}]}` | R14 |
| 专题论述 | `data/themes/` | `{unit_id, themes:[{title,text,sources,needs_verification}]}` | R12 |
| 术语表 | `data/glossary/` | `{terms:[{term,desc,unit_id,sources,needs_verification}]}` | R13 |
| 比较视野 | `data/comparative/` | `{essays:[{title,text,sources}]}` | R15 |

---

## 第三步：写校验器 check.py（1天）

校验器是整个项目的**质量守门员**——所有内容必须通过才能上线。

### 核心规则（R1–R15，可直接复用）

| 规则 | 校验内容 | 适用层 |
|---|---|---|
| R1 | 字段完整性（必填字段非空） | 全部 |
| R2 | 事件按时间升序排列 | 主事件+延伸 |
| R3 | 人物生卒与事件年份矛盾检测 | 全部 |
| R4 | 来源引用合法性（id 必须在 sources.json 中定义） | 全部 |
| R5 | 重复检测（同单元内 + 跨单元同年份同标题） | 全部 |
| R6 | SVG 合法性（XML 解析、白名单元素、无脚本、viewBox） | 主事件 |
| R7 | 计数限制（主事件 10–15、人物 5–8） | 主层 |
| R8 | 显示年份与数值年份一致（`year_display` 首个数字 = `|year|`） | 全部 |
| R9 | 全局 id 唯一（人物 id 跨单元不可重复） | 全部 |
| R10 | 完整性（必填内容非空、needs_verification 与 pending_notes 联动） | 全部 |
| R11 | 延伸条目校验（跨文件 id+年份标题双查重） | 延伸层 |
| R12 | 专题论述（标题去重、文本长度、双源） | 专题层 |
| R13 | 术语表（去重、unit_id 关联、双源） | 术语层 |
| R14 | 人物升级（年谱年份范围、评价结构、仅针对已有条目） | 升级层 |
| R15 | 比较视野（≥4 篇、≥100 字、双源） | 比较层 |
| R16 | 条目 id 仅允许 `a-z 0-9 -`（引号/ü/大写会破坏链接与文件名） | 全部 |

### 双源规则（最重要的规则）

```
每条事件/专题/术语的 sources 数组 ≥2 个不同 id → 通过
sources <2 个 → 必须 needs_verification=true 且 pending_notes 非空
否则 → 校验报错，拒绝通过
```

这条规则强制每条内容都有可追溯的依据来源，是全项目"诚实标注"体系的技术保障。

---

## 第四步：写生成器 gen_site.py（1天）

生成器从 JSON 渲染静态 HTML，核心功能：

1. **加载顺序**：单元 JSON → enrich 合并（按 id 排序）→ enrich2 合并（按 id 升级字段）→ themes → glossary → comparative
2. **排除目录**：单元加载 glob `data/*/*.json` 时必须排除 enrich/enrich2/themes/glossary/comparative 子目录
3. **页面类型**：
   - 首页（统计卡片导航）
   - 单元总览页 ×N（线索/分期/变化/事件/延伸/专题/人物）
   - 事件详情页 ×N（七节固定结构 + SVG + 导航）
   - 延伸事件详情页 ×N（轻量页：时间/说明/来源/待核实）
   - 人物详情页 ×N（生卒/年谱/事迹/相关事件/评价，条件渲染——extras 无年谱则隐藏年谱节）
   - 时间线 ×2（按年份排序，主事件可点入，延伸灰色）
   - 对照表（两列并排，不做因果解释）
   - 世纪总览（按世纪粒度汇总）
   - 全站事件索引（按年排序）
   - 全站人物索引（按出生年排序）
   - 术语表（按音序）
   - 比较视野（按篇渲染）
   - 来源列表（三态链接核验标注）
4. **SVG 净化**：`sanitize_svg()` 自动修复常见 SVG 笔误（`'/<` → `'/><`、标签栈补齐）
5. **导航栏**：所有板块入口

---

## 第五步：写来源列表 sources.json（半天）

分四类收集：
- **原典**：一手史料/经典文献/数据集（附在线全文链接或标"离线"）
- **学术著作**：权威专著/教材/论文集
- **权威百科**：Britannica/Wikipedia/领域大百科
- **官方机构**：博物馆/研究所/政府/国际组织

每条含：`id`（全站引用键）、`title`、`author`、`type`、`url`、`url2`（备用）、`link_ok`（三态核验结果）、`note`。

**链接核验脚本**（linkcheck.py）分三态：
- `true` = HTTP < 400（可达）
- `"blocked"` = 401/403/429/503（服务器反爬拒绝脚本，URL 有效）
- `false` = 404/DNS 失败/超时（真死链）
- `null` = 离线文献（url=null 不核验）

---

## 第六步：写内容（核心阶段，每单元约1天）

### 编写规约（写入 prompts/ 供 agent 或人工参考）

1. **引号纪律**：JSON 字符串内一律用中文引号""——ASCII 引号未转义会毁 JSON
2. **年份格式**：`year` 用整数（负数=公元前），`year_display` 首个数字必须等于 `|year|`
3. **year_note 必填**：古代/约数年份必须写明换算依据（"据×××""通说""约数"）
4. **SVG 规范**：自闭合标签 `/>`（漏 `>` 是最常犯的错——gen_site 内置自动修复）、元素白名单、viewBox 必填
5. **事件升序**：JSON 数组内按 year 排列（check 会报错）
6. **人物 chronology 年份**必须在生卒范围内（check 会报错）
7. **争议必须真实**：不虚构学者与观点；无大争议的写"记载一致，学界对 X 有讨论"
8. **数字纪律**：兵力/伤亡/人口等必须括注来源；单源数字移入待核实
9. **key_people** 只能引用本单元 people 数组中的 id

### Agent 辅助编写模式

```
主线程（你/agent A）          后台代理（agent B，串行）
    │                              │
    ├─ 写单元 A ──────┐            │
    ├─ 写单元 B        ├─ 写单元 C │
    ├─ 校验 A+B ──────┤            │
    ├─ 写单元 D        ├─ 校验 C   │
    │                 │            │
    └─ 提交 A+B ──────┴─ 提交 C   │
```

- **并发上限**：最多 1 个后台代理（两个并发会因平台限制失败）
- **代理 prompt**：指向 `prompts/unit-task.md` 任务书 + 指定单元 + sources 白名单 + 常见坑提醒
- **质量保证**：代理产出与主线程产出使用完全相同的 schema 与校验标准
- **代理失败处理**：两次无产出 → 停掉代理，主线程直接写（记 BLOCKERS.md）

### 校验循环

```
写 JSON → python check.py --file xxx.json → 按报错修复 → 直到 errors=0
```

常见报错及修复（预判）：
| 报错 | 原因 | 修复 |
|---|---|---|
| JSON 解析失败 | 字符串内有未转义 ASCII 引号 | `fix_quotes.py` |
| SVG XML 解析失败 | `'/<text` 漏了 `>` | 替换 `'/<` → `'/><` |
| SVG mismatched tag | `</g>` 多写或漏写 | 标签栈修复器 |
| 年份乱序 | JSON 数组未按 year 排列 | 脚本 sort |
| year_display 不一致 | "约前10世纪" ≠ 具体年 | 改写为"约前980年（前10世纪末）" |
| 来源 id 未定义 | sources.json 中无此 id | 添加来源或改用已有 id |
| 升级目标不存在 | upgrade 引用了未创建的 id | 先创建人物条目再升级 |

---

## 第七步：生成站点与校验循环（半天）

1. `python tools/check.py` → 直到 0 errors
2. `python tools/gen_site.py` → 生成 site/
3. `python tools/check_links.py` → 站内链接完整性核验，直到 0 断链（能抓出 depth 层级错配这类肉眼难发现的存量 bug）
4. 抽查页面（HTML 结构、SVG 渲染、链接完整性）
5. `git commit`（每单元一个 commit，可审计）

---

## 第八步：发布（半天）

1. GitHub 仓库：`git remote add origin https://github.com/xxx/yyy.git && git push -u origin main`
2. Pages 工作流（`.github/workflows/deploy-pages.yml`）：
   ```yaml
   name: Deploy Pages
   on:
     push:
       branches: [main]
     workflow_dispatch:
   permissions:
     contents: read
     pages: write
     id-token: write
   jobs:
     deploy:
       runs-on: ubuntu-latest
       environment:
         name: github-pages
         url: ${{ steps.deployment.outputs.page_url }}
       steps:
         - uses: actions/checkout@v4
         - uses: actions/configure-pages@v5
           with:
             enablement: true    # 自动启用 Pages
         - uses: actions/upload-pages-artifact@v3
           with:
             path: site          # 部署物来源目录
         - id: deployment
           uses: actions/deploy-pages@v4
   ```
3. README 可视化：截图（浏览器实拍）+ 统计图（从数据生成 SVG）
4. 如需启用 Pages API：`POST /repos/{owner}/{repo}/pages` + `{"build_type": "workflow"}`

---

## 第九步：持续丰富循环（可重复 N 轮）

```
第一轮：主事件 + 主人物（核心骨架）
第二轮：延伸事件 + 其他人物（密度提升）
第三轮：专题论述（经济社会/技术/宗教/艺术/生活维度）
第四波：补盲（审计工具检查缺失的文明/地区/主题）
第五波：术语表 + 比较视野（概念与跨领域分析）
人物升级：为其他人物补年谱 + 评价分歧（深度提升）
术语扩充：持续补充新术语
比较视野扩充：持续新增跨领域比较
```

每轮重复：写 JSON → check.py 校验 → gen_site.py 生成 → git commit → push

---

## 踩坑清单（从本项目实战提炼，提前预防）

| # | 坑 | 预防 |
|---|---|---|
| 1 | JSON 字符串内 ASCII 引号未转义 → JSON 解析失败 | 字符串内一律用中文引号""；`fix_quotes.py` 可修复 |
| 2 | SVG 自闭合标签漏 `>`（`'/<text` 应为 `'/><text`） | gen_site 内置 `sanitize_svg()` 自动修复 |
| 3 | SVG `y='0 width=` 缺引号 | 同上，`y='0 width='760'` 替换 |
| 4 | SVG `</g>` 多写/漏写 → mismatched tag | 标签栈修复器（gen_site 内置） |
| 5 | 事件未按 year 升序 | 写完后脚本统一 sort |
| 6 | gen_site 单元加载误扫 data/enrich/ 等子目录 → KeyError | 排除列表：enrich/enrich2/themes/glossary/comparative |
| 7 | 人物 chronology 漏 `{}` 或 `}` | 手写时注意，check 会报 JSON 解析错 |
| 8 | year_display "约前10世纪" ≠ year(-980) | display 首个数字必须等于 \|year\| |
| 9 | heredoc 内含 `\\` 时 bash 吞反斜杠 | 改用 Write 写脚本文件再执行 |
| 10 | agent 并发 >1 失败 | 严格串行，最多 1 个后台代理 |
| 11 | Python 在 Windows 输出中文乱码 | `PYTHONIOENCODING=utf-8 python -X utf8` |
| 12 | git push 偶发断连 | 重试即可（网络波动，非权限问题） |
| 13 | curl/gh 不可用（网络限制） | 用 Python urllib + ssl 跳过证书验证 |
| 14 | 来源 id 拼写错误 | check 会报错"未在 sources.json 中定义" |
| 15 | 术语/专题 unit_id 指向不存在的单元 | check 会报错"无对应单元" |
| 16 | 事件/人物页与单元页目录深度不同，depth 写错则导航/面包屑全站错位（线上 404） | 单元页两层深 depth=2，events/、people/ 一层深 depth=1；用 check_links.py 全量核验 |
| 17 | id 里混入拼音撇号（di'erci）、ü、大写 → 截断 href 属性/产生非 ASCII 文件名 | R16 强制 `a-z0-9-`；ü 一律写 v（lvshi、nvwang） |

---

## 换域适配清单

把本项目复刻到新知识域时，需要替换的内容：

| 要替换 | 示例（地理） | 示例（哲学） |
|---|---|---|
| scope.md 单元划分 | 按大洲/气候带/地形 | 按时代/流派/地域 |
| 事件→ "地理发现/地质事件/探险" | 喜马拉雅形成、大陆漂移 | 康德《纯粹理性批判》、维也纳学派 |
| 人物→ "地理学家/探险家/地质学家" | 麦哲伦、洪堡、竺可桢 | 苏格拉底、康德、维特根斯坦 |
| 主题→ "气候/地形/海洋/生态" | 大陆漂移、板块构造 | 认识论、本体论、伦理学 |
| 术语→ "板块构造、等高线、季风" | 先验、辩证法、现象学还原 | |
| SVG 内容 | 地形示意图、气候带分布 | 论证结构图、流派谱系图 |
| 时间线 | 地质年代/探险史 | 哲学史年代 |
| 对照表 | 同期不同地区的地理发现 | 同期不同流派的哲学著作 |
| 比较视野 | "东西方地理发现比较" | "中西方认识论比较" |

不需要替换的（架构级复用）：
- check.py 的校验逻辑（改正则匹配即可适配新域）
- gen_site.py 的渲染逻辑（页面类型和导航不变）
- CSS 样式（改配色即可）
- Sources.json 的四分类结构（换内容即可）
- enrich/enrich2/themes/glossary/comparative 的 schema（字段不变）
- GitHub Pages 工作流
- 双源规则、待核实标注、争议并列的诚实标注体系

---

## 总结：最小可行流程（MVP 一天完成）

```
1. scope.md（列出单元+条目清单）                    → 半天
2. sources.json（收集来源）                         → 半天
3. check.py（复制本项目改校验规则）                   → 1天
4. gen_site.py（复制本项目改页面模板）               → 1天
5. 写 3-5 个单元的 JSON（主事件+人物）              → 1天
6. check → gen → 抽查 → commit                    → 半天
7. 逐单元补完（每单元：写JSON→校验→commit）          → N天
8. 延伸层+专题+术语+比较视野（按需逐层添加）           → 按需
9. GitHub Pages 发布                               → 半天
```

**核心思想：数据驱动、机器校验、诚实标注、逐层丰富。**
