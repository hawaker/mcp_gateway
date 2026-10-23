"""Json Path Filter。只支持 $.a.b、$[0] 和 ['键']，不截断正文。"""

import re
from typing import Any

_STEP = re.compile(r"""\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]|\['([^']*)'\]|\["([^"]*)"\]""")


def apply_jsonpath(data: Any, expression: str | None) -> Any:
    if expression is None:
        return data
    path = expression.strip()
    if path == "" or path == "$":
        return data
    if not path.startswith("$"):
        path = f"$.{path}" if not path.startswith((".", "[")) else f"${path}"
    current = data
    index = 1
    while index < len(path):
        match = _STEP.match(path, index)
        if match is None:
            return None
        key = match.group(1) or match.group(3) or match.group(4)
        if key is not None:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        else:
            item_index = int(match.group(2))
            if not isinstance(current, list) or item_index >= len(current) or item_index < 0:
                return None
            current = current[item_index]
        index = match.end()
    return current
