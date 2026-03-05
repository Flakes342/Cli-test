from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List


def run(argument: str) -> Dict[str, Any]:
    query_file = Path(argument.strip().strip('"').strip("'"))
    if not query_file.exists():
        raise FileNotFoundError(f"SQL file not found: {query_file}")

    query = query_file.read_text(encoding="utf-8")
    db = sqlite3.connect(":memory:")
    cur = db.cursor()
    cur.execute("CREATE TABLE sample(id INTEGER, value TEXT)")
    cur.executemany("INSERT INTO sample VALUES(?,?)", [(1, "a"), (2, "b")])
    cur.execute(query)
    rows: List[Any] = cur.fetchall()
    db.close()
    return {"rows": rows, "row_count": len(rows)}
