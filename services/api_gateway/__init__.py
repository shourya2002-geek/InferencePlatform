"""API Gateway service — the platform's front door.

Handles validation, authentication, rate limiting, request tracing and routing
onto the data plane. Stateless; scales horizontally on RPS.
"""
