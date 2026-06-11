from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerSettings:
    queue_name: str = "platform_jobs"
