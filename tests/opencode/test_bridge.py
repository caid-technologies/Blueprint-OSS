from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from fastapi import HTTPException

from apps.api.auth import UserContext, has_opencode_authoring_access, require_opencode_authoring_access
from apps.api.main import _runtime_config_settings
from apps.api.opencode_api import _require_owned_project
from apps.api.opencode_mcp import handle_opencode_mcp_json_rpc, opencode_mcp_tools
from forma_core.opencode.capabilities import CapabilityError, issue_capability, verify_capability
from forma_core.opencode.models import ConnectorEventInput, McpJsonRpcRequest, OpenCodeCommandStatus, OpenCodeEventKind, OpenCodeOperation
from forma_core.opencode.public_events import project_public_event
from forma_core.opencode.store import OpenCodeStore


class OpenCodeBridgeTests(unittest.IsolatedAsyncioTestCase):
    def test_allowed_email_is_server_derived_and_exact(self) -> None:
        user = UserContext(provider="clerk", subject="user_1", owner_user_id="user_1", is_authenticated=True, is_admin=True)
        with patch.dict(os.environ, {"FORMA_DEPLOYMENT_MODE": "hosted", "FORMA_AUTH_MODE": "clerk", "FORMA_OPENCODE_ALLOWED_EMAILS": "isayahculbertson@gmail.com"}, clear=True), patch("apps.api.auth.require_user_context", new=AsyncMock(return_value=user)), patch("apps.api.auth.clerk_user_email", return_value="isayahculbertson@gmail.com"):
            resolved = asyncio.run(require_opencode_authoring_access(object()))
        self.assertEqual("user_1", resolved.owner_user_id)

    def test_allowlist_defaults_to_deny_and_service_identity_cannot_bypass(self) -> None:
        service = UserContext(provider="mcp-api-key", subject="mcp-service", owner_user_id=None, is_authenticated=True, is_admin=True)
        with patch.dict(os.environ, {"FORMA_DEPLOYMENT_MODE": "hosted", "FORMA_AUTH_MODE": "clerk"}, clear=True), patch("apps.api.auth.require_user_context", new=AsyncMock(return_value=service)):
            with self.assertRaises(HTTPException) as denied:
                asyncio.run(require_opencode_authoring_access(object()))
        self.assertEqual(403, denied.exception.status_code)
        self.assertEqual("opencode_clerk_required", denied.exception.detail["code"])

    def test_runtime_authoring_access_is_limited_to_the_exact_allowlisted_email(self) -> None:
        allowed = UserContext(provider="clerk", subject="user_1", owner_user_id="user_1", is_authenticated=True, is_admin=False)
        denied = UserContext(provider="clerk", subject="user_2", owner_user_id="user_2", is_authenticated=True, is_admin=False)
        with patch.dict(os.environ, {"FORMA_OPENCODE_ALLOWED_EMAILS": "isayahculbertson@gmail.com"}, clear=True), patch(
            "apps.api.auth.clerk_user_email",
            side_effect=lambda user_id: "isayahculbertson@gmail.com" if user_id == "user_1" else "someone-else@example.com",
        ):
            self.assertTrue(has_opencode_authoring_access(allowed))
            self.assertFalse(has_opencode_authoring_access(denied))

    def test_allowlisted_runtime_config_falls_back_when_user_settings_are_unreadable(self) -> None:
        user = UserContext(provider="clerk", subject="user_1", owner_user_id="user_1", is_authenticated=True, is_admin=False)
        with patch("apps.api.main._resolve_user_integrations", side_effect=RuntimeError("key mismatch")), patch(
            "apps.api.main.has_opencode_authoring_access", return_value=True,
        ):
            self.assertIsNone(_runtime_config_settings(user))

        with patch("apps.api.main._resolve_user_integrations", side_effect=RuntimeError("key mismatch")), patch(
            "apps.api.main.has_opencode_authoring_access", return_value=False,
        ):
            with self.assertRaises(RuntimeError):
                _runtime_config_settings(user)

    def test_project_scope_rejects_a_foreign_owner_before_session_use(self) -> None:
        with patch("apps.api.opencode_api.get_project_identity", return_value={"owner_user_id": "another-user", "status": "active"}):
            with self.assertRaises(HTTPException) as denied:
                _require_owned_project(str(uuid4()), "user_a")
        self.assertEqual(404, denied.exception.status_code)
        self.assertEqual("opencode_project_not_found", denied.exception.detail["code"])

    def test_capability_rejects_cross_session_and_tampering(self) -> None:
        with patch.dict(os.environ, {"FORMA_OPENCODE_CAPABILITY_SECRET": "s" * 32}, clear=True):
            token = issue_capability(connector_id="mini", session_id="session_a", project_id="project_a", owner_user_id="user_a", scopes=frozenset({"poll"}))
            self.assertEqual("user_a", verify_capability(token, session_id="session_a", project_id="project_a", scope="poll").owner_user_id)
            with self.assertRaises(CapabilityError):
                verify_capability(token, session_id="session_b", scope="poll")
            with self.assertRaises(CapabilityError):
                verify_capability(token[:-1] + ("A" if token[-1] != "A" else "B"), session_id="session_a", scope="poll")

    def test_event_projection_removes_internal_payloads_and_raw_errors(self) -> None:
        project_id = uuid4()
        event = ConnectorEventInput.model_validate({
            "event_id": "evt_1",
            "kind": "assistant_message",
            "message": "diff: C:\\secret\\project\\main.py api_key=sk-secret",
            "tool_call": {"command": "cat C:\\secret"},
            "reasoning": "hidden reasoning",
            "raw_exception": "provider token=secret",
        })
        public = project_public_event(event, sequence=1, session_id="session", project_id=project_id)
        serialized = str(public.model_dump(mode="json"))
        self.assertNotIn("secret\\project", serialized)
        self.assertNotIn("sk-secret", serialized)
        self.assertNotIn("tool_call", serialized)
        self.assertIsNone(public.error)
        self.assertEqual(OpenCodeEventKind.ASSISTANT_MESSAGE, public.kind)

    def test_restricted_mcp_surface_excludes_forbidden_tools(self) -> None:
        names = {str(tool["name"]) for tool in opencode_mcp_tools()}
        self.assertEqual({
            "forma.opencode.create_project",
            "forma.opencode.read_project",
            "forma.opencode.update_project",
            "forma.opencode.compile_project",
            "forma.opencode.validate_project",
        }, names)
        with patch.dict(os.environ, {"FORMA_OPENCODE_CAPABILITY_SECRET": "s" * 32}, clear=True):
            from forma_core.opencode.capabilities import ConnectorCapability
            capability = ConnectorCapability("mini", "session", str(uuid4()), "user", int(datetime.now(timezone.utc).timestamp()) + 60, "nonce", frozenset({"mcp"}))
            response = asyncio.run(handle_opencode_mcp_json_rpc(McpJsonRpcRequest.model_validate({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "forma.generate_project", "arguments": {}}}), capability))
        self.assertEqual("authorization_required", response["error"]["data"]["code"])

    def test_store_is_idempotent_leased_and_cursorable(self) -> None:
        project_id = str(uuid4())
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"FORMA_USER_SECRETS_KEY": "test-key"}, clear=False):
            path = os.path.join(directory, "opencode.sqlite")
            store = OpenCodeStore(path)
            try:
                session = store.create_session(session_id="session", connector_id="mini", owner_user_id="user", project_id=project_id)
                first = store.create_command(command_id="command", session=session, operation=OpenCodeOperation.PROJECT_MESSAGE, idempotency_key="same", message="build")
                duplicate = store.create_command(command_id="other", session=session, operation=OpenCodeOperation.PROJECT_MESSAGE, idempotency_key="same", message="build")
                self.assertEqual(first.command_id, duplicate.command_id)
                self.assertIsNotNone(first.message_ciphertext)
                self.assertNotIn("build", str(first.message_ciphertext))
            finally:
                store.close()

            reopened = OpenCodeStore(path)
            try:
                claimed = reopened.claim_next(connector_id="mini", session_id="session")
                self.assertIsNotNone(claimed)
                assert claimed is not None
                self.assertEqual("build", claimed.message)
                public = project_public_event(ConnectorEventInput(event_id="event", kind="working"), sequence=1, session_id="session", project_id=UUID(project_id))
                reopened.add_event(public)
                self.assertEqual(1, len(reopened.list_events("session", 0, 10)))
            finally:
                reopened.close()

    def test_store_is_session_scoped_renews_leases_and_completes_idempotently(self) -> None:
        first_project_id = str(uuid4())
        second_project_id = str(uuid4())
        with patch.dict(os.environ, {"FORMA_USER_SECRETS_KEY": "test-key"}, clear=False):
            store = OpenCodeStore(":memory:")
            try:
                first_session = store.create_session(session_id="session_a", connector_id="mini", owner_user_id="user", project_id=first_project_id)
                second_session = store.create_session(session_id="session_b", connector_id="mini", owner_user_id="user", project_id=second_project_id)
                store.create_command(command_id="command_a", session=first_session, operation=OpenCodeOperation.PROJECT_MESSAGE, idempotency_key="a", message="first")
                store.create_command(command_id="command_b", session=second_session, operation=OpenCodeOperation.PROJECT_MESSAGE, idempotency_key="b", message="second")
                claimed = store.claim_next(connector_id="mini", session_id="session_a")
                self.assertIsNotNone(claimed)
                assert claimed is not None
                self.assertEqual("command_a", claimed.command_id)
                stored = store.get_command(claimed.command_id)
                self.assertIsNotNone(stored)
                assert stored is not None
                old_expiry = stored.lease_expires_at
                renewed = store.heartbeat(stored, claimed.lease_token)
                self.assertNotEqual(old_expiry, renewed.lease_expires_at)
                completed = store.complete(renewed, claimed.lease_token, OpenCodeCommandStatus.SUCCEEDED)
                self.assertEqual(OpenCodeCommandStatus.SUCCEEDED, completed.status)
                self.assertEqual(completed, store.complete(completed, "not-needed-after-terminal", OpenCodeCommandStatus.SUCCEEDED))
                self.assertIsNotNone(store.claim_next(connector_id="mini", session_id="session_b"))
            finally:
                store.close()
