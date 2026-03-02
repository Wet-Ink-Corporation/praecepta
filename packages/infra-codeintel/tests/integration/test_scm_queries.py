"""Integration tests for .scm tag query files.

Parses real code snippets with tree-sitter and verifies that tag queries
capture expected definitions and references.
"""

from __future__ import annotations

import importlib.resources

import pytest
import tree_sitter_language_pack as tslp
from tree_sitter import Query, QueryCursor

PYTHON_SNIPPET = """\
import os
from pathlib import Path

class AuthService:
    def authenticate(self, username: str) -> bool:
        return self.validate(username)

    def validate(self, username: str) -> bool:
        return len(username) > 0

def login(credentials: dict) -> None:
    service = AuthService()
    service.authenticate(credentials["user"])

MAX_RETRIES = 3
"""

TS_SNIPPET = """\
import { Request } from "express";

interface User {
    name: string;
    email: string;
}

type UserId = string;

class UserService {
    async findUser(id: UserId): Promise<User> {
        return fetchUser(id);
    }
}

export function createApp(): void {
    const service = new UserService();
    service.findUser("123");
}
"""

JS_SNIPPET = """\
import { Router } from "express";

class ApiController {
    handleRequest(req) {
        return processData(req.body);
    }
}

function setup() {
    const controller = new ApiController();
    controller.handleRequest({});
}

const PORT = 3000;
"""


def _load_scm(lang: str) -> str:
    """Load a .scm query file for the given language."""
    return (
        importlib.resources.files("praecepta.infra.codeintel.parser.queries")
        .joinpath(f"{lang}.scm")
        .read_text()
    )


def _run_captures(lang: str, source: str) -> dict[str, list[object]]:
    """Parse source with tree-sitter and run .scm query captures."""
    parser = tslp.get_parser(lang)
    tree = parser.parse(source.encode("utf-8"))
    language = tslp.get_language(lang)
    scm_text = _load_scm(lang)
    query = Query(language, scm_text)
    cursor = QueryCursor(query)
    return cursor.captures(tree.root_node)


def _get_captured_names(captures: dict[str, list[object]], key: str) -> list[str]:
    """Extract node text from captures for a given key."""
    nodes = captures.get(key, [])
    return [node.text.decode("utf-8") for node in nodes]  # type: ignore[union-attr]


@pytest.mark.integration
class TestPythonQueries:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.captures = _run_captures("python", PYTHON_SNIPPET)

    def test_class_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.class")
        assert "AuthService" in names

    def test_method_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.method")
        assert "authenticate" in names
        assert "validate" in names

    def test_function_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.function")
        assert "login" in names

    def test_variable_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.variable")
        assert "MAX_RETRIES" in names

    def test_function_call_references(self) -> None:
        names = _get_captured_names(self.captures, "name.reference.call")
        assert "AuthService" in names
        assert "len" in names

    def test_method_call_references(self) -> None:
        names = _get_captured_names(self.captures, "name.reference.call")
        assert "validate" in names
        assert "authenticate" in names

    def test_import_references(self) -> None:
        names = _get_captured_names(self.captures, "name.reference.import")
        assert "os" in names
        assert "Path" in names


@pytest.mark.integration
class TestTypeScriptQueries:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.captures = _run_captures("typescript", TS_SNIPPET)

    def test_interface_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.interface")
        assert "User" in names

    def test_type_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.type")
        assert "UserId" in names

    def test_class_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.class")
        assert "UserService" in names

    def test_method_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.method")
        assert "findUser" in names

    def test_function_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.function")
        assert "createApp" in names

    def test_function_call_references(self) -> None:
        names = _get_captured_names(self.captures, "name.reference.call")
        assert "fetchUser" in names

    def test_method_call_references(self) -> None:
        names = _get_captured_names(self.captures, "name.reference.call")
        assert "findUser" in names

    def test_import_references(self) -> None:
        names = _get_captured_names(self.captures, "name.reference.import")
        # The import source string includes quotes
        assert any("express" in n for n in names)


@pytest.mark.integration
class TestJavaScriptQueries:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.captures = _run_captures("javascript", JS_SNIPPET)

    def test_class_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.class")
        assert "ApiController" in names

    def test_method_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.method")
        assert "handleRequest" in names

    def test_function_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.function")
        assert "setup" in names

    def test_variable_definitions(self) -> None:
        names = _get_captured_names(self.captures, "name.definition.variable")
        assert "PORT" in names

    def test_function_call_references(self) -> None:
        names = _get_captured_names(self.captures, "name.reference.call")
        assert "processData" in names

    def test_method_call_references(self) -> None:
        names = _get_captured_names(self.captures, "name.reference.call")
        assert "handleRequest" in names

    def test_import_references(self) -> None:
        names = _get_captured_names(self.captures, "name.reference.import")
        assert any("express" in n for n in names)
