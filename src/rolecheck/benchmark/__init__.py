"""Offline Benchmark Adapter boundary for Stage 3 local work."""

from rolecheck.benchmark.adapter import BenchmarkAdapter, SyntheticBenchmarkAdapter
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

__all__ = [
    "BenchmarkAdapter",
    "BenchmarkAdapterIdentity",
    "OfflineTaskRecord",
    "SplitWeights",
    "SyntheticBenchmarkAdapter",
    "TaskConversionResult",
    "TaskPartition",
    "TaskSplitManifest",
    "create_task_split_manifest",
]
