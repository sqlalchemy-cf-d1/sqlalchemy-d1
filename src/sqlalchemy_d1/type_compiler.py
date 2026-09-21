# sqlalchemy_d1/type_compiler.py
from sqlalchemy_cloudflare_d1.compiler import CloudflareD1TypeCompiler


class D1TypeCompiler(CloudflareD1TypeCompiler):
    def visit_d1_declared(self, type_, **kw):
        # Reflected types keep the name the column was declared with
        return type(type_).__name__
