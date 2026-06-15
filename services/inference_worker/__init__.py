"""Inference Worker service — the data plane.

Loads models, executes batched forward passes on the configured runtime backend
(stub / torch / onnx), and publishes results. Scales horizontally on GPU nodes.
"""
