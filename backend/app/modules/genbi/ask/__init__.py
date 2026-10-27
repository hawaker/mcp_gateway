"""GenBI ask 管线：Wren NL→SQL → 组×源 ACL → 预览执行。"""

from .service import AskService, run_ask

__all__ = ["AskService", "run_ask"]
