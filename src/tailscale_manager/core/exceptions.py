from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TemplateError(Exception):
    pass


@dataclass
class ConfigurationError(TemplateError):
    message: str = ""
    field: str | None = None
    hint: str | None = None
    docs_url: str | None = None

    def __str__(self) -> str:
        return self.message


@dataclass
class ServiceError(TemplateError):
    pass


@dataclass
class NotFoundError(TemplateError):
    pass


@dataclass
class TerraformError(TemplateError):
    command: str = ""
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    hint: str | None = None

    def __str__(self) -> str:
        return self.stderr or self.stdout
