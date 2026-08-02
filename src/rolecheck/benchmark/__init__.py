"""Offline Benchmark Adapter boundary for Stage 3 local work."""

from rolecheck.benchmark.adapter import BenchmarkAdapter, SyntheticBenchmarkAdapter
from rolecheck.benchmark.models import (
    BenchmarkAdapterIdentity,
    OfflineTaskRecord,
    TaskConversionResult,
)

__all__ = [
    "BenchmarkAdapter",
    "BenchmarkAdapterIdentity",
    "OfflineTaskRecord",
    "SyntheticBenchmarkAdapter",
    "TaskConversionResult",
]
