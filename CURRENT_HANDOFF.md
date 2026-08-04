# RoleCheck 当前工作交接

**交接日期：** 2026-08-04
**适用对象：** 接手当前仓库开发、GitHub 审查和服务器实验的新 Codex 对话
**Current gate:** Pilot v0.3 Gate 6 completed and independently artifact-verified; repository review and publication are pending. The Gate 6 result document is authoritative; older gate-status text below is historical context.

## 1. 新对话首先做什么

新对话必须依次完整阅读：

1. `AGENTS.md`；
2. 本文件；
3. `research_docs/RESEARCH_SPEC_v0.2.md`；
4. `research_docs/DECISION_LOG.md`；
5. `research_docs/INTERVENTION_PROTOCOL.md`；
6. `research_docs/CLAIM_EVIDENCE_MAP.md`；
7. `research_docs/RISK_REGISTER.md`；
8. `research_docs/SERVER_PILOT_PLAN_v0.1.md`；
9. `research_docs/PILOT_EXECUTION_FREEZE_v0.1.md`；
10. `README.md`。

研究决策的优先级仍由 `AGENTS.md` 规定。本文件只记录操作状态，不得覆盖冻结研究决策。

## 2. 当前 Git 和 GitHub 状态

- 仓库：`Q-78/Rolecheck`；
- merged `main` checkpoint: `9737f2efbff0e0cd314db24835c7e40094c35536`;
- current handoff branch: `codex/current-handoff`;
- superseded snapshot: `origin/codex/gate-2b-execution-freeze` contains post-merge handoff commit `82426ee`; use PR #8 as the canonical handoff instead;
- Gate 2-B implementation commit: `f4790df59924609630926a623e9c8fc7a93cb00c`;
- Gate 2-B PR: [#7 Freeze Gate 2-B pilot execution](https://github.com/Q-78/Rolecheck/pull/7);
- PR #7 state: MERGED; merge commit `9737f2efbff0e0cd314db24835c7e40094c35536`;
- current handoff PR: [#8 Add current RoleCheck handoff](https://github.com/Q-78/Rolecheck/pull/8), OPEN and DRAFT at handoff time;
- PR #7 GitHub Actions: Python 3.11, 3.12, and 3.13 all passed.

Gate 2-B is complete. `AGENTS.md` intentionally retains the Gate 3 hard stop until a separate transition is reviewed and explicitly approved.

## 3. 整个实验目前的位置

已经完成：

- 冻结研究规范、干预协议、证据主张和风险边界；
- RoleContract 和严格 Schema 基础；
- Role Contract Normalizer v0.1；
- 受控并行单角色移除和 DAG bypass 的模型无关协议；
- Stage 3 本地脚手架及运行边界；
- Gate 0：服务器 Pilot 计划；
- Gate 1：经验数据边界、MMLU-Pro 适配接口和 Runtime Adapter 边界，已通过 PR #6 合并；
- Gate 2-A：服务器环境、模型文件和硬件身份审计，证据保存在 Git 外；
- Gate 2-B: the three-role execution freeze was reviewed and merged through PR #7.

尚未完成：

- merge of this current handoff update;
- Gate 3：固定版本 MMLU-Pro 数据物化、子集 Manifest 和泄漏审计；
- Gate 4：首次模型加载和一题一角色 smoke test；
- Gate 5：14 题 dry run；
- Gate 6：56 题受控 Pilot；
- 任何预测器、修复器或正式研究评估。

The project is now between Gate 2-B and Gate 3. There are still no empirical results; Fake-engine test output is not research evidence.

## 4. Gate 2-B 已实现内容

PR #7 新增 `src/rolecheck/pilot`，冻结：

- `domain_analyst`、`elimination_analyst`、`verification_analyst` 三个独立角色；
- 三个准确 raw Prompts、显式 Normalizer 输入和 Role Contracts；
- 同一固定 Qwen3-8B revision、无工具、无网络、一轮独立执行；
- `parallel_independent` 协议和受控 parallel aggregation removal 协议；
- Qwen thinking 文本分离和严格终止行 `Answer: <LETTER>` 解析；
- 不调用模型的确定性多数投票及字典序平票规则；
- 独立 system/user 消息渲染和消息哈希；
- 依赖注入的 `LocalGenerationEngine` 接口；
- generation engine、parser、aggregator、backend 和 runtime 身份；
- raw token IDs、raw decoded output、解析结果、seed、hash、token count 和 latency 的证据保留。

本次没有修改核心 `RoleContract`、Benchmark Schema、既有 Runtime Schema 或依赖，没有实现 Transformers backend。

## 5. Gate 2-B 自主审计结论

审计中已发现并修复：

- 可公开访问的生成配置原本可变，现为只读映射；
- Prompt 原本没有显式冻结 system/user 消息边界，现使用严格消息模型和消息哈希；
- parser 行为原本没有独立身份，现绑定 parser config hash；
- aggregator 原本未核对 TaskSpec 的选项数与解析证据，现不一致即拒绝；
- aggregator 身份漂移原本直到角色生成后才拒绝，现任何生成前即拒绝，并在聚合调用前后再次核对；
- engine、backend、runtime 和文档中的派生哈希已重新计算并由测试冻结。

最终本地验证结果：

```text
ruff check .                         PASS
mypy src                            PASS (32 source files)
pytest                              PASS (150 tests)
python -m compileall src tests      PASS
```

交接提交必须重新运行相同四项检查；测试数量可能因纯文档提交保持为 150。

## 6. 冻结身份

关键代码身份如下，完整表见 `research_docs/PILOT_EXECUTION_FREEZE_v0.1.md`：

- team：`sha256:3c768707410ed19e2a06eaee70b9116e0ef1a01380c5cf361166b38b7acaadac`；
- aggregator：`sha256:fe61484ff35764e87e5bf3bf2a4ca9881eac5d2ef274278284de1b5a6a11e31e`；
- parser：`sha256:782c7636a1dbcaec4ac0d56dfe974dea5c6342eeee99c5308a6015dc1f97cd9f`；
- required generation engine：`sha256:17f02120c9861c4e0bd34a5ef9396359eabdc389312effa38ca1202182f1f7a3`；
- backend：`sha256:62beeb34048c7b6f29402449212c9831246ff047ec0adf67b0cdf3f4fcdfff1e`；
- self-hosted runtime：`sha256:3359697ecd6b32fe3f869cca2b4c1fc1cd712b34ec59a60d3d869297bcf9cf43`；
- runtime environment：`sha256:75bd5f65b1c3acca4d364e2a67041db2aa57db5b3e0eedea42c2890d104ffc55`。

## 7. 已冻结的服务器环境

服务器已审计状态：

- 4 × NVIDIA A100-SXM4-40GB；Pilot 只允许使用 GPU 0；
- NVIDIA driver：550.90.12；
- PyTorch：2.6.0+cu124；
- PyTorch CUDA runtime：12.4；
- Python：3.11.15；
- Transformers：4.51.3；
- Datasets：3.6.0；
- Accelerate：1.6.0；
- Safetensors：0.5.3；
- Conda 环境：`rolecheck-pilot-v01`；
- Gate 2-A 审计时 `/data/qhy` 可用空间约 1295 GB。

服务器代码和证据位置：

- Gate 2-A 代码目录：`/home/qhy/projects/RoleCheck-gate2`；
- 服务器数据根：`/data/qhy/rolecheck_server`；
- artifact 根：`/data/qhy/rolecheck_server/artifacts/pilot-v0.1`；
- Gate 2-A artifact：`/data/qhy/rolecheck_server/artifacts/pilot-v0.1/gate-2`；
- dataset 目录：`/data/qhy/rolecheck_server/datasets`；
- Hugging Face cache：`/data/qhy/rolecheck_server/cache/huggingface`；
- 模型实际 cache 根：`/data/qhy/huggingface/hub`。

模型：

- ID：`Qwen/Qwen3-8B`；
- revision：`b968826d9c46dd6066d109eabc6255188de91218`；
- snapshot：`/data/qhy/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/b968826d9c46dd6066d109eabc6255188de91218`；
- model artifact manifest：`sha256:866aaf6607fe6c4bc59ac58d599710e97555710114c1925c99ed392d452862a1`；
- tokenizer：`sha256:aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492daa4`；
- generation config file：`sha256:2325da0f15bb848e018c5ae071b7943332e9f871d6b60e2ed22ca97d4cb993d2`；
- dependency lock：`sha256:9e8ce3b71f339a891420046befbdaf3ab8c370a06a37e28e578dcba125bddf6c`；
- hardware inventory：`sha256:89d3a5849c7f6c6dcfd1802e95ee2ebbd77ff804ca9ed0c873346c7d1363b9f4`。

不要安装系统级 CUDA toolkit。`nvcc` 不存在不是阻断项；当前 PyTorch wheel 已提供所需 CUDA runtime，`nvidia-smi` 和 `torch.cuda.is_available()` 已通过。

## 8. 下一位执行者的准确任务

### 8.1 Close out the handoff before Gate 3

1. Verify that PR #7 is merged at `9737f2efbff0e0cd314db24835c7e40094c35536`.
2. Review and merge the documentation-only PR #8.
3. Fast-forward local and server checkouts to the resulting `main` revision and record it.
4. Confirm the Gate 2-A artifacts and model hashes still verify without loading the model.
5. Obtain explicit approval for Gate 3 and update the active-phase guard separately.
6. Keep Gate 3 work in a new branch and PR; do not append it to the handoff change.

### 8.2 Gate 3 只能在合并和明确批准后开始

固定数据集：

- ID：`TIGER-Lab/MMLU-Pro`；
- revision：`b189ec765aa7ed75c8acfea42df31fdae71f97be`；
- dataset card license：MIT；
- 预期 domain 数：14；
- subset split seed：`2026080301`；
- experiment seed：`2026080302`。

Gate 3 最小工作：

1. 从已合并 `main` 创建独立分支；
2. 在服务器再次解析并记录固定 dataset revision；
3. 只将该 revision 物化到隔离的 Git 外 dataset 目录；
4. 记录文件 hash、row count、schema、split names 和 license；
5. 不查看答案内容地构建 14 题和 56 题 Manifest，56 题包含前述 14 题；
6. 保存准确 task IDs 和 canonical subset hashes；
7. 运行 gold leakage audit，保证 gold answer/reference rationale 不进入 `TaskSpec`、Prompt、Normalizer、aggregator 或任何 pre-execution 输入；
8. 封存 Gate 3 artifacts 后停止，先审查 Manifest；
9. 不加载 Qwen3-8B，不生成任何角色输出。

任一 domain 有效记录不足必须 hard abort，不得静默重分配。

## 9. Gate 3 仍然禁止的事情

- 不加载 Transformers 模型或调用真实 API；
- 不运行一题 smoke test；
- 不生成 role output；
- 不做 baseline、removal 或 replay execution；
- 不读取 gold answer 来挑选任务；
- 不训练或拟合 keep-value/repair-value predictor；
- 不实现 defect injection、repairer、AutoGen 或 AgentInit；
- 不把 dataset、模型、cache、secrets 或 runtime artifacts 提交到 Git；
- 不改模型、工具、拓扑、协议、轮数、聚合或停止规则。

首次模型加载属于 Gate 4，必须等待 Gate 3 的 Manifest 和泄漏审计独立通过。

## 10. 新对话可直接使用的首条指令

```text
请先只读，不要修改、提交或运行服务器实验。

请遵守根目录 AGENTS.md，并完整阅读 CURRENT_HANDOFF.md 及其第 1 节列出的研究文档。然后：

1. Verify that GitHub PR #7 is merged at `9737f2efbff0e0cd314db24835c7e40094c35536`;
2. inspect the documentation-only PR #8 and the current `main`;
3. rerun the four required local checks;
4. report whether the handoff PR can be merged;
5. do not enter Gate 3, download MMLU-Pro, or load Qwen3-8B without my explicit confirmation.

必须主动寻找阻断性设计问题，不要只总结成果。
```

## 11. 新对话的快速核对命令

```bash
git status --short --branch
git log -3 --oneline --decorate
git diff origin/main...HEAD --stat
git diff --check origin/main...HEAD
ruff check .
mypy src
pytest
python -m compileall src tests
```

GitHub 状态：

```bash
gh pr view 7 --repo Q-78/Rolecheck \
  --json number,title,state,isDraft,mergeStateStatus,statusCheckRollup,url
gh pr view 8 --repo Q-78/Rolecheck --json number,title,state,isDraft,mergeStateStatus,statusCheckRollup,url
```

## 12. 交接完成标准

新对话只有在以下事实都被重新确认后，才能接管执行：

- 知道核心研究任务是 protocol-conditioned keep-value prediction，而不是通用 Prompt 优化；
- knows that PR #7 is merged but the handoff update must also reach `main`;
- 知道测试输出不是经验数据；
- 知道 Gate 3 只做数据物化、Manifest 和泄漏审计；
- 知道 Gate 4 才允许第一次模型加载；
- 知道所有服务器 dataset、模型、cache 和 artifact 必须留在 Git 外；
- 知道任何新的阶段都要独立审计、独立提交和独立合并。
