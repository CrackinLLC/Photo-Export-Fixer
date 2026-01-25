"""Tests for pef.core.state module."""

import json
import os


from pef.core.state import StateManager


class TestStateManagerBasics:
    """Tests for StateManager basic functionality."""

    def test_initial_state(self, temp_dir):
        """Verify initial state values."""
        state = StateManager(temp_dir)

        assert state.processed_count == 0
        assert state.source_path == ""
        assert state.status == "pending"

    def test_can_resume_false_when_no_file(self, temp_dir):
        """Verify can_resume returns False when no state file exists."""
        state = StateManager(temp_dir)
        assert state.can_resume() is False

    def test_is_completed_false_when_no_file(self, temp_dir):
        """Verify is_completed returns False when no state file exists."""
        state = StateManager(temp_dir)
        assert state.is_completed() is False


class TestStateManagerCreate:
    """Tests for StateManager.create()."""

    def test_create_sets_properties(self, temp_dir):
        """Verify create sets internal properties correctly."""
        state = StateManager(temp_dir)
        state.create("/path/to/source", 100)

        assert state.source_path == "/path/to/source"
        assert state.total_count == 100
        assert state.status == "in_progress"
        assert state.processed_count == 0

    def test_create_writes_state_file(self, temp_dir):
        """Verify create writes a state file."""
        state = StateManager(temp_dir)
        state.create("/path/to/source", 100)

        assert os.path.exists(state.state_path)

        with open(state.state_path, "r") as f:
            saved = json.load(f)

        assert saved["version"] == 1
        assert saved["source_path"] == "/path/to/source"
        assert saved["total_json_count"] == 100
        assert saved["status"] == "in_progress"
        assert saved["processed_count"] == 0
        assert saved["processed_jsons"] == []

    def test_create_can_resume_after(self, temp_dir):
        """Verify can_resume returns True after create."""
        state = StateManager(temp_dir)
        state.create("/path/to/source", 100)

        # Create new manager to simulate restart
        state2 = StateManager(temp_dir)
        assert state2.can_resume() is True


class TestStateManagerLoad:
    """Tests for StateManager.load()."""

    def test_load_restores_state(self, temp_dir):
        """Verify load restores state from file."""
        # Create state
        state1 = StateManager(temp_dir)
        state1.create("/path/to/source", 100)
        state1.mark_processed("/path/file1.json")
        state1.mark_processed("/path/file2.json")
        state1.save()

        # Load in new manager
        state2 = StateManager(temp_dir)
        result = state2.load()

        assert result is True
        assert state2.source_path == "/path/to/source"
        assert state2.total_count == 100
        assert state2.processed_count == 2
        assert state2.is_processed("/path/file1.json")
        assert state2.is_processed("/path/file2.json")

    def test_load_returns_false_when_no_file(self, temp_dir):
        """Verify load returns False when no state file exists."""
        state = StateManager(temp_dir)
        assert state.load() is False

    def test_load_handles_corrupted_file(self, temp_dir):
        """Verify load handles corrupted state file gracefully."""
        state = StateManager(temp_dir)

        # Write corrupted file
        os.makedirs(temp_dir, exist_ok=True)
        with open(state.state_path, "w") as f:
            f.write("not valid json {{{")

        result = state.load()
        assert result is False


class TestStateManagerMarkProcessed:
    """Tests for StateManager.mark_processed()."""

    def test_mark_processed_adds_to_set(self, temp_dir):
        """Verify mark_processed adds JSON to processed set."""
        state = StateManager(temp_dir)
        state.create("/source", 10)

        state.mark_processed("/source/file1.json")

        assert state.is_processed("/source/file1.json")
        assert state.processed_count == 1

    def test_mark_processed_multiple(self, temp_dir):
        """Verify marking multiple files works correctly."""
        state = StateManager(temp_dir)
        state.create("/source", 10)

        state.mark_processed("/source/file1.json")
        state.mark_processed("/source/file2.json")
        state.mark_processed("/source/file3.json")

        assert state.processed_count == 3
        assert state.is_processed("/source/file1.json")
        assert state.is_processed("/source/file2.json")
        assert state.is_processed("/source/file3.json")

    def test_mark_processed_idempotent(self, temp_dir):
        """Verify marking same file twice doesn't double count."""
        state = StateManager(temp_dir)
        state.create("/source", 10)

        state.mark_processed("/source/file1.json")
        state.mark_processed("/source/file1.json")

        assert state.processed_count == 1

    def test_auto_save_at_interval(self, temp_dir):
        """Verify state auto-saves after SAVE_INTERVAL files."""
        state = StateManager(temp_dir)
        state.create("/source", 200)

        # Mark files up to just before interval
        for i in range(StateManager.SAVE_INTERVAL - 1):
            state.mark_processed(f"/source/file{i}.json")

        # Check file hasn't been updated since create
        with open(state.state_path, "r") as f:
            saved = json.load(f)
        assert saved["processed_count"] == 0  # Only create was saved

        # Mark one more to trigger auto-save
        state.mark_processed(f"/source/file{StateManager.SAVE_INTERVAL}.json")

        # Now file should be updated
        with open(state.state_path, "r") as f:
            saved = json.load(f)
        assert saved["processed_count"] == StateManager.SAVE_INTERVAL


class TestStateManagerFilterUnprocessed:
    """Tests for StateManager.filter_unprocessed()."""

    def test_filter_removes_processed(self, temp_dir):
        """Verify filter_unprocessed removes processed items."""
        state = StateManager(temp_dir)
        state.create("/source", 5)

        state.mark_processed("/source/file1.json")
        state.mark_processed("/source/file3.json")

        all_jsons = [
            "/source/file1.json",
            "/source/file2.json",
            "/source/file3.json",
            "/source/file4.json",
            "/source/file5.json",
        ]

        result = state.filter_unprocessed(all_jsons)

        assert len(result) == 3
        assert "/source/file2.json" in result
        assert "/source/file4.json" in result
        assert "/source/file5.json" in result
        assert "/source/file1.json" not in result
        assert "/source/file3.json" not in result

    def test_filter_preserves_order(self, temp_dir):
        """Verify filter_unprocessed preserves original order."""
        state = StateManager(temp_dir)
        state.create("/source", 5)

        state.mark_processed("/source/file2.json")

        all_jsons = [
            "/source/file1.json",
            "/source/file2.json",
            "/source/file3.json",
        ]

        result = state.filter_unprocessed(all_jsons)

        assert result == ["/source/file1.json", "/source/file3.json"]

    def test_filter_empty_when_all_processed(self, temp_dir):
        """Verify filter returns empty list when all processed."""
        state = StateManager(temp_dir)
        state.create("/source", 2)

        state.mark_processed("/source/file1.json")
        state.mark_processed("/source/file2.json")

        all_jsons = ["/source/file1.json", "/source/file2.json"]
        result = state.filter_unprocessed(all_jsons)

        assert result == []


class TestStateManagerComplete:
    """Tests for StateManager.complete()."""

    def test_complete_sets_status(self, temp_dir):
        """Verify complete sets status to completed."""
        state = StateManager(temp_dir)
        state.create("/source", 10)
        state.complete()

        assert state.status == "completed"

    def test_complete_saves_state(self, temp_dir):
        """Verify complete saves state to file."""
        state = StateManager(temp_dir)
        state.create("/source", 10)
        state.mark_processed("/source/file1.json")
        state.complete()

        with open(state.state_path, "r") as f:
            saved = json.load(f)

        assert saved["status"] == "completed"
        assert saved["processed_count"] == 1

    def test_can_resume_false_after_complete(self, temp_dir):
        """Verify can_resume returns False after complete."""
        state = StateManager(temp_dir)
        state.create("/source", 10)
        state.complete()

        state2 = StateManager(temp_dir)
        assert state2.can_resume() is False

    def test_is_completed_true_after_complete(self, temp_dir):
        """Verify is_completed returns True after complete."""
        state = StateManager(temp_dir)
        state.create("/source", 10)
        state.complete()

        state2 = StateManager(temp_dir)
        assert state2.is_completed() is True


class TestStateManagerResumeScenarios:
    """Tests for full resume scenarios."""

    def test_full_resume_workflow(self, temp_dir):
        """Test complete resume workflow."""
        # First run - process some files
        state1 = StateManager(temp_dir)
        state1.create("/source", 5)
        state1.mark_processed("/source/file1.json")
        state1.mark_processed("/source/file2.json")
        state1.save()  # Simulate crash - not complete

        # Second run - resume
        state2 = StateManager(temp_dir)
        assert state2.can_resume() is True

        state2.load()
        assert state2.processed_count == 2

        all_jsons = [f"/source/file{i}.json" for i in range(1, 6)]
        remaining = state2.filter_unprocessed(all_jsons)

        assert len(remaining) == 3
        assert "/source/file3.json" in remaining
        assert "/source/file4.json" in remaining
        assert "/source/file5.json" in remaining

        # Complete remaining
        for path in remaining:
            state2.mark_processed(path)
        state2.complete()

        # Verify final state
        state3 = StateManager(temp_dir)
        assert state3.can_resume() is False
        assert state3.is_completed() is True

    def test_fresh_start_ignores_completed(self, temp_dir):
        """Verify that force=True behavior can ignore completed state."""
        # Complete a run
        state1 = StateManager(temp_dir)
        state1.create("/source", 5)
        state1.complete()

        # Fresh start would call create() again
        state2 = StateManager(temp_dir)
        state2.create("/source", 10)  # Different count

        assert state2.status == "in_progress"
        assert state2.total_count == 10
        assert state2.processed_count == 0
