"""Synthetic and pinned empirical Benchmark Adapter boundaries."""

from rolecheck.benchmark.adapter import BenchmarkAdapter, SyntheticBenchmarkAdapter
from rolecheck.benchmark.mmlu_pro import (
    MMLU_PRO_DATASET_ID,
    MMLU_PRO_REVISION,
    MMLUProBenchmarkAdapter,
    MMLUProEvaluationRecord,
    MMLUProTaskRecord,
)
from rolecheck.benchmark.models import (
    BenchmarkAdapterIdentity,
    OfflineTaskRecord,
    TaskConversionResult,
)
from rolecheck.benchmark.splits import (
    SplitWeights,
    TaskPartition,
    TaskSplitManifest,
    create_task_split_manifest,
)
from rolecheck.schemas import EvidenceClass

__all__ = [
    "MMLU_PRO_DATASET_ID",
    "MMLU_PRO_REVISION",
    "BenchmarkAdapter",
    "BenchmarkAdapterIdentity",
    "EvidenceClass",
    "MMLUProBenchmarkAdapter",
    "MMLUProEvaluationRecord",
    "MMLUProTaskRecord",
    "OfflineTaskRecord",
    "SplitWeights",
    "SyntheticBenchmarkAdapter",
    "TaskConversionResult",
    "TaskPartition",
    "TaskSplitManifest",
    "create_task_split_manifest",
]
