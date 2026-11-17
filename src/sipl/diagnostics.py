from dataclasses import dataclass


@dataclass
class Diagnostic:
    severity: str
    code: str
    message: str
    span: object = None

    def to_dict(self):
        span = None
        if self.span is not None:
            span = self.span.to_dict()
        return {"severity": self.severity, "code": self.code,
                "message": self.message, "span": span}

    def format(self, source=None, filename="<input>"):
        if self.span is None:
            return f"{filename}: {self.severity}: {self.message}"
        text = f"{filename}:{self.span.line}:{self.span.column}: {self.severity}: {self.message}"
        if source is not None:
            lines = source.split("\n")
            if self.span.line <= len(lines):
                text += "\n    " + lines[self.span.line - 1]
                text += "\n    " + " " * (self.span.column - 1) + "^"
        return text


class SiplError(Exception):
    def __init__(self, diagnostic):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class SiplSyntaxError(SiplError):
    pass


class SiplRuntimeError(SiplError):
    pass
