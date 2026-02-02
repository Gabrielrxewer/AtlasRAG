"""Rotas da camada de apresentação."""
from . import connections, scans, tables, api_routes, rag, agents

# Exporta módulos de rotas para registro no app.
__all__ = ["connections", "scans", "tables", "api_routes", "rag", "agents"]
