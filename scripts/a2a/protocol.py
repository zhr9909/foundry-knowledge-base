from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any
import time


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    REWRITING = "rewriting"
    SEARCHING = "searching"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PartType(str, Enum):
    TEXT = "text"
    TOKEN = "token"
    CONTEXT = "context"
    MERMAID = "mermaid"
    COMPARISON = "comparison"
    ERROR = "error"


@dataclass
class Part:
    type: PartType
    content: Any
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type.value, "content": self.content, "metadata": self.metadata}


@dataclass
class AgentCard:
    agent_id: str
    name: str
    version: str
    description: str
    capabilities: list
    rate_limit: dict = field(default_factory=lambda: {"rpm": 60, "concurrent": 5})

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities,
            "rate_limit": self.rate_limit,
        }


@dataclass
class Task:
    task_id: str
    source: str
    target: str
    type: str
    input: dict
    status: TaskStatus = TaskStatus.PENDING
    output: Optional[dict] = None
    error: Optional[dict] = None
    stream: bool = False
    ttl_seconds: int = 120
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metrics: dict = field(default_factory=dict)

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds

    def mark_completed(self, output: dict):
        self.status = TaskStatus.COMPLETED
        self.output = output
        self.completed_at = time.time()

    def mark_failed(self, code: str, message: str, detail: str = ""):
        self.status = TaskStatus.FAILED
        self.error = {"code": code, "message": message, "detail": detail}
        self.completed_at = time.time()

    def to_dict(self) -> dict:
        d = {
            "task_id": self.task_id,
            "source": self.source,
            "target": self.target,
            "type": self.type,
            "status": self.status.value,
            "stream": self.stream,
            "created_at": self.created_at,
        }
        if self.status == TaskStatus.COMPLETED:
            d["output"] = self.output
        if self.status == TaskStatus.FAILED:
            d["error"] = self.error
        if self.completed_at:
            d["completed_at"] = self.completed_at
            d["duration_ms"] = int((self.completed_at - self.created_at) * 1000)
        if self.metrics:
            d["metrics"] = self.metrics
        return d
