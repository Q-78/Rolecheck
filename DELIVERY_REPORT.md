# RoleCheck 当前阶段交付报告

**交付日期：** 2026-08-02  
**阶段：** 研究冻结与基础仓库初始化  
**正式实验状态：** 尚未开始

## 1. 已完成内容

### 研究冻结

- 生成 `research_docs/RESEARCH_SPEC_v0.2.md`，将十项决策从“待冻结”改为第一版硬约束；
- 生成 `research_docs/DECISION_LOG.md`，记录 10 项研究决策和 1 项仓库阶段决策；
- 生成 `research_docs/RISK_REGISTER.md`，覆盖科学有效性、协议、泄漏、复现、过度治疗和可插拔性风险；
- 生成 `research_docs/INTERVENTION_PROTOCOL.md`，冻结：
  - parallel aggregation removal；
  - schema-preserving bypass；
  - non-removable roles；
  - seed 层级、配对重放和多 seed 标签规则；
- 生成 `research_docs/CLAIM_EVIDENCE_MAP.md`，将 L0–L4 主张映射到实验、指标、基线和 Go/No-Go；
- 保留原交接文档与七份研究规范，便于追溯。

### 基础仓库

- 创建 Python 3.11 `src` 布局和 `pyproject.toml`；
- 创建基础配置 `configs/base.yaml`；
- 创建 GitHub Actions 质量检查工作流；
- 创建 README、`.gitignore` 和空运行目录占位文件。

### Pydantic Schema

已实现并可生成 JSON Schema：

1. `TaskSpec`
2. `RoleContract`
3. `AgentInstance`
4. `CanonicalTeamConfig`
5. `ExecutionProtocol`
6. `RemovalProtocol`
7. `ExecutionRecord`
8. `InterventionRecord`
9. `KeepValueRecord`
10. `RepairCandidate`
11. `RepairValueRecord`
12. `RoleAuditReport`

同时实现必要的嵌套对象和枚举，例如 Input/Output/Dependency、CommunicationEdge、BypassRule、SeedBundle、三类执行前信息设置与动作类型。

关键硬约束已进入 Schema 校验：

- Strict/Probe 信息设置显式记录；
- 当前任务输出、Gold 和当前任务反事实结果的泄漏标记只能为 `false`；
- REWRITE 不能修改模型、工具、拓扑或协议字段；
- 每角色最多三个修复候选；
- ABSTAIN 必须对外输出 KEEP；
- joint intervention 必须 KEEP；
- REMOVE 必须 `removal_safe=true` 且无 Coverage Gap；
- parallel removal 必须固定其他响应并使用同一协议重新聚合；
- DAG bypass 必须预注册旁路规则且禁止语义补偿。

### 工程基础设施

- `config.py`：YAML 加载、Pydantic 校验、有限环境变量覆盖、稳定配置哈希；
- `logging_utils.py`：标准日志与 JSON-lines 日志；
- `manifest.py`：完整实验 Manifest 和默认禁止覆盖；
- `hashing.py`：稳定内容哈希与层级 seed 派生；
- `runtime/mock.py`：确定性 Mock Runtime，不调用模型，`utility=None`，所有记录标记 `mock=true`。

## 2. 本地验证结果

| 检查 | 结果 |
|---|---|
| 配置 smoke test | PASS |
| 12 个必需模型 JSON Schema 生成 | PASS |
| Python `compileall` | PASS |
| `pytest` | PASS：11 tests |
| Editable package build/install | PASS |
| 超过 100 字符的 Python 行检查 | PASS：0 |
| `ruff` | 未在当前沙箱执行；工具不可用且包索引/外网安装失败 |
| `mypy` | 未在当前沙箱执行；工具不可用且包索引/外网安装失败 |

`ruff` 和 `mypy` 已写入开发依赖、配置和 `.github/workflows/quality.yml`。在可访问 Python 包源的 Python 3.11 环境执行：

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest
```

在这两个检查真正通过前，不应进入正式实验实现。

## 3. 明确未实现内容

本次交付没有实现：

- 真实模型或 API 调用；
- Benchmark 下载与正式数据集；
- 缺陷注入；
- Static Defect Auditor；
- Keep-Value Predictor；
- Repair Candidate Generator；
- Repair-Value Predictor；
- AgentInit 或其他初始化器 Adapter；
- 两个正式受控执行协议的运行逻辑；
- 旧项目实验代码迁移。

这些缺失是当前阶段的设计要求，不是遗漏。

## 4. 尚未解决的问题

1. 需要在标准 Python 3.11 环境或 CI 中实际运行 `ruff` 与 `mypy`；
2. 具体 Benchmark、任务族、效用函数实例化和样本量仍未冻结；
3. Role Contract Normalizer 的确定性解析规则尚未设计；
4. 并行 removal 与 DAG bypass 目前只有规范和 Schema，尚无正式执行器；
5. 解析置信、OOD 风险和模型不确定性的具体估计方法尚未选择。

## 5. 下一阶段建议

下一阶段只做两项：

1. 实现并测试两个受控执行协议：
   - Parallel Aggregation Removal；
   - Schema-Preserving Bypass。
2. 实现 Role Contract Normalizer：
   - 先确定性解析；
   - 再保留可选结构化模型抽取接口；
   - provenance、missing fields 和 parse confidence 必须全程保留。

在此之前，不实现预测器，不开始大规模实验。
