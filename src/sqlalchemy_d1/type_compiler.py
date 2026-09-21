# sqlalchemy_d1/type_compiler.py
from sqlalchemy_cloudflare_d1.compiler import CloudflareD1TypeCompiler


class D1TypeCompiler(CloudflareD1TypeCompiler):
    def _type_name(self, name, parent, type_, kw):
        # Tables are created with the same types as upstream
        if kw.get("type_expression") is not None:
            return parent(type_, **kw)
        return name

    def visit_DATETIME(self, type_, **kw):
        return self._type_name("DATETIME", super().visit_DATETIME, type_, kw)

    def visit_TIMESTAMP(self, type_, **kw):
        return self._type_name("TIMESTAMP", super().visit_TIMESTAMP, type_, kw)

    def visit_DATE(self, type_, **kw):
        return self._type_name("DATE", super().visit_DATE, type_, kw)

    def visit_TIME(self, type_, **kw):
        return self._type_name("TIME", super().visit_TIME, type_, kw)

    def visit_BOOLEAN(self, type_, **kw):
        return self._type_name("BOOLEAN", super().visit_BOOLEAN, type_, kw)
