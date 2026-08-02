"""Public Role Contract Normalizer API."""

from rolecheck.normalization.models import (
    DependencySpecDraft,
    DetectedLanguage,
    FieldNormalization,
    InputSpecDraft,
    NormalizationResult,
    NormalizationSource,
    OutputSpecDraft,
    RoleContractDraft,
    SourceKind,
    SourceSpan,
    promote_draft,
)
from rolecheck.normalization.normalizer import RoleContractNormalizer
from rolecheck.normalization.rules import NORMALIZER_VERSION

__all__ = [
    "NORMALIZER_VERSION",
    "DependencySpecDraft",
    "DetectedLanguage",
    "FieldNormalization",
    "InputSpecDraft",
    "NormalizationResult",
    "NormalizationSource",
    "OutputSpecDraft",
    "RoleContractDraft",
    "RoleContractNormalizer",
    "SourceKind",
    "SourceSpan",
    "promote_draft",
]
