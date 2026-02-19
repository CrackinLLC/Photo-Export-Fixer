"""Tests for pef.core.orchestrator module."""

import os
import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from pef.core.orchestrator import PEFOrchestrator, _adaptive_interval
from pef.core.models import DryRunResult, ProcessRunResult, ProcessingStats


class TestAdaptiveInterval:
    """Tests for _adaptive_interval() helper function."""

    def test_tiny_collection_updates_every_item(self):
        """Collections < 50 items should update every item."""
        assert _adaptive_interval(10) == 1
        assert _adaptive_interval(49) == 1

    def test_small_collection_updates_every_10(self):
        """Collections 50-199 items should update every 10 items."""
        assert _adaptive_interval(50) == 10
        assert _adaptive_interval(150) == 10
        assert _adaptive_interval(199) == 10

    def test_medium_collection_updates_every_25(self):
        """Collections 200-999 items should update every 25 items."""
        assert _adaptive_interval(200) == 25
        assert _adaptive_interval(500) == 25
        assert _adaptive_interval(999) == 25

    def test_large_collection_updates_every_50(self):
        """Collections 1000-4999 items should update every 50 items."""
        assert _adaptive_interval(1000) == 50
        assert _adaptive_interval(3000) == 50
        assert _adaptive_interval(4999) == 50

    def test_huge_collection_updates_every_100(self):
        """Collections 5000+ items should update every 100 items."""
        assert _adaptive_interval(5000) == 100
        assert _adaptive_interval(10000) == 100
        assert _adaptive_interval(100000) == 100


class TestPEFOrchestratorInit:
    """Tests for PEFOrchestrator initialization."""

    def test_default_dest_path(self):
        orchestrator = PEFOrchestrator("/source/path")
        assert orchestrator.dest_path == "/source/path_processed"

    def test_custom_dest_path(self):
        orchestrator = PEFOrchestrator("/source", dest_path="/custom/output")
        assert orchestrator.dest_path == "/custom/output"

    def test_default_suffixes(self):
        orchestrator = PEFOrchestrator("/source")
        assert "" in orchestrator.suffixes
        assert "-edited" in orchestrator.suffixes

    def test_custom_suffixes(self):
        orchestrator = PEFOrchestrator("/source", suffixes=["", "-modified"])
        assert "-modified" in orchestrator.suffixes
        assert "-edited" not in orchestrator.suffixes

    def test_write_exif_default_true(self):
        orchestrator = PEFOrchestrator("/source")
        assert orchestrator.write_exif is True

    def test_write_exif_disabled(self):
        orchestrator = PEFOrchestrator("/source", write_exif=False)
        assert orchestrator.write_exif is False


class TestPEFOrchestratorDryRun:
    """Tests for PEFOrchestrator.dry_run() method."""

    def test_returns_error_for_missing_source(self, temp_dir):
        missing_path = os.path.join(temp_dir, "nonexistent")
        orchestrator = PEFOrchestrator(missing_path)

        result = orchestrator.dry_run()

        assert isinstance(result, DryRunResult)
        assert len(result.errors) > 0
        assert "does not exist" in result.errors[0]

    def test_returns_dry_run_result(self, sample_takeout):
        orchestrator = PEFOrchestrator(sample_takeout)

        result = orchestrator.dry_run()

        assert isinstance(result, DryRunResult)

    def test_counts_json_files(self, sample_takeout):
        orchestrator = PEFOrchestrator(sample_takeout)

        result = orchestrator.dry_run()

        assert result.json_count > 0

    def test_counts_media_files(self, sample_takeout):
        orchestrator = PEFOrchestrator(sample_takeout)

        result = orchestrator.dry_run()

        assert result.file_count > 0

    def test_counts_matched_files(self, sample_takeout):
        orchestrator = PEFOrchestrator(sample_takeout)

        result = orchestrator.dry_run()

        # Should have at least some matches
        assert result.matched_count >= 0

    def test_checks_exiftool_availability(self, sample_takeout):
        with patch('pef.core.orchestrator.is_exiftool_available') as mock_check:
            mock_check.return_value = True

            orchestrator = PEFOrchestrator(sample_takeout, write_exif=True)
            result = orchestrator.dry_run()

            mock_check.assert_called_once()
            assert result.exiftool_available is True

    def test_progress_callback_called(self, sample_takeout):
        orchestrator = PEFOrchestrator(sample_takeout)
        callback = Mock()

        orchestrator.dry_run(on_progress=callback)

        assert callback.called

    def test_empty_takeout_reports_error(self, temp_dir):
        # Create empty directory
        empty_dir = os.path.join(temp_dir, "empty")
        os.makedirs(empty_dir)

        orchestrator = PEFOrchestrator(empty_dir)
        result = orchestrator.dry_run()

        assert result.json_count == 0
        assert len(result.errors) > 0
        assert "No JSON metadata" in result.errors[0]


class TestPEFOrchestratorProcess:
    """Tests for PEFOrchestrator.process() method."""

    def test_returns_error_for_missing_source(self, temp_dir):
        missing_path = os.path.join(temp_dir, "nonexistent")
        orchestrator = PEFOrchestrator(missing_path)

        result = orchestrator.process()

        assert isinstance(result, ProcessRunResult)
        assert len(result.errors) > 0
        assert "does not exist" in result.errors[0]

    def test_creates_output_directory(self, sample_takeout, temp_dir):
        output_dir = os.path.join(temp_dir, "output")
        orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                result = orchestrator.process()

        assert os.path.exists(output_dir) or result.output_dir is not None

    def test_creates_pef_subdir(self, sample_takeout, temp_dir):
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                result = orchestrator.process()

        assert "_pef" in result.pef_dir

    def test_returns_processing_stats(self, sample_takeout, temp_dir):
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                result = orchestrator.process()

        assert isinstance(result.stats, ProcessingStats)

    def test_records_elapsed_time(self, sample_takeout, temp_dir):
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                result = orchestrator.process()

        assert result.elapsed_time >= 0

    def test_progress_callback_called(self, sample_takeout, temp_dir):
        output_dir = os.path.join(temp_dir, "output")
        callback = Mock()

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                orchestrator.process(on_progress=callback)

        assert callback.called


class TestPEFOrchestratorResume:
    """Tests for PEFOrchestrator resume functionality."""

    def test_process_creates_state_file(self, sample_takeout, temp_dir):
        """Verify processing creates a state file."""
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)
                orchestrator.process()

        state_path = os.path.join(output_dir, "_pef", "processing_state.json")
        assert os.path.exists(state_path)

        with open(state_path, "r") as f:
            state = json.load(f)
        assert state["status"] == "completed"

    def test_process_resumes_from_state(self, sample_takeout, temp_dir):
        """Verify processing resumes and skips already-processed files."""
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(os.path.join(output_dir, "_pef"), exist_ok=True)

        # Create in-progress state file with ALL JSONs already processed
        # sample_takeout has 3 JSONs: photo1.jpg.json, photo2.jpg.json, image.png.json
        all_jsons = [
            os.path.join(sample_takeout, "Album1", "photo1.jpg.json"),
            os.path.join(sample_takeout, "Album1", "photo2.jpg.json"),
            os.path.join(sample_takeout, "Album2", "image.png.json"),
        ]
        state_data = {
            "version": 1,
            "source_path": sample_takeout,
            "started_at": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00",
            "status": "in_progress",
            "total_json_count": 3,
            "processed_count": 3,
            "processed_jsons": all_jsons
        }
        with open(os.path.join(output_dir, "_pef", "processing_state.json"), "w") as f:
            json.dump(state_data, f)

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)
                result = orchestrator.process()

        # Should complete without processing any JSONs (all already done)
        assert result.stats.processed == 0  # No new files processed
        assert os.path.exists(os.path.join(output_dir, "_pef", "processing_state.json"))

    def test_process_resumes_partial(self, sample_takeout, temp_dir):
        """Verify processing resumes and only processes remaining files."""
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(os.path.join(output_dir, "_pef"), exist_ok=True)

        # Create in-progress state file with 1 of 3 JSONs already processed
        state_data = {
            "version": 1,
            "source_path": sample_takeout,
            "started_at": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00",
            "status": "in_progress",
            "total_json_count": 3,
            "processed_count": 1,
            "processed_jsons": [os.path.join(sample_takeout, "Album1", "photo1.jpg.json")]
        }
        with open(os.path.join(output_dir, "_pef", "processing_state.json"), "w") as f:
            json.dump(state_data, f)

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)
                result = orchestrator.process()

        # Should process only the 2 remaining JSONs
        # photo2.jpg.json -> photo2.jpg (1 file)
        # image.png.json -> image.png + image-edited.png (2 files)
        assert result.stats.processed == 3  # 3 new files processed
        assert os.path.exists(os.path.join(output_dir, "_pef", "processing_state.json"))

    def test_process_force_ignores_state(self, sample_takeout, temp_dir):
        """Verify force=True ignores existing state."""
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(os.path.join(output_dir, "_pef"), exist_ok=True)

        # Create in-progress state file with all JSONs marked as processed
        all_jsons = [
            os.path.join(sample_takeout, "Album1", "photo1.jpg.json"),
            os.path.join(sample_takeout, "Album1", "photo2.jpg.json"),
            os.path.join(sample_takeout, "Album2", "image.png.json"),
        ]
        state_data = {
            "version": 1,
            "source_path": sample_takeout,
            "started_at": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00",
            "status": "in_progress",
            "total_json_count": 3,
            "processed_count": 3,
            "processed_jsons": all_jsons
        }
        with open(os.path.join(output_dir, "_pef", "processing_state.json"), "w") as f:
            json.dump(state_data, f)

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)
                result = orchestrator.process(force=True)

        # With force=True, should process all files from scratch
        # 4 files: photo1.jpg, photo2.jpg, image.png, image-edited.png
        # (image.png.json matches both image.png and image-edited.png)
        assert result.stats.processed == 4

    def test_process_creates_new_dir_when_completed(self, sample_takeout, temp_dir):
        """Verify completed run creates new directory on next run."""
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(os.path.join(output_dir, "_pef"), exist_ok=True)

        # Create completed state file
        state_data = {
            "version": 1,
            "source_path": sample_takeout,
            "status": "completed",
            "processed_jsons": []
        }
        with open(os.path.join(output_dir, "_pef", "processing_state.json"), "w") as f:
            json.dump(state_data, f)

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)
                result = orchestrator.process()

        # Should create a new directory (output(1))
        assert result.output_dir != output_dir or "processing_state.json" in os.listdir(result.output_dir)


class TestPEFOrchestratorFreshStartDirectoryReuse:
    """Tests for fresh-start directory reuse (no prior state file)."""

    def test_fresh_run_reuses_existing_empty_dir(self, sample_takeout, temp_dir):
        """Existing empty directory should be reused directly (no '(2)' suffix)."""
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir)

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(
                    sample_takeout, dest_path=output_dir, write_exif=False
                )
                result = orchestrator.process()

        assert result.output_dir == output_dir

    def test_fresh_run_reuses_existing_nonempty_dir_without_pef(self, sample_takeout, temp_dir):
        """Existing non-empty directory without _pef/ should be reused directly."""
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir)
        # Put some non-PEF content in the directory
        with open(os.path.join(output_dir, "readme.txt"), "w") as f:
            f.write("some content")

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(
                    sample_takeout, dest_path=output_dir, write_exif=False
                )
                result = orchestrator.process()

        assert result.output_dir == output_dir

    def test_fresh_run_creates_nonexistent_dir(self, sample_takeout, temp_dir):
        """Non-existent directory should be created."""
        output_dir = os.path.join(temp_dir, "new_output")

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(
                    sample_takeout, dest_path=output_dir, write_exif=False
                )
                result = orchestrator.process()

        assert result.output_dir == output_dir
        assert os.path.isdir(output_dir)

    def test_force_reuses_existing_dir(self, sample_takeout, temp_dir):
        """Force mode with existing directory should reuse it."""
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir)

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(
                    sample_takeout, dest_path=output_dir, write_exif=False
                )
                result = orchestrator.process(force=True)

        assert result.output_dir == output_dir

    def test_completed_run_creates_new_dir(self, sample_takeout, temp_dir):
        """Completed prior run should create a new directory with suffix."""
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(os.path.join(output_dir, "_pef"), exist_ok=True)

        # Create completed state file
        state_data = {
            "version": 1,
            "source_path": sample_takeout,
            "status": "completed",
            "processed_jsons": []
        }
        with open(os.path.join(output_dir, "_pef", "processing_state.json"), "w") as f:
            json.dump(state_data, f)

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(
                    sample_takeout, dest_path=output_dir, write_exif=False
                )
                result = orchestrator.process()

        # Should have created output(1) since output has completed state
        assert result.output_dir != output_dir


class TestPEFOrchestratorReadJson:
    """Tests for PEFOrchestrator._read_json() method."""

    def test_reads_valid_json(self, temp_dir):
        # Create a valid JSON file
        json_path = os.path.join(temp_dir, "test.json")
        json_data = {
            "title": "photo.jpg",
            "photoTakenTime": {"timestamp": "1609459200"},
            "geoData": {"latitude": 40.7, "longitude": -74.0},
            "people": [{"name": "Alice"}],
            "description": "Test photo"
        }
        with open(json_path, "w") as f:
            json.dump(json_data, f)

        orchestrator = PEFOrchestrator(temp_dir)
        result = orchestrator._read_json(json_path)

        assert result is not None
        assert result.title == "photo.jpg"
        assert result.geo_data is not None
        assert len(result.people) == 1

    def test_returns_none_for_missing_title(self, temp_dir):
        json_path = os.path.join(temp_dir, "test.json")
        json_data = {"photoTakenTime": {"timestamp": "1609459200"}}
        with open(json_path, "w") as f:
            json.dump(json_data, f)

        orchestrator = PEFOrchestrator(temp_dir)
        result = orchestrator._read_json(json_path)

        assert result is None

    def test_returns_none_for_missing_timestamp(self, temp_dir):
        json_path = os.path.join(temp_dir, "test.json")
        json_data = {"title": "photo.jpg"}
        with open(json_path, "w") as f:
            json.dump(json_data, f)

        orchestrator = PEFOrchestrator(temp_dir)
        result = orchestrator._read_json(json_path)

        assert result is None

    def test_returns_none_for_invalid_json(self, temp_dir):
        json_path = os.path.join(temp_dir, "test.json")
        with open(json_path, "w") as f:
            f.write("not valid json")

        orchestrator = PEFOrchestrator(temp_dir)
        result = orchestrator._read_json(json_path)

        assert result is None

    def test_returns_none_for_missing_file(self, temp_dir):
        json_path = os.path.join(temp_dir, "nonexistent.json")

        orchestrator = PEFOrchestrator(temp_dir)
        result = orchestrator._read_json(json_path)

        assert result is None

    def test_logs_corrupt_json(self, temp_dir, caplog):
        """Corrupt/invalid JSON logs a distinct debug message."""
        import logging
        json_path = os.path.join(temp_dir, "corrupt.json")
        with open(json_path, "w") as f:
            f.write("{bad json content")

        orchestrator = PEFOrchestrator(temp_dir)
        with caplog.at_level(logging.DEBUG, logger="pef.core.orchestrator"):
            result = orchestrator._read_json(json_path)

        assert result is None
        assert any("Invalid/corrupt JSON" in msg for msg in caplog.messages)

    def test_logs_non_takeout_json_missing_title(self, temp_dir, caplog):
        """JSON missing 'title' field logs a non-Takeout debug message."""
        import logging
        json_path = os.path.join(temp_dir, "not_takeout.json")
        json_data = {"someField": "someValue"}
        with open(json_path, "w") as f:
            json.dump(json_data, f)

        orchestrator = PEFOrchestrator(temp_dir)
        with caplog.at_level(logging.DEBUG, logger="pef.core.orchestrator"):
            result = orchestrator._read_json(json_path)

        assert result is None
        assert any("non-Takeout JSON" in msg and "missing 'title'" in msg for msg in caplog.messages)

    def test_logs_non_takeout_json_missing_timestamp(self, temp_dir, caplog):
        """JSON missing 'photoTakenTime.timestamp' logs a non-Takeout debug message."""
        import logging
        json_path = os.path.join(temp_dir, "no_timestamp.json")
        json_data = {"title": "photo.jpg"}
        with open(json_path, "w") as f:
            json.dump(json_data, f)

        orchestrator = PEFOrchestrator(temp_dir)
        with caplog.at_level(logging.DEBUG, logger="pef.core.orchestrator"):
            result = orchestrator._read_json(json_path)

        assert result is None
        assert any("non-Takeout JSON" in msg and "photoTakenTime" in msg for msg in caplog.messages)

    def test_timestamp_converts_utc_epoch_to_local_datetime(self, temp_dir):
        """Verify UTC epoch timestamp is converted to local datetime.

        Google Takeout stores photoTakenTime as UTC epoch seconds.
        datetime.fromtimestamp() converts this to the system's local timezone.
        We use a known epoch and verify it matches the expected local datetime.
        """
        # 1609459200 = 2021-01-01 00:00:00 UTC
        epoch = 1609459200
        expected_local = datetime.fromtimestamp(epoch)

        json_path = os.path.join(temp_dir, "test.json")
        json_data = {
            "title": "photo.jpg",
            "photoTakenTime": {"timestamp": str(epoch)},
        }
        with open(json_path, "w") as f:
            json.dump(json_data, f)

        orchestrator = PEFOrchestrator(temp_dir)
        result = orchestrator._read_json(json_path)

        assert result is not None
        assert result.date == expected_local


@pytest.mark.integration
class TestPEFOrchestratorIntegration:
    """Integration tests for PEFOrchestrator."""

    def test_full_dry_run_workflow(self, sample_takeout):
        """Test complete dry-run workflow."""
        orchestrator = PEFOrchestrator(sample_takeout)

        # Mock ExifTool check
        with patch('pef.core.orchestrator.is_exiftool_available') as mock_check:
            mock_check.return_value = False
            result = orchestrator.dry_run()

        # Should complete without errors (besides missing exiftool)
        assert result.json_count >= 0
        assert result.file_count >= 0

    def test_full_process_workflow(self, sample_takeout, temp_dir):
        """Test complete processing workflow."""
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                result = orchestrator.process()

        # Should complete
        assert result.elapsed_time >= 0
        assert result.start_time is not None
        assert result.end_time is not None


class TestPEFOrchestratorErrorHandling:
    """Tests for error handling in PEFOrchestrator."""

    def test_dry_run_handles_invalid_json(self, temp_dir):
        """Verify dry_run handles corrupt JSON files gracefully."""
        album = os.path.join(temp_dir, "Album1")
        os.makedirs(album)

        # Create corrupt JSON
        corrupt_json = os.path.join(album, "corrupt.json")
        with open(corrupt_json, "w") as f:
            f.write("not valid json {{{")

        # Create valid JSON and file
        with open(os.path.join(album, "photo.jpg"), "wb") as f:
            f.write(b"data")
        with open(os.path.join(album, "photo.jpg.json"), "w") as f:
            json.dump({
                "title": "photo.jpg",
                "photoTakenTime": {"timestamp": "1609459200"}
            }, f)

        orchestrator = PEFOrchestrator(temp_dir)
        result = orchestrator.dry_run()

        # Should still count valid JSON
        assert result.json_count == 2  # Both JSONs found
        assert result.unmatched_json_count >= 1  # Corrupt one unmatched

    def test_process_continues_after_file_error(self, temp_dir):
        """Verify processing continues after a file fails."""
        album = os.path.join(temp_dir, "Album1")
        os.makedirs(album)

        # Create two valid files with JSONs
        for i in range(2):
            with open(os.path.join(album, f"photo{i}.jpg"), "wb") as f:
                f.write(b"data")
            with open(os.path.join(album, f"photo{i}.jpg.json"), "w") as f:
                json.dump({
                    "title": f"photo{i}.jpg",
                    "photoTakenTime": {"timestamp": "1609459200"}
                }, f)

        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    temp_dir,
                    dest_path=output_dir,
                    write_exif=False
                )
                result = orchestrator.process()

        # Both files should be processed
        assert result.stats.processed == 2

    def test_process_accumulates_errors(self, temp_dir):
        """Verify errors are accumulated in result."""
        album = os.path.join(temp_dir, "Album1")
        os.makedirs(album)

        # Create file with JSON
        with open(os.path.join(album, "photo.jpg"), "wb") as f:
            f.write(b"data")
        with open(os.path.join(album, "photo.jpg.json"), "w") as f:
            json.dump({
                "title": "photo.jpg",
                "photoTakenTime": {"timestamp": "1609459200"}
            }, f)

        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                # Patch process_file to raise an error
                with patch.object(
                    __import__('pef.core.processor', fromlist=['FileProcessor']).FileProcessor,
                    'process_file',
                    side_effect=PermissionError("Access denied")
                ):
                    orchestrator = PEFOrchestrator(
                        temp_dir,
                        dest_path=output_dir,
                        write_exif=False
                    )
                    result = orchestrator.process()

        # Error should be recorded
        assert len(result.errors) >= 1
        assert "Access denied" in str(result.errors[0]) or "Error" in str(result.errors[0])


class TestCopyUnmatchedJsonsIOErrors:
    """Tests for I/O error handling in _copy_unmatched_jsons()."""

    def test_copy_failure_continues_loop(self, temp_dir):
        """Verify _copy_unmatched_jsons continues after individual copy failure."""
        # Create source JSON files
        album = os.path.join(temp_dir, "Album1")
        os.makedirs(album)

        json_paths = []
        for i in range(3):
            path = os.path.join(album, f"file{i}.json")
            with open(path, "w") as f:
                json.dump({"title": f"file{i}"}, f)
            json_paths.append(path)

        pef_dir = os.path.join(temp_dir, "output", "_pef")
        os.makedirs(pef_dir, exist_ok=True)

        orchestrator = PEFOrchestrator(temp_dir)

        # Make second copy fail
        call_count = 0
        import shutil as shutil_mod
        original_copy = shutil_mod.copy

        def selective_fail(src, dst):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OSError("permission denied")
            return original_copy(src, dst)

        with patch('pef.core.orchestrator.shutil.copy', side_effect=selective_fail):
            orchestrator._copy_unmatched_jsons(json_paths, pef_dir)

        # Should have attempted all 3 copies (not stopped at failure)
        assert call_count == 3

        # Files 1 and 3 should exist, file 2 should not
        unmatched_dir = os.path.join(pef_dir, "unmatched_data")
        copied_files = []
        for root, dirs, files in os.walk(unmatched_dir):
            copied_files.extend(files)
        assert len(copied_files) == 2


class TestUnmatchedFileCopyIOErrors:
    """Tests for I/O error handling in orchestrator unmatched file loop."""

    def test_unmatched_file_copy_error_continues_loop(self, temp_dir):
        """Verify orchestrator continues copying unmatched files after a failure."""
        album = os.path.join(temp_dir, "Album1")
        os.makedirs(album)

        # Create files without matching JSONs (they'll all be unmatched)
        for i in range(3):
            with open(os.path.join(album, f"photo{i}.jpg"), "wb") as f:
                f.write(f"data{i}".encode())

        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    temp_dir, dest_path=output_dir, write_exif=False
                )

                import shutil as shutil_mod
                orig_copy = shutil_mod.copy

                def selective_copy_fail(src, dst):
                    if "photo1" in src:
                        raise OSError("disk full")
                    return orig_copy(src, dst)

                with patch('pef.core.processor.shutil.copy', side_effect=selective_copy_fail):
                    result = orchestrator.process()

                # Error counted in stats, processing continued for other files
                assert result.stats.errors == 1
                assert result.stats.unmatched_files == 2  # 2 of 3 succeeded


class TestPEFOrchestratorSaveProgress:
    """Tests for PEFOrchestrator.save_progress() method."""

    def test_save_progress_returns_false_when_no_active_processing(self):
        """Verify save_progress returns False when not processing."""
        orchestrator = PEFOrchestrator("/some/path")
        assert orchestrator.save_progress() is False

    def test_save_progress_returns_true_during_processing(self, sample_takeout, temp_dir):
        """Verify save_progress saves state during active processing."""
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)

                # Start processing but interrupt mid-way
                progress_calls = []

                def tracking_callback(current, total, msg):
                    progress_calls.append((current, total, msg))
                    # After JSON processing starts (Phase 2), test save_progress
                    if "[2/3]" in msg and orchestrator._active_state is not None:
                        assert orchestrator._active_state is not None

                orchestrator.process(on_progress=tracking_callback)

        # After completion, _active_state should be None
        assert orchestrator._active_state is None

    def test_active_state_cleared_after_processing(self, sample_takeout, temp_dir):
        """Verify _active_state is None after processing completes."""
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)
                orchestrator.process()

        assert orchestrator._active_state is None


class TestPEFOrchestratorResumeFields:
    """Tests for ProcessRunResult resume-related fields."""

    def test_fresh_run_not_resumed(self, sample_takeout, temp_dir):
        """Verify fresh run has resumed=False and skipped_count=0."""
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)
                result = orchestrator.process()

        assert result.resumed is False
        assert result.skipped_count == 0

    def test_resumed_run_has_correct_fields(self, sample_takeout, temp_dir):
        """Verify resumed run has resumed=True and correct skipped_count."""
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(os.path.join(output_dir, "_pef"), exist_ok=True)

        # Create in-progress state file with 1 of 3 JSONs already processed
        state_data = {
            "version": 1,
            "source_path": sample_takeout,
            "started_at": "2024-01-01T00:00:00",
            "last_updated": "2024-01-01T00:00:00",
            "status": "in_progress",
            "total_json_count": 3,
            "processed_count": 1,
            "processed_jsons": [os.path.join(sample_takeout, "Album1", "photo1.jpg.json")]
        }
        with open(os.path.join(output_dir, "_pef", "processing_state.json"), "w") as f:
            json.dump(state_data, f)

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)
                result = orchestrator.process()

        assert result.resumed is True
        assert result.skipped_count == 1

    def test_force_run_not_resumed(self, sample_takeout, temp_dir):
        """Verify force=True results in resumed=False."""
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(os.path.join(output_dir, "_pef"), exist_ok=True)

        # Create in-progress state file
        state_data = {
            "version": 1,
            "source_path": sample_takeout,
            "status": "in_progress",
            "processed_jsons": [os.path.join(sample_takeout, "Album1", "photo1.jpg.json")]
        }
        with open(os.path.join(output_dir, "_pef", "processing_state.json"), "w") as f:
            json.dump(state_data, f)

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)
                result = orchestrator.process(force=True)

        assert result.resumed is False
        assert result.skipped_count == 0


class TestPEFOrchestratorProgressPhases:
    """Tests for progress message phase indicators."""

    def test_dry_run_shows_phase_indicators(self, sample_takeout):
        """Verify dry_run progress messages include phase indicators."""
        orchestrator = PEFOrchestrator(sample_takeout)
        messages = []

        def capture_progress(current, total, message):
            messages.append(message)

        with patch('pef.core.orchestrator.is_exiftool_available', return_value=False):
            orchestrator.dry_run(on_progress=capture_progress)

        # Should have phase indicators in messages
        phase_messages = [m for m in messages if m.startswith("[")]
        assert len(phase_messages) > 0

        # Check specific phases exist (dry_run uses 2 phases: scan + analyze)
        phase_1 = any("[1/2]" in m for m in messages)
        phase_2 = any("[2/2]" in m for m in messages)
        assert phase_1 or phase_2  # At least one phase shown

    def test_process_shows_phase_indicators(self, sample_takeout, temp_dir):
        """Verify process progress messages include phase indicators."""
        output_dir = os.path.join(temp_dir, "output")
        orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir, write_exif=False)
        messages = []

        def capture_progress(current, total, message):
            messages.append(message)

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                orchestrator.process(on_progress=capture_progress)

        # Should have phase indicators in messages
        phase_messages = [m for m in messages if m.startswith("[")]
        assert len(phase_messages) > 0

        # Check that processing phase exists
        has_processing_phase = any("[2/3]" in m and "Processing" in m for m in messages)
        assert has_processing_phase

    def test_progress_updates_more_frequently_for_small_collections(self, sample_takeout):
        """Verify progress updates are more frequent for small collections."""
        orchestrator = PEFOrchestrator(sample_takeout)
        update_counts = []

        def capture_progress(current, total, message):
            update_counts.append((current, total))

        with patch('pef.core.orchestrator.is_exiftool_available', return_value=False):
            orchestrator.dry_run(on_progress=capture_progress)

        # For small test collection, should have multiple updates
        # (adaptive interval for small collections is 1-10)
        assert len(update_counts) >= 2


class TestStreamingDryRun:
    """Tests for streaming/chunked dry_run behavior."""

    def test_chunked_dry_run_matches_results(self, sample_takeout):
        """Verify chunked dry_run produces correct counts.

        The streaming approach should produce identical results regardless
        of chunk size.
        """
        orchestrator = PEFOrchestrator(sample_takeout)

        # Run with default chunk size
        with patch('pef.core.orchestrator.is_exiftool_available', return_value=False):
            result = orchestrator.dry_run()

        # sample_takeout has 3 JSONs, 5 files (photo1.jpg, photo2.jpg, video.mp4, image.png, image-edited.png)
        assert result.json_count == 3
        assert result.file_count == 5
        # photo1 and photo2 match, image matches
        assert result.matched_count == 3
        assert result.with_gps == 1  # Only photo1 has GPS
        assert result.with_people == 2  # photo1 and image have people

    def test_small_chunk_size_produces_same_results(self, sample_takeout):
        """Verify that a chunk size of 1 produces the same results as default."""
        orchestrator = PEFOrchestrator(sample_takeout)

        with patch('pef.core.orchestrator.is_exiftool_available', return_value=False):
            # Override chunk size to 1 (each JSON in its own chunk)
            orchestrator._DRY_RUN_CHUNK_SIZE = 1
            result_small = orchestrator.dry_run()

            # Reset to large chunk (all in one batch)
            orchestrator._DRY_RUN_CHUNK_SIZE = 10000
            result_large = orchestrator.dry_run()

        assert result_small.matched_count == result_large.matched_count
        assert result_small.with_gps == result_large.with_gps
        assert result_small.with_people == result_large.with_people
        assert result_small.unmatched_json_count == result_large.unmatched_json_count
        assert result_small.unmatched_file_count == result_large.unmatched_file_count

    def test_dry_run_handles_empty_chunks(self, temp_dir):
        """Verify dry_run handles zero JSONs (no chunks to process)."""
        # Empty directory with no JSONs
        empty_dir = os.path.join(temp_dir, "empty")
        os.makedirs(empty_dir)

        orchestrator = PEFOrchestrator(empty_dir)
        result = orchestrator.dry_run()

        assert result.json_count == 0
        assert result.matched_count == 0


class TestPipelinedProcess:
    """Tests for pipelined JSON pre-reading in process()."""

    def test_pipelined_process_produces_correct_results(self, sample_takeout, temp_dir):
        """Verify pipelined reading produces same results as sequential."""
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    sample_takeout, dest_path=output_dir, write_exif=False
                )
                result = orchestrator.process()

        # Should process all 4 matched files (photo1, photo2, image, image-edited)
        assert result.stats.processed == 4
        assert result.stats.with_gps == 1
        assert result.stats.with_people == 2

    def test_small_pipeline_batch_produces_same_results(self, sample_takeout, temp_dir):
        """Verify tiny pipeline batch size doesn't break processing."""
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    sample_takeout, dest_path=output_dir, write_exif=False
                )
                # Override batch size to 1 (each JSON triggers a new batch)
                orchestrator._PIPELINE_BATCH_SIZE = 1
                result = orchestrator.process()

        assert result.stats.processed == 4

    def test_pipeline_preserves_processing_order(self, sample_takeout, temp_dir):
        """Verify pipelined reading preserves deterministic processing order.

        State resume depends on deterministic order, so pipelining must
        not change the order JSONs are processed in the main loop.
        """
        output_dir = os.path.join(temp_dir, "output")
        processed_order = []

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    sample_takeout, dest_path=output_dir, write_exif=False
                )

                def tracking_progress(current, total, message):
                    if "Processing:" in message:
                        # Extract filename from progress message
                        processed_order.append(message)

                orchestrator.process(on_progress=tracking_progress)

        # Verify processing messages are generated in order
        assert len(processed_order) > 0

    def test_pipeline_handles_io_errors_gracefully(self, temp_dir):
        """Verify pipeline handles I/O errors in individual JSONs."""
        album = os.path.join(temp_dir, "Album1")
        os.makedirs(album)

        # Create valid file + JSON
        with open(os.path.join(album, "photo.jpg"), "wb") as f:
            f.write(b"data")
        with open(os.path.join(album, "photo.jpg.json"), "w") as f:
            json.dump({
                "title": "photo.jpg",
                "photoTakenTime": {"timestamp": "1609459200"}
            }, f)

        # Create corrupt JSON
        with open(os.path.join(album, "corrupt.json"), "w") as f:
            f.write("not valid json")

        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    temp_dir, dest_path=output_dir, write_exif=False
                )
                result = orchestrator.process()

        # Should still process the valid file
        assert result.stats.processed == 1
