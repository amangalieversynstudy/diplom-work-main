"""What a piece of student code is made of, without keeping the code itself.

Two things come out of ``analyse``: the language constructs the code uses (``def``, ``lambda``,
comprehensions, ``try``...) and a fingerprint of its structure. The fingerprint ignores the names the
author chose for variables, functions and arguments, comments and docstrings, so two solutions that
differ only in naming get the same one. Only the fingerprint, the node count and the construct names are
stored in ``CodeRun``; the learner's last attempt stays where it always was, in ``TaskProgress.answer``.

A same-fingerprint pair is a reason for a teacher to look, never proof: for a short exercise there is
often just one natural solution, which is why ``authorship`` only compares solutions of a minimum size.
"""

import ast
import hashlib

# constructs a course author can mark as "not taught yet" for a step
CONSTRUCTS = ("def", "lambda", "comprehension", "try", "import", "class", "with")

_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def constructs_used(tree):
    """The names from ``CONSTRUCTS`` that appear in the parsed code."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.add("def")
        elif isinstance(node, ast.Lambda):
            found.add("lambda")
        elif isinstance(node, _COMPREHENSIONS):
            found.add("comprehension")
        elif isinstance(node, ast.Try):
            found.add("try")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            found.add("import")
        elif isinstance(node, ast.ClassDef):
            found.add("class")
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            found.add("with")
    return sorted(found)


class _Renamer(ast.NodeTransformer):
    """Replaces the names the author introduced by v0, v1, ... in order of appearance.

    Built-ins and attributes (``print``, ``len``, ``.append``) keep their names: they say what the
    program does, while the author's own names only say what the author likes.
    """

    def __init__(self, bound):
        self.bound = bound
        self.numbers = {}

    def _new(self, name):
        if name not in self.bound:
            return name
        return self.numbers.setdefault(name, f"v{len(self.numbers)}")

    def visit_Name(self, node):
        node.id = self._new(node.id)
        return node

    def visit_arg(self, node):
        node.arg = self._new(node.arg)
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):
        node.name = self._new(node.name)
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        node.name = self._new(node.name)
        self.generic_visit(node)
        return node


def _bound_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def _drop_docstrings(tree):
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body:
            body[:] = [
                stmt
                for stmt in body
                if not (
                    isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                )
            ] or [ast.Pass()]


def analyse(code):
    """{"fingerprint", "nodes", "constructs"} of *code*, or None when it does not parse."""
    try:
        tree = ast.parse(code or "")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    used = constructs_used(tree)
    _drop_docstrings(tree)
    tree = _Renamer(_bound_names(tree)).visit(tree)
    nodes = sum(1 for _ in ast.walk(tree))
    digest = hashlib.sha1(ast.dump(tree, annotate_fields=False).encode("utf-8")).hexdigest()
    return {"fingerprint": digest[:32], "nodes": nodes, "constructs": used}
