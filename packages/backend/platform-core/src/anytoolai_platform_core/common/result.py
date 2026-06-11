from dataclasses import dataclass

@dataclass(frozen=True)
class Ok:
    value: object
