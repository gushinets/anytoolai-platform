from itertools import count
from time import time_ns
from uuid import uuid4

_ORDER_COUNTER = count()


def new_id(prefix: str) -> str:
    return f"{prefix}_{time_ns():020d}_{next(_ORDER_COUNTER):010d}_{uuid4().hex}"


def new_ordered_id(prefix: str) -> str:
    """Return an opaque ID whose lexical order follows creation order in this process."""
    return new_id(prefix)
