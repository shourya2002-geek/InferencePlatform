"""Scheduler service — queue management, dynamic batching, scheduling strategy.

Stateless control-plane service: it holds only an in-flight batching buffer and
can run as multiple replicas behind a Redis Stream consumer group.
"""
