"""Shared fixtures for tests."""

import os
import tempfile
import shutil
from pathlib import Path

import pytest
import pytest_asyncio


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    dir_path = tempfile.mkdtemp(prefix="hive_test_")
    yield Path(dir_path)
    # Cleanup
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def temp_file(temp_dir):
    """Create a temporary file in the temp directory."""
    file_path = temp_dir / "test_file.txt"
    file_path.write_text("Line 1\nLine 2\nLine 3\n")
    return file_path


@pytest.fixture
def temp_git_repo(temp_dir):
    """Create a temporary git repository."""
    import subprocess
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_dir, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_dir, capture_output=True
    )
    
    # Create initial commit
    readme = temp_dir / "README.md"
    readme.write_text("# Test Project\n")
    subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_dir, capture_output=True
    )
    
    return temp_dir


@pytest.fixture
def sample_ticket_data():
    """Sample ticket data for testing."""
    return {
        "id": "TEST-001",
        "title": "Test Ticket",
        "description": "This is a test ticket.",
        "type": "feature",
        "priority": "medium",
        "status": "backlog",
    }


@pytest.fixture
def sample_project_config():
    """Sample project configuration."""
    return {
        "name": "Test Project",
        "description": "A test project",
        "tech_stack": {
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
            "databases": ["PostgreSQL"],
        },
    }
