import pytest
import os
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

# Import app logic
from cli import app, get_project_path, HiveNotInitializedError

runner = CliRunner()

class TestCLI:
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temp directory and cd into it."""
        cwd = os.getcwd()
        os.chdir(tmp_path)
        yield tmp_path
        os.chdir(cwd)

    def test_init_command(self, temp_project):
        """Test 'hive init' command."""
        # Mock Prompts
        with patch("rich.prompt.Prompt.ask") as mock_ask:
            mock_ask.side_effect = ["TestProject", "Desc", "", ""]
            
            result = runner.invoke(app, ["init"])
            
            if result.exit_code != 0:
                print(result.stdout)
                
            assert result.exit_code == 0
            assert "Hive initialisiert" in result.stdout
            assert (temp_project / ".hive").exists()

    def test_init_existing_fails(self, temp_project):
        """Test 'hive init' fails if already initialized."""
        (temp_project / ".hive").mkdir()
        
        # We need to mock input because prompt might still be triggered before check? 
        # No, check is first.
        # However, typer might catch Exit(1) and return 1.
        
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 1
        assert "Hive bereits initialisiert" in result.stdout

    def test_create_ticket(self, temp_project):
        """Test 'hive create-ticket'."""
        # Setup env
        hive_dir = temp_project / ".hive"
        hive_dir.mkdir()
        (hive_dir / "tickets").mkdir()
        
        # Mocking
        with patch("rich.prompt.Prompt.ask") as mock_ask:
            # ID, Title, Type, Priority
            mock_ask.side_effect = ["HIVE-001", "Test Ticket", "feature", "high"]
            
            # Mock input() for description
            with patch("builtins.input", side_effect=["Description line 1", ""]):
                result = runner.invoke(app, ["create-ticket"])
                
                if result.exit_code != 0:
                    print(f"Stdout: {result.stdout}")
                    import traceback
                    if result.exc_info:
                        traceback.print_exception(*result.exc_info)

                assert result.exit_code == 0
                assert "HIVE-001 erstellt" in result.stdout
                assert (hive_dir / "tickets" / "HIVE-001.yaml").exists()

    def test_status_command(self, temp_project):
        """Test 'hive status'."""
        hive_dir = temp_project / ".hive"
        tickets_dir = hive_dir / "tickets"
        
        # Create parents properly
        # Note: hive status calls get_tickets_dir which calls get_hive_dir -> get_project_path
        # So structure must exist
        tickets_dir.mkdir(parents=True)
        
        (tickets_dir / "TEST-1.yaml").write_text("""
id: TEST-1
title: Test
type: feature
priority: high
status: backlog
""")
        
        result = runner.invoke(app, ["status"])
        
        if result.exit_code != 0:
            print(result.stdout)
            
        assert result.exit_code == 0
        assert "TEST-1" in result.stdout

    def test_uninitialized_command_fails(self, temp_project):
        """Test commands fail outside initialized project."""
        # Ensure no .hive exists
        
        result = runner.invoke(app, ["status"])
        
        # Typer catches Exit(1) and returns 1. If it returns 2 from this test, it might be ArgumentError?
        # status takes no args.
        
        if result.exit_code != 1:
            print(f"Exit code: {result.exit_code}")
            print(result.stdout)
        
        assert result.exit_code == 1
        assert "Kein Hive-Projekt gefunden" in result.stdout
