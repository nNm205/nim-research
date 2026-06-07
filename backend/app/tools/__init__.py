"""Lower-level adapters and utilities shared across the service layer.

This package holds I/O-heavy primitives that aren't tied to any single
agent or service:

    tools/document  — fetchers, parsers, chunkers, embedders, vector store
    tools/search    — search adapters (arXiv / Scholar / S2 / web), ranking,
                      deduplication, publisher classification

These are deliberately placed OUTSIDE ``app/agents/`` because they are
shared infrastructure: ``DocumentIngestionService`` and ``SearchService``
(both in the service layer) consume them, alongside the agents themselves.
Moving them under ``app/agents/tools/`` would force the service layer to
import from the agent layer — an inversion we want to avoid.

Agent-specific tool primitives (``ProgressTracker``, the section-mapper
used only by ``AnalysisAgent``, etc.) live under ``app/agents/tools/<agent>/``
instead.
"""
