import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from core.activity_logger import ActivityLogger, get_activity_logger

class TestActivityLogger:
    @pytest.fixture
    def logger(self, tmp_path):
        """Fixture for a fresh ActivityLogger instance."""
        ActivityLogger.reset()
        logger = ActivityLogger(workspace_path=str(tmp_path), _reset=True)
        yield logger
        ActivityLogger.reset()

    def test_singleton_pattern(self, tmp_path):
        """Test that ActivityLogger behaves as a singleton."""
        ActivityLogger.reset()
        logger1 = ActivityLogger(workspace_path=str(tmp_path))
        logger2 = ActivityLogger(workspace_path=str(tmp_path))
        
        assert logger1 is logger2
        
        # Test helper function
        logger3 = get_activity_logger(str(tmp_path))
        assert logger3 is logger1

    def test_log_creation(self, logger):
        """Test basic log file creation and writing."""
        logger.log("test_event", agent="agent-007", data="test_data")
        
        assert logger.log_file.exists()
        
        with open(logger.log_file) as f:
            lines = f.readlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["type"] == "test_event"
            assert entry["agent"] == "agent-007"
            assert entry["data"] == "test_data"
            assert "ts" in entry

    def test_get_events_filtering(self, logger):
        """Test filtering events via get_events."""
        # Setup data
        logger.log("type1", agent="agentA", ticket="T1")
        logger.log("type1", agent="agentB", ticket="T1")
        logger.log("type2", agent="agentA", ticket="T2")
        logger.log("type2", agent="agentB", ticket="T2")
        
        # Filter by agent
        events = logger.get_events(agent="agentA")
        assert len(events) == 2
        assert all(e["agent"] == "agentA" for e in events)
        
        # Filter by type
        events = logger.get_events(event_type="type1")
        assert len(events) == 2
        assert all(e["type"] == "type1" for e in events)
        
        # Filter by ticket
        events = logger.get_events(ticket="T2")
        assert len(events) == 2
        assert all(e["ticket"] == "T2" for e in events)
        
        # Combined filter
        events = logger.get_events(agent="agentA", ticket="T1")
        assert len(events) == 1
        assert events[0]["agent"] == "agentA"
        assert events[0]["ticket"] == "T1"

    def test_log_rotation(self, logger):
        """Test log file rotation when size limit exceeded."""
        # Set small limit for testing
        logger.max_size_mb = 0.0001 # ~100 bytes
        
        # Write enough data to trigger rotation
        large_data = "x" * 200
        logger.log("event1", data=large_data)
        
        # This write should trigger rotation BEFORE writing
        logger.log("event2", data="short")
        
        # Check files
        assert logger.log_file.exists()
        backup = logger.log_file.with_suffix(".jsonl.1")
        assert backup.exists()
        
        # Check content
        with open(backup) as f:
            content = f.read()
            assert "event1" in content
            
        with open(logger.log_file) as f:
            content = f.read()
            assert "event2" in content

    def test_robustness(self, logger):
        """Test that logging failure doesn't crash app."""
        # Make file read-only to force write error
        with patch("builtins.open", side_effect=IOError("Disk full")):
            # Should not raise exception
            logger.log("test_event") 
