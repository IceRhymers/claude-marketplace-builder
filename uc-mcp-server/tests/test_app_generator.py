"""Tests for the DAB (Databricks Asset Bundle) app generator."""

from __future__ import annotations

import pathlib

import pytest
import yaml

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


# ==============================================================================
# render_databricks_yml
# ==============================================================================


class TestRenderDatabricksYml:
    """Tests for the databricks.yml renderer."""

    def test_contains_bundle_name(self):
        from uc_mcp.codegen.app_generator import render_databricks_yml

        result = render_databricks_yml("slack", "MCP server for Slack API")
        parsed = yaml.safe_load(result)
        assert parsed["bundle"]["name"] == "slack-mcp-server"

    def test_resource_key_uses_underscores(self):
        from uc_mcp.codegen.app_generator import render_databricks_yml

        result = render_databricks_yml("slack", "desc")
        parsed = yaml.safe_load(result)
        assert "slack_mcp" in parsed["resources"]["apps"]

    def test_app_name(self):
        from uc_mcp.codegen.app_generator import render_databricks_yml

        result = render_databricks_yml("slack", "desc")
        parsed = yaml.safe_load(result)
        app = parsed["resources"]["apps"]["slack_mcp"]
        assert app["name"] == "slack-mcp-server"

    def test_description(self):
        from uc_mcp.codegen.app_generator import render_databricks_yml

        result = render_databricks_yml("slack", "MCP server for Slack API")
        parsed = yaml.safe_load(result)
        app = parsed["resources"]["apps"]["slack_mcp"]
        assert app["description"] == "MCP server for Slack API"

    def test_source_code_path(self):
        from uc_mcp.codegen.app_generator import render_databricks_yml

        result = render_databricks_yml("slack", "desc")
        parsed = yaml.safe_load(result)
        app = parsed["resources"]["apps"]["slack_mcp"]
        assert app["source_code_path"] == "."

    def test_targets(self):
        from uc_mcp.codegen.app_generator import render_databricks_yml

        result = render_databricks_yml("slack", "desc")
        parsed = yaml.safe_load(result)
        assert "dev" in parsed["targets"]
        assert "prod" in parsed["targets"]
        assert parsed["targets"]["dev"]["mode"] == "development"
        assert parsed["targets"]["dev"]["default"] is True
        assert parsed["targets"]["prod"]["mode"] == "production"

    def test_hyphenated_name(self):
        from uc_mcp.codegen.app_generator import render_databricks_yml

        result = render_databricks_yml("my-cool-service", "desc")
        parsed = yaml.safe_load(result)
        assert parsed["bundle"]["name"] == "my-cool-service-mcp-server"
        # Resource key must use underscores, not hyphens
        assert "my_cool_service_mcp" in parsed["resources"]["apps"]


# ==============================================================================
# render_app_yaml
# ==============================================================================


class TestRenderAppYaml:
    """Tests for the app.yaml renderer."""

    def test_command_uses_uv_run(self):
        from uc_mcp.codegen.app_generator import render_app_yaml

        result = render_app_yaml("slack", "slack_connection")
        parsed = yaml.safe_load(result)
        cmd = parsed["command"]
        assert "uv" in cmd
        assert "run" in cmd

    def test_env_has_connection_name(self):
        from uc_mcp.codegen.app_generator import render_app_yaml

        result = render_app_yaml("slack", "slack_connection")
        parsed = yaml.safe_load(result)
        env_vars = {e["name"]: e["value"] for e in parsed["env"]}
        assert env_vars["UC_CONNECTION_NAME"] == "slack_connection"

    def test_different_connection_name(self):
        from uc_mcp.codegen.app_generator import render_app_yaml

        result = render_app_yaml("jira", "jira_oauth_conn")
        parsed = yaml.safe_load(result)
        env_vars = {e["name"]: e["value"] for e in parsed["env"]}
        assert env_vars["UC_CONNECTION_NAME"] == "jira_oauth_conn"


# ==============================================================================
# render_pyproject_toml
# ==============================================================================


class TestRenderPyprojectToml:
    """Tests for the pyproject.toml renderer."""

    def test_project_name(self):
        from uc_mcp.codegen.app_generator import render_pyproject_toml

        result = render_pyproject_toml("slack")
        assert 'name = "slack-mcp-server"' in result

    def test_dep_mcp(self):
        from uc_mcp.codegen.app_generator import render_pyproject_toml

        result = render_pyproject_toml("slack")
        assert "mcp" in result

    def test_dep_databricks_sdk(self):
        from uc_mcp.codegen.app_generator import render_pyproject_toml

        result = render_pyproject_toml("slack")
        assert "databricks-sdk" in result

    def test_dep_starlette(self):
        from uc_mcp.codegen.app_generator import render_pyproject_toml

        result = render_pyproject_toml("slack")
        assert "starlette" in result

    def test_dep_uvicorn(self):
        from uc_mcp.codegen.app_generator import render_pyproject_toml

        result = render_pyproject_toml("slack")
        assert "uvicorn" in result

    def test_dep_pyyaml(self):
        from uc_mcp.codegen.app_generator import render_pyproject_toml

        result = render_pyproject_toml("slack")
        assert "pyyaml" in result

    def test_entry_point(self):
        from uc_mcp.codegen.app_generator import render_pyproject_toml

        result = render_pyproject_toml("slack")
        assert "slack-mcp-server" in result
        assert "app.main:main" in result


# ==============================================================================
# render_requirements_txt
# ==============================================================================


class TestRenderRequirementsTxt:
    """Tests for the requirements.txt renderer."""

    def test_contains_mcp(self):
        from uc_mcp.codegen.app_generator import render_requirements_txt

        result = render_requirements_txt()
        assert "mcp>=1.8" in result

    def test_contains_databricks_sdk(self):
        from uc_mcp.codegen.app_generator import render_requirements_txt

        result = render_requirements_txt()
        assert "databricks-sdk>=0.30.0" in result

    def test_contains_starlette(self):
        from uc_mcp.codegen.app_generator import render_requirements_txt

        result = render_requirements_txt()
        assert "starlette" in result

    def test_contains_uvicorn(self):
        from uc_mcp.codegen.app_generator import render_requirements_txt

        result = render_requirements_txt()
        assert "uvicorn" in result

    def test_contains_pyyaml(self):
        from uc_mcp.codegen.app_generator import render_requirements_txt

        result = render_requirements_txt()
        assert "pyyaml" in result


# ==============================================================================
# render_main_py
# ==============================================================================


class TestRenderMainPy:
    """Tests for the self-contained main.py renderer."""

    def test_imports_yaml(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "import yaml" in result

    def test_imports_mcp_server(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "from mcp.server" in result

    def test_imports_session_manager_from_correct_module(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "from mcp.server.streamable_http_manager import StreamableHTTPSessionManager" in result

    def test_does_not_import_from_streamable_http(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        # Should NOT import from the wrong module
        assert "from mcp.server.streamable_http import StreamableHTTPSessionManager" not in result

    def test_imports_contextlib(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "import contextlib" in result

    def test_imports_starlette(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "Starlette" in result

    def test_imports_uvicorn(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "import uvicorn" in result

    def test_uses_lifespan(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "lifespan" in result
        assert "session_manager.run()" in result

    def test_uses_mount_for_mcp(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert 'Mount("/mcp"' in result or "Mount('/mcp'" in result

    def test_uses_app_param_not_server(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "StreamableHTTPSessionManager(\n        app=server," in result or \
               "StreamableHTTPSessionManager(\n        app=server" in result

    def test_uses_contextvars_for_forwarded_token(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "import contextvars" in result
        assert "_forwarded_token" in result

    def test_middleware_captures_forwarded_token(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "x-forwarded-access-token" in result.lower()
        assert "ForwardedTokenMiddleware" in result or "_forwarded_token.set(" in result

    def test_get_workspace_client_reads_context_var(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "_forwarded_token.get(" in result

    def test_definition_path_resolves_to_project_root(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        # main.py is at src/app/main.py — need 3 .parent calls to reach project root
        assert ".parent.parent.parent" in result

    def test_contains_definition_path(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "slack.yaml" in result

    def test_contains_connection_name(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "slack_connection" in result

    def test_contains_workspace_client(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "WorkspaceClient" in result

    def test_contains_forwarded_token(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "X-Forwarded-Access-Token" in result

    def test_contains_model_serving_credentials(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "ModelServingUserCredentials" in result

    def test_contains_main_function(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "def main()" in result

    def test_does_not_import_uc_mcp(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        assert "from uc_mcp" not in result
        assert "import uc_mcp" not in result

    def test_no_str_coercion_on_query_params(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        # query_params should NOT wrap values in str()
        assert "str(params.pop(qp))" not in result
        assert "str(v) for" not in result

    def test_is_valid_python(self):
        from uc_mcp.codegen.app_generator import render_main_py

        result = render_main_py("slack", "slack_connection")
        compile(result, "main.py", "exec")  # Raises SyntaxError if invalid


# ==============================================================================
# generate_app orchestrator
# ==============================================================================


class TestGenerateApp:
    """Tests for the generate_app orchestrator."""

    def test_creates_directory_structure(self, tmp_path):
        from uc_mcp.codegen.app_generator import generate_app

        defn_path = FIXTURES / "simple_definition.yaml"
        output = tmp_path / "output"
        generate_app(str(defn_path), output_dir=str(output))

        expected_files = [
            output / "databricks.yml",
            output / "app.yaml",
            output / "pyproject.toml",
            output / "requirements.txt",
            output / "src" / "app" / "__init__.py",
            output / "src" / "app" / "main.py",
            output / "scripts" / "deploy.sh",
        ]
        for f in expected_files:
            assert f.exists(), f"Expected {f} to exist"

    def test_copies_definition_yaml(self, tmp_path):
        from uc_mcp.codegen.app_generator import generate_app

        defn_path = FIXTURES / "simple_definition.yaml"
        output = tmp_path / "output"
        generate_app(str(defn_path), output_dir=str(output))

        copied = output / "definitions" / "test-service.yaml"
        assert copied.exists()
        # Contents should match the original
        assert copied.read_text() == defn_path.read_text()

    def test_invalid_definition_raises_value_error(self, tmp_path):
        from uc_mcp.codegen.app_generator import generate_app

        bad_def = FIXTURES / "invalid_definitions" / "missing_name.yaml"
        output = tmp_path / "output"
        with pytest.raises(ValueError):
            generate_app(str(bad_def), output_dir=str(output))
        # Should not create the output directory
        assert not output.exists()

    def test_default_output_path(self, tmp_path, monkeypatch):
        from uc_mcp.codegen.app_generator import generate_app

        defn_path = FIXTURES / "simple_definition.yaml"
        # Change to tmp_path so default build/output/ goes there
        monkeypatch.chdir(tmp_path)
        result = generate_app(str(defn_path))

        expected = tmp_path / "generated_mcp_servers" / "test-service-app"
        assert pathlib.Path(result).resolve() == expected.resolve()
        assert expected.exists()

    def test_custom_output_path(self, tmp_path):
        from uc_mcp.codegen.app_generator import generate_app

        defn_path = FIXTURES / "simple_definition.yaml"
        custom_output = tmp_path / "my-custom-dir"
        result = generate_app(str(defn_path), output_dir=str(custom_output))

        assert pathlib.Path(result) == custom_output
        assert custom_output.exists()

    def test_nonexistent_definition_raises_file_not_found(self, tmp_path):
        from uc_mcp.codegen.app_generator import generate_app

        with pytest.raises(FileNotFoundError):
            generate_app("/nonexistent/path.yaml", output_dir=str(tmp_path / "out"))

    def test_overwrites_existing_output(self, tmp_path):
        from uc_mcp.codegen.app_generator import generate_app

        defn_path = FIXTURES / "simple_definition.yaml"
        output = tmp_path / "output"
        # First run
        generate_app(str(defn_path), output_dir=str(output))
        # Second run should not error
        generate_app(str(defn_path), output_dir=str(output))
        assert (output / "databricks.yml").exists()


# ==============================================================================
# render_deploy_script
# ==============================================================================


class TestRenderDeployScript:
    """Tests for the deploy.sh renderer."""

    def test_contains_shebang(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert result.startswith("#!/usr/bin/env bash")

    def test_contains_strict_mode(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "set -euo pipefail" in result

    def test_contains_bundle_validate(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "databricks bundle validate" in result

    def test_contains_bundle_deploy(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "databricks bundle deploy" in result

    def test_contains_apps_start(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "databricks apps start" in result

    def test_contains_apps_stop(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "databricks apps stop" in result

    def test_contains_apps_deploy(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "databricks apps deploy" in result

    def test_contains_bundle_summary(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "databricks bundle summary -o json" in result

    def test_default_target_is_dev(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "${TARGET:-dev}" in result

    def test_contains_jq(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "jq" in result

    def test_contains_prerequisite_checks(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "command -v databricks" in result or "which databricks" in result
        assert "command -v jq" in result or "which jq" in result

    def test_contains_help_subcommand(self):
        from uc_mcp.codegen.app_generator import render_deploy_script

        result = render_deploy_script("slack")
        assert "help" in result
        assert "Usage:" in result or "usage:" in result.lower()


# ==============================================================================
# Content correctness (using slack_definition.yaml)
# ==============================================================================


class TestContentCorrectness:
    """Verify generated file contents for a known definition."""

    @pytest.fixture
    def slack_app(self, tmp_path):
        from uc_mcp.codegen.app_generator import generate_app

        defn_path = FIXTURES / "slack_definition.yaml"
        output = tmp_path / "slack-app"
        generate_app(str(defn_path), output_dir=str(output))
        return output

    def test_databricks_yml_bundle_name(self, slack_app):
        parsed = yaml.safe_load((slack_app / "databricks.yml").read_text())
        assert parsed["bundle"]["name"] == "slack-mcp-server"

    def test_databricks_yml_resource_key(self, slack_app):
        parsed = yaml.safe_load((slack_app / "databricks.yml").read_text())
        assert "slack_mcp" in parsed["resources"]["apps"]

    def test_app_yaml_command(self, slack_app):
        parsed = yaml.safe_load((slack_app / "app.yaml").read_text())
        cmd = parsed["command"]
        assert "slack-mcp-server" in cmd

    def test_app_yaml_connection(self, slack_app):
        parsed = yaml.safe_load((slack_app / "app.yaml").read_text())
        env_vars = {e["name"]: e["value"] for e in parsed["env"]}
        assert env_vars["UC_CONNECTION_NAME"] == "slack_connection"

    def test_pyproject_name(self, slack_app):
        content = (slack_app / "pyproject.toml").read_text()
        assert 'name = "slack-mcp-server"' in content

    def test_pyproject_entry_point(self, slack_app):
        content = (slack_app / "pyproject.toml").read_text()
        assert "app.main:main" in content

    def test_main_py_valid_python(self, slack_app):
        content = (slack_app / "src" / "app" / "main.py").read_text()
        compile(content, "main.py", "exec")

    def test_deploy_script_exists_and_executable(self, slack_app):
        deploy = slack_app / "scripts" / "deploy.sh"
        assert deploy.exists()
        assert deploy.stat().st_mode & 0o111, "deploy.sh should be executable"

    def test_deploy_script_has_shebang(self, slack_app):
        content = (slack_app / "scripts" / "deploy.sh").read_text()
        assert content.startswith("#!/usr/bin/env bash")

    def test_requirements_txt_exists(self, slack_app):
        reqs = slack_app / "requirements.txt"
        assert reqs.exists()
        content = reqs.read_text()
        assert "mcp" in content

    def test_definition_copied(self, slack_app):
        copied = slack_app / "definitions" / "slack.yaml"
        assert copied.exists()
        original = FIXTURES / "slack_definition.yaml"
        assert copied.read_text() == original.read_text()


# ==============================================================================
# CLI integration
# ==============================================================================


class TestAppCommand:
    """Tests for the `app` CLI subcommand."""

    def test_app_command_calls_generate_app(self, tmp_path, monkeypatch):
        import sys

        from unittest.mock import patch

        defn_path = str(FIXTURES / "simple_definition.yaml")
        output = str(tmp_path / "out")
        monkeypatch.setattr(
            sys,
            "argv",
            ["uc-mcp", "app", defn_path, "--output", output],
        )

        with patch("uc_mcp.codegen.app_generator.generate_app", return_value=output) as mock_gen:
            from uc_mcp.__main__ import main

            main()
            mock_gen.assert_called_once_with(defn_path, output_dir=output)

    def test_output_flag_passed_through(self, tmp_path, monkeypatch):
        import sys

        from unittest.mock import patch

        defn_path = str(FIXTURES / "simple_definition.yaml")
        custom = str(tmp_path / "custom")
        monkeypatch.setattr(
            sys,
            "argv",
            ["uc-mcp", "app", defn_path, "-o", custom],
        )

        with patch("uc_mcp.codegen.app_generator.generate_app", return_value=custom) as mock_gen:
            from uc_mcp.__main__ import main

            main()
            mock_gen.assert_called_once_with(defn_path, output_dir=custom)

    def test_missing_definition_arg_exits(self, monkeypatch):
        import sys

        monkeypatch.setattr(sys, "argv", ["uc-mcp", "app"])
        with pytest.raises(SystemExit) as exc_info:
            from uc_mcp.__main__ import main

            main()
        assert exc_info.value.code == 2
