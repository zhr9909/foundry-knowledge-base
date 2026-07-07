from .protocol import Part, PartType


def text_part(content: str, metadata: dict = None) -> Part:
    return Part(type=PartType.TEXT, content=content, metadata=metadata or {})


def token_part(content: str) -> Part:
    return Part(type=PartType.TOKEN, content=content)


def context_part(chunks: list, metadata: dict = None) -> Part:
    return Part(type=PartType.CONTEXT, content=chunks, metadata=metadata or {})


def mermaid_part(code: str, fmt: str = "mermaid") -> Part:
    return Part(type=PartType.MERMAID, content={"code": code, "format": fmt})


def comparison_part(headers: list, rows: list) -> Part:
    return Part(type=PartType.COMPARISON, content={"headers": headers, "rows": rows})


def error_part(code: str, message: str, detail: str = "") -> Part:
    return Part(type=PartType.ERROR, content={"code": code, "message": message, "detail": detail})
