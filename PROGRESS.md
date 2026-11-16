# PROGRESS — 中外历史脉络库

- [x] 0. 项目骨架（git、PROGRESS/DECISIONS/BLOCKERS）
- [x] 1. scope.md 入选清单（18 单元：中国13 + 世界5）
- [x] 2. 阶段1：sources.json 156 条 + 三态链接核验（68可达/61反爬拦截/19离线/0真死链）
- [x] 3. 阶段2：tools/check.py（R1–R10 规则，冒烟测试通过）+ tools/gen_site.py + assets/style.css
- [ ] 4. 阶段3：样板（秦 + 世界·古代文明）通过检查
- [ ] 5. 阶段4：中国其余 12 单元
- [ ] 6. 阶段4：世界其余 4 时期
- [ ] 7. 阶段5：时间线 / 对照表 / 导航 / REPORT.md
- [ ] 8. ALL_DONE

## 日志
- 2026-11-17 开始。目录为空，全新构建。Python 3.11.7 可用。
- 2026-11-17 sources.json 实测 156 条；linkcheck 三态（true/blocked/false）写入 DECISIONS.md 第12条。
- 2026-11-17 样板阶段：并发限制，改为串行执行编写代理；通用任务书 prompts/unit-task.md。
