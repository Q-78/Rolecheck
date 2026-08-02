# RoleCheck 主张—证据映射

**版本：** v0.1  
**日期：** 2026-08-02  
**原则：** 没有对应证据的主张不得进入摘要、结论或项目主页。

## 1. 主张层级

| 层级 | 主张 | 所需证据 | 最低实验/分析 | 关键指标 | Gate | 当前状态 |
|---|---|---|---|---|---|---|
| L0-C1 | 提出初始化后、当前任务执行前的角色审计问题 | 清晰定义、边界、与相关工作的区别 | 规范与相关工作矩阵 | 定义一致性；非主张清单 | 无 | READY-DESIGN |
| L0-C2 | 定义协议条件的操作性 Keep Value | 可执行、可复现的移除协议 | 并行 removal 与 DAG bypass 单元/集成验证 | 重放一致性；协议有效率 | Gate 1 前置 | SPECIFIED |
| L0-C3 | 定义具体候选绑定的 Repair Value | 候选版本、替换协议和差值定义 | 候选 Schema 与替换记录验证 | 候选合法率；可追溯率 | Gate 1 前置 | SPECIFIED |
| L0-C4 | Role Contract 可作为统一中间表示 | 多来源字段可映射且保留 provenance | 至少两个初始化来源的适配案例 | 字段覆盖率；解析置信；信息损失 | 系统验证 | NOT STARTED |
| L1-C1 | 初始化角色存在可观察缺陷 | 人工/规则/模型标注一致性与自然样本分析 | 缺陷分布、案例审查 | prevalence；macro/micro F1；一致性 | Gate 1 | NOT STARTED |
| L1-C2 | 缺陷与 Keep Value 不等价 | 同缺陷不同价值、无缺陷负价值等反例统计 | 缺陷—价值交叉分析 | 条件分布；互信息；反例率 | Gate 1 | NOT STARTED |
| L1-C3 | 角色价值具有任务、团队、协议条件性 | 同角色跨任务/团队/协议的价值变化 | 配对反事实实验 | 方差分解；符号翻转率 | Gate 1 | NOT STARTED |
| L2-C1 | Strict 模式下 Keep Value 存在可预测信号 | 未见任务/团队测试表现优于基线 | Keep predictor benchmark | MAE/Spearman/AUROC/PR-AUC；校准仅在验证后使用该词 | Gate 2 | NOT STARTED |
| L2-C2 | 团队条件特征优于个体能力/角色语义基线 | 严格消融和统计检验 | individual-only vs team-conditioned | Δmetric；置信区间；多 seed | Gate 2 | NOT STARTED |
| L2-C3 | 能识别有害角色 | 负 Keep Value 样本上的风险评估 | harmful-role classification | PR-AUC；precision@coverage；false removal risk | Gate 2 | NOT STARTED |
| L2-C4 | Probe-assisted 在不泄漏当前任务的前提下增益 | 独立校准集与严格血缘 | Strict vs Probe | 增益、成本、覆盖；泄漏审计 | Gate 2 | NOT STARTED |
| L2-C5 | OOD/合同风险可被识别 | 未见任务/初始化器与解析扰动 | OOD 与 contract corruption tests | AUROC；risk-coverage；abstention utility | Gate 2 | NOT STARTED |
| L3-C1 | 保守策略减少健康角色误改 | 与无 abstention/规则策略比较 | policy simulation + real reruns | healthy-role intervention rate；harm rate | Gate 2/3 | NOT STARTED |
| L3-C2 | 有限修复候选价值可排序 | 未见任务/团队的候选真实反事实结果 | candidate ranking benchmark | NDCG/MRR/top-1 regret/Spearman | Gate 3 | NOT STARTED |
| L3-C3 | 价值排序优于缺陷规则和生成器原始排序 | 多基线对照 | rule/edit-distance/generator-rank comparisons | top-1 success；regret；净收益 | Gate 3 | NOT STARTED |
| L3-C4 | 选择性 REWRITE 优于普遍重写 | 同一候选生成器下策略比较 | selective vs rewrite-all | task gain；harm rate；cost | Gate 3 | NOT STARTED |
| L3-C5 | REMOVE 只在安全旁路下产生可解释收益 | removal-valid subset 分析 | protocol-stratified removal | valid removal rate；coverage gap；harm rate | Gate 3 | NOT STARTED |
| L4-C1 | RoleCheck 改善性能—成本前沿 | 完整计入审计、Probe、候选生成、重跑成本 | end-to-end evaluation | Pareto frontier；net utility；latency | 系统 Gate | NOT STARTED |
| L4-C2 | 核心逻辑可跨初始化器复用 | 至少两个代表性初始化器，核心模型/规则基本不变 | cross-initializer transfer | zero/few-shot transfer；adapter LOC；retraining need | 系统 Gate | NOT STARTED |
| L4-C3 | 设计为 plug-and-play 的审计层 | 清晰接口与有限 Adapter 工作量 | integration study | integration changes；schema coverage；runtime compatibility | 系统 Gate | NOT STARTED |

## 2. 关键基线映射

### Keep Value

- 常数/训练均值；
- role-name 或文本嵌入；
- 个体能力画像；
- 静态缺陷规则；
- team-agnostic predictor；
- protocol-agnostic predictor；
- oracle removal（只作上界/标签，不作执行前方法）。

### Repair Value

- 随机候选；
- 生成器原始顺序；
- 缺陷匹配规则；
- 最小编辑距离；
- 最大合同完整度提升；
- oracle candidate value（上界）。

### Policy

- KEEP-all；
- REMOVE-if-defect；
- REWRITE-all-suspicious；
- point-estimate without uncertainty；
- conservative RoleCheck；
- oracle action（上界）。

## 3. 主张升级规则

1. `READY-DESIGN` 只允许使用 “formulate / define / design / intended”；
2. Gate 1 通过后可报告描述性分布，但不能说“可预测”；
3. Gate 2 通过后才可主张 Keep Value 的预测性；
4. Gate 3 通过后才可主张 repair ranking 与自动最小修复；
5. 跨初始化器和完整成本实验完成前，不得使用 “universally plug-and-play” 或“改善净收益”；
6. 任一主张必须同时链接到实验 ID、代码 commit、数据 revision、指标文件和错误分析。

## 4. Go / No-Go 证据包

### Gate 1：Benchmark 有效性

必须包含：

- 正/零/负 Keep Value 分布；
- 各缺陷类型和自然样本覆盖；
- 多 seed 稳定性；
- 移除协议有效率；
- Coverage Gap 与不可移除比例；
- 标签噪声和聚合器敏感性。

### Gate 2：Keep Value 可预测性

必须包含：

- 未见任务/团队划分；
- 严格泄漏审计；
- 简单基线与团队条件消融；
- 连续值、符号和风险—覆盖指标；
- 高置信错误分析；
- Strict 与 Probe 分开报告。

### Gate 3：Repair Value 可预测性

必须包含：

- 每候选真实反事实收益；
- 候选多样性与合法率；
- 排序基线；
- 修复后下降率；
- 健康角色误改率；
- 计入候选生成和执行成本的净结果。
