from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class MetricsStore:
    request_count: int = 0
    request_count_by_status: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    request_latency_ms: list[float] = field(default_factory=list)
    lint_execution_ms: list[float] = field(default_factory=list)

    def record_request(self, status_code: int, duration_ms: float) -> None:
        self.request_count += 1
        self.request_count_by_status[status_code] += 1
        self.request_latency_ms.append(duration_ms)

    def record_lint_execution(self, duration_ms: float) -> None:
        self.lint_execution_ms.append(duration_ms)


metrics = MetricsStore()
