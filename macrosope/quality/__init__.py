"""数据质量检查引擎。"""
from macrosope.quality.checks import (
    detect_frequency,
    run_frame_checks,
    run_metadata_checks,
)

__all__ = ["detect_frequency", "run_frame_checks", "run_metadata_checks"]
