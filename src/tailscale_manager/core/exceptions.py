from __future__ import annotations


class TemplateError(Exception):
    pass


class ConfigurationError(TemplateError):
    pass


class ServiceError(TemplateError):
    pass


class NotFoundError(TemplateError):
    pass


class TerraformError(TemplateError):
    pass
