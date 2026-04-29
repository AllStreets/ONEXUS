"""
Flux -- natural language to SQL query generator.
Converts plain-English questions into SQL queries given a database schema.

Inspired by:
  - defog-ai/sqlcoder (Apache 2.0) — open source text-to-SQL model
  - NumbersStation/NSText2SQL — text-to-SQL benchmarks
  - Spider benchmark (CC BY-SA 4.0) — text-to-SQL evaluation dataset
"""
import re
from dataclasses import dataclass
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class SQLResult:
    query: str
    explanation: str
    tables_used: list[str]
    estimated_complexity: str  # "simple", "moderate", "complex"


# SQL keyword patterns for complexity estimation
_COMPLEX_PATTERNS = ["JOIN", "SUBQUERY", "UNION", "HAVING", "WINDOW", "CTE", "WITH"]
_MODERATE_PATTERNS = ["GROUP BY", "ORDER BY", "DISTINCT", "COUNT", "SUM", "AVG"]


class FluxModule(NexusModule):
    name = "flux"
    description = "Natural language to SQL -- converts questions about data into SQL queries"
    version = "0.1.0"

    def __init__(self):
        self._schemas: dict[str, list[str]] = {}
        self._query_history: list[SQLResult] = []

    def register_schema(self, table: str, columns: list[str]) -> None:
        """Register a table schema for query generation."""
        self._schemas[table] = columns

    def list_schemas(self) -> dict[str, list[str]]:
        return dict(self._schemas)

    @staticmethod
    def parse_schema(text: str) -> dict[str, list[str]]:
        """Parse CREATE TABLE or schema descriptions from text."""
        schemas: dict[str, list[str]] = {}

        # Match CREATE TABLE statements
        creates = re.findall(
            r'CREATE\s+TABLE\s+(\w+)\s*\((.*?)\)',
            text, re.IGNORECASE | re.DOTALL
        )
        for table, body in creates:
            columns = []
            for line in body.split(','):
                col_match = re.match(r'\s*(\w+)\s+', line.strip())
                if col_match and col_match.group(1).upper() not in (
                    'PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'CONSTRAINT', 'INDEX'
                ):
                    columns.append(col_match.group(1))
            if columns:
                schemas[table] = columns

        # Match "table: col1, col2, col3" format
        if not schemas:
            table_lines = re.findall(r'^(\w+)\s*:\s*(.+)$', text, re.MULTILINE)
            for table, cols_str in table_lines:
                columns = [c.strip() for c in cols_str.split(',') if c.strip()]
                if columns:
                    schemas[table] = columns

        return schemas

    @staticmethod
    def estimate_complexity(query: str) -> str:
        """Estimate SQL query complexity."""
        query_upper = query.upper()
        if any(p in query_upper for p in _COMPLEX_PATTERNS):
            return "complex"
        if any(p in query_upper for p in _MODERATE_PATTERNS):
            return "moderate"
        return "simple"

    @staticmethod
    def extract_tables(query: str) -> list[str]:
        """Extract table names from a SQL query."""
        tables = re.findall(r'(?:FROM|JOIN)\s+(\w+)', query, re.IGNORECASE)
        return list(dict.fromkeys(tables))

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Check if message contains a schema definition
        new_schemas = self.parse_schema(message)
        if new_schemas:
            self._schemas.update(new_schemas)
            if not any(c in message.lower() for c in ("show", "query", "select", "find", "get", "list")):
                table_list = ", ".join(f"{t} ({len(c)} cols)" for t, c in new_schemas.items())
                return f"[Flux] Schema registered: {table_list}. Ask a question about your data."

        if not llm:
            return "[Flux] LLM required for SQL generation. Configure a local model or API provider."

        # Build schema context
        schema_text = ""
        if self._schemas:
            schema_parts = []
            for table, columns in self._schemas.items():
                schema_parts.append(f"  {table}({', '.join(columns)})")
            schema_text = "Available tables:\n" + "\n".join(schema_parts) + "\n\n"

        prompt = (
            "Generate a SQL query for the following question. "
            "Return the query and a brief explanation.\n\n"
            f"{schema_text}"
            f"Question: {message}\n\n"
            "Format your response as:\n"
            "SQL:\n<query>\n\n"
            "EXPLANATION:\n<explanation>"
        )

        try:
            response = await llm.complete(prompt)
        except Exception:
            return "[Flux] LLM call failed. Check your model configuration."

        # Parse response
        sql_match = re.search(r'SQL:\s*\n?(.*?)(?=EXPLANATION|$)', response, re.DOTALL | re.IGNORECASE)
        exp_match = re.search(r'EXPLANATION:\s*\n?(.*?)$', response, re.DOTALL | re.IGNORECASE)

        query = sql_match.group(1).strip().strip('`') if sql_match else response.strip()
        explanation = exp_match.group(1).strip() if exp_match else ""

        tables = self.extract_tables(query)
        complexity = self.estimate_complexity(query)

        result = SQLResult(
            query=query, explanation=explanation,
            tables_used=tables, estimated_complexity=complexity,
        )
        self._query_history.append(result)

        if engram:
            try:
                engram.episodic.store(
                    f"SQL generated: {query[:100]} (complexity: {complexity})",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Flux] SQL Query Generated"]
        lines.append(f"  Complexity: {complexity}")
        if tables:
            lines.append(f"  Tables: {', '.join(tables)}")
        lines.append(f"\n  ```sql\n  {query}\n  ```")
        if explanation:
            lines.append(f"\n  Explanation: {explanation}")

        return "\n".join(lines)
