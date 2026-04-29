"""
Flux -- natural language to SQL query generator.
Converts plain-English questions into SQL queries given a database schema.

Inspired by:
  - defog-ai/sqlcoder (Apache 2.0) — open source text-to-SQL model
  - NumbersStation/NSText2SQL — text-to-SQL benchmarks
  - Spider benchmark (CC BY-SA 4.0) — text-to-SQL evaluation dataset
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class SQLResult:
    query: str
    explanation: str
    tables_used: list[str]
    estimated_complexity: str  # "simple", "moderate", "complex"


# SQL keyword patterns for complexity estimation
_COMPLEX_PATTERNS = ["JOIN", "SUBQUERY", "UNION", "HAVING", "WINDOW", "CTE", "WITH"]
_MODERATE_PATTERNS = ["GROUP BY", "ORDER BY", "DISTINCT", "COUNT", "SUM", "AVG"]


class FluxModule(AgentModule):
    name = "flux"
    description = "Natural language to SQL -- converts questions about data into SQL queries"
    version = "0.1.0"

    watch_events: list[str] = []
    coordination_targets: list[str] = []

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

    def generate_pattern_sql(self, question: str) -> str | None:
        """Generate SQL from common natural-language patterns without an LLM.

        Returns a SQL string if the question matches a known pattern, else None.
        Table and column names are resolved from registered schemas when possible.
        """
        q = question.lower()

        # Resolve a table name from registered schemas
        def best_table() -> str:
            for table in self._schemas:
                if table.lower() in q:
                    return table
            return next(iter(self._schemas), "table_name")

        # Resolve a numeric column from a table (prefer non-id columns)
        def numeric_col(table: str) -> str:
            cols = self._schemas.get(table, [])
            for c in cols:
                cl = c.lower()
                if any(kw in cl for kw in ("amount", "price", "cost", "total", "count", "value", "score", "age", "salary", "qty", "quantity")):
                    return c
            for c in cols:
                if c.lower() not in ("id",) and not c.lower().endswith("_id"):
                    return c
            return cols[0] if cols else "column_name"

        # Resolve a column mentioned explicitly in the question
        def mentioned_col(table: str) -> str | None:
            cols = self._schemas.get(table, [])
            for c in cols:
                if c.lower() in q:
                    return c
            return None

        table = best_table()
        col = mentioned_col(table) or numeric_col(table)

        # COUNT
        if any(p in q for p in ("how many", "count", "number of", "total number")):
            return f"SELECT COUNT(*) FROM {table}"

        # SELECT ALL
        if any(p in q for p in ("show all", "list all", "get all", "show me all", "list", "get all", "fetch all", "retrieve all", "display all")):
            return f"SELECT * FROM {table} LIMIT 100"

        # AVERAGE
        if any(p in q for p in ("average", "mean", "avg")):
            return f"SELECT AVG({col}) FROM {table}"

        # SUM
        if any(p in q for p in ("total", "sum", "summ")):
            return f"SELECT SUM({col}) FROM {table}"

        # MAX
        if any(p in q for p in ("maximum", "max", "highest", "largest", "biggest", "greatest", "top")):
            return f"SELECT MAX({col}) FROM {table}"

        # MIN
        if any(p in q for p in ("minimum", "min", "lowest", "smallest", "least", "bottom")):
            return f"SELECT MIN({col}) FROM {table}"

        return None

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

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Check if message contains a schema definition
        new_schemas = self.parse_schema(message)
        if new_schemas:
            self._schemas.update(new_schemas)
            if not any(c in message.lower() for c in ("show", "query", "select", "find", "get", "list")):
                table_list = ", ".join(f"{t} ({len(c)} cols)" for t, c in new_schemas.items())
                return f"[Flux] Schema registered: {table_list}. Ask a question about your data."

        # Attempt pattern-based SQL generation first (works without LLM)
        pattern_query = self.generate_pattern_sql(message)

        if not llm:
            if pattern_query:
                tables = self.extract_tables(pattern_query)
                complexity = self.estimate_complexity(pattern_query)
                result = SQLResult(
                    query=pattern_query,
                    explanation="Generated by pattern matching. For complex queries, configure an LLM provider.",
                    tables_used=tables,
                    estimated_complexity=complexity,
                )
                self._query_history.append(result)
                if engram:
                    try:
                        engram.episodic.store(
                            f"SQL generated (pattern): {pattern_query[:100]} (complexity: {complexity})",
                            source=self.name,
                        )
                    except Exception:
                        pass
                out = ["[Flux] SQL Query Generated (pattern-based)"]
                out.append(f"  Complexity: {complexity}")
                if tables:
                    out.append(f"  Tables: {', '.join(tables)}")
                out.append(f"\n  ```sql\n  {pattern_query}\n  ```")
                out.append("\n  Note: pattern-based generation. An LLM provider can handle more complex queries.")
                return "\n".join(out)
            return (
                "[Flux] Could not match a query pattern. "
                "Configure an LLM provider for complex SQL generation, "
                "or try phrasing your question as: 'how many', 'show all', 'average', 'total', 'maximum', or 'minimum'."
            )

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
            # Fall back to pattern-based if LLM call fails
            if pattern_query:
                tables = self.extract_tables(pattern_query)
                complexity = self.estimate_complexity(pattern_query)
                result = SQLResult(
                    query=pattern_query,
                    explanation="LLM call failed; generated by pattern matching.",
                    tables_used=tables,
                    estimated_complexity=complexity,
                )
                self._query_history.append(result)
                out = ["[Flux] SQL Query Generated (pattern fallback -- LLM call failed)"]
                out.append(f"  Complexity: {complexity}")
                if tables:
                    out.append(f"  Tables: {', '.join(tables)}")
                out.append(f"\n  ```sql\n  {pattern_query}\n  ```")
                return "\n".join(out)
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

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in ("data", "table", "column", "database", "schema", "query", "select")):
            return "Provide a schema or question about your data and Flux can generate a SQL query."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        return ""
