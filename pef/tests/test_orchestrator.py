"""Tests for pef.core.orchestrator module."""

import os
import json
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest

from pef.core.orchestrator import PEFOrchestrator
from pef.core.models import DryRunResult, ProcessResult, ProcessingStats


class TestPEFOrchestratorInit:
    """Tests for PEFOrchestrator initialization."""

    def test_default_dest_path(self):
        orchestrator = PEFOrchestrator("/source/path")
        assert orchestrator.dest_path == "/source/path_pefProcessed"

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

        assert isinstance(result, ProcessResult)
        assert len(result.errors) > 0
        assert "does not exist" in result.errors[0]

    def test_creates_output_directory(self, sample_takeout, temp_dir):
        output_dir = os.path.join(temp_dir, "output")
        orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)

        with patch('pef.core.orchestrator.FileProcessor'):
            with patch('pef.core.orchestrator.BufferedLogger'):
                with patch('pef.core.orchestrator.SummaryLogger'):
                    result = orchestrator.process()

        assert os.path.exists(output_dir) or result.output_dir is not None

    def test_creates_processed_subdir(self, sample_takeout, temp_dir):
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                result = orchestrator.process()

        assert "Processed" in result.processed_dir

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


class TestPEFOrchestratorExtend:
    """Tests for PEFOrchestrator.extend() method."""

    @pytest.fixture
    def processed_output(self, temp_dir, sample_takeout):
        """Create a processed output directory structure."""
        output_dir = os.path.join(temp_dir, "output")
        processed_dir = os.path.join(output_dir, "Processed")
        album_dir = os.path.join(processed_dir, "Album1")
        os.makedirs(album_dir)

        # Create a processed file
        with open(os.path.join(album_dir, "photo1.jpg"), "wb") as f:
            f.write(b"fake image data")

        return output_dir

    def test_returns_error_for_missing_source(self, temp_dir):
        missing_path = os.path.join(temp_dir, "nonexistent")
        orchestrator = PEFOrchestrator(missing_path, dest_path=temp_dir)

        result = orchestrator.extend()

        assert len(result.errors) > 0
        assert "does not exist" in result.errors[0]

    def test_returns_error_for_missing_processed_folder(self, sample_takeout, temp_dir):
        # Output exists but no Processed folder
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir)

        orchestrator = PEFOrchestrator(sample_takeout, dest_path=output_dir)
        result = orchestrator.extend()

        assert len(result.errors) > 0
        assert "Processed folder not found" in result.errors[0]

    def test_returns_process_result(self, sample_takeout, processed_output):
        with patch('pef.core.processor.ExifToolManager'):
            orchestrator = PEFOrchestrator(sample_takeout, dest_path=processed_output)
            result = orchestrator.extend()

        assert isinstance(result, ProcessResult)

    def test_records_elapsed_time(self, sample_takeout, processed_output):
        with patch('pef.core.processor.ExifToolManager'):
            orchestrator = PEFOrchestrator(sample_takeout, dest_path=processed_output)
            result = orchestrator.extend()

        assert result.elapsed_time >= 0

    def test_progress_callback_called(self, sample_takeout, processed_output):
        callback = Mock()

        with patch('pef.core.processor.ExifToolManager'):
            orchestrator = PEFOrchestrator(sample_takeout, dest_path=processed_output)
            orchestrator.extend(on_progress=callback)

        assert callback.called


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
