"""Text-only report generation and idempotent terminal finalization."""

from .builder import ReportBuilder, ReportFinalizationError, ReportFinalizer, ReportInput

__all__ = ["ReportBuilder", "ReportFinalizationError", "ReportFinalizer", "ReportInput"]

