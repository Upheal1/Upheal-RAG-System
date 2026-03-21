"""
Upheal microservices package.

This repo currently uses an in-process "wiring" approach (gateway orchestrates
domain service modules directly). Each domain keeps its own pure functions
and optional API router for health checks.
"""

