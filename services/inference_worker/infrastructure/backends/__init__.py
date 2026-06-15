"""Concrete runtime backends + a factory to select one from config."""

from services.inference_worker.infrastructure.backends.factory import build_backend

__all__ = ["build_backend"]
