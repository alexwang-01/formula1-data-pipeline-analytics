import ast
import importlib.util
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source", ROOT / "notebooks/00-common/source.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


def notebook(path):
    return ast.parse((ROOT / "notebooks" / path).read_text(encoding="utf-8"))


def render(node, values):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(str(render(v, values)) for v in node.values)
    if isinstance(node, ast.FormattedValue) and isinstance(node.value, ast.Name):
        return values[node.value.id]
    raise ValueError(f"Unsupported SQL expression: {ast.dump(node)}")


def queries(path, values):
    calls = [n for n in ast.walk(notebook(path))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "sql" and isinstance(n.func.value, ast.Name)
             and n.func.value.id == "spark"]
    return [render(n.args[0], values) for n in sorted(calls, key=lambda n: n.lineno)]


def duck_sql(sql):
    # Only test-engine dialect changes; notebook transformations stay authoritative.
    sql = re.sub(r"`([^`]+)`", r'"\1"', sql)
    return (sql.replace("<=>", "IS NOT DISTINCT FROM")
            .replace(" USING DELTA", "").replace("LEFT ANTI JOIN", "ANTI JOIN"))


def row_contract(path):
    for node in ast.walk(notebook(path)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "check_rows"):
            return ast.literal_eval(node.args[1]), ast.literal_eval(node.args[2])
    raise ValueError("Notebook needs an explicit row contract")
