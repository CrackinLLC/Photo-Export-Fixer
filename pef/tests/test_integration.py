"""Integration tests with real file operations.

These tests use actual file operations (not mocked) to verify the full
workflow works correctly end-to-end.
"""

import json
import os
import shutil

import pytest

from pef.core.orchestrator import PEFOrchestrator
from pef.core.scanner import FileScanner


@pytest.mark.integration
class TestFullWorkflow:
    """End-to-end workflow tests with real file operations."""

    def test_dry_run_then_process(self, sample_takeout, temp_dir):
        """Test complete dry-run followed by actual processing."""
        output_dir = os.path.join(temp_dir, "output")

        orchestrator = PEFOrchestrator(
            source_path=sample_takeout,
            dest_path=output_dir,
            write_exif=False  # Skip ExifTool to avoid external dependency
        )

        # First, dry run
        dry_result = orchestrator.dry_run()

        assert dry_result.json_count == 3  # photo1, photo2, image
        assert dry_result.file_count >= 3  # At least 3 media files
        assert dry_result.matched_count >= 2  # At least 2 matches
        assert not os.path.exists(output_dir)  # No files created yet

        # Now actual processing (need to re-create since dry_run doesn't modify)
        from unittest.mock import patch
        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                process_result = orchestrator.process()

        # Verify processing completed
        assert process_result.stats.processed >= 2
        assert os.path.exists(output_dir)
        assert os.path.exists(process_result.processed_dir)
        assert os.path.exists(process_result.log_file)

    def test_files_actually_copied(self, sample_takeout, temp_dir):
        """Verify files are actually copied to destination."""
        output_dir = os.path.join(temp_dir, "output")

        from unittest.mock import patch
        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    source_path=sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                orchestrator.process()

        # Check files exist in Processed folder
        processed_dir = os.path.join(output_dir, "Processed")

        # Verify Album1 files
        album1_dir = os.path.join(processed_dir, "Album1")
        assert os.path.exists(album1_dir)
        assert os.path.exists(os.path.join(album1_dir, "photo1.jpg"))
        assert os.path.exists(os.path.join(album1_dir, "photo2.jpg"))

        # Verify Album2 files
        album2_dir = os.path.join(processed_dir, "Album2")
        assert os.path.exists(album2_dir)
        assert os.path.exists(os.path.join(album2_dir, "image.png"))

        # Verify file contents match source
        with open(os.path.join(sample_takeout, "Album1", "photo1.jpg"), "rb") as f:
            source_content = f.read()
        with open(os.path.join(album1_dir, "photo1.jpg"), "rb") as f:
            dest_content = f.read()
        assert source_content == dest_content

    def test_unmatched_files_copied_to_unprocessed(self, sample_takeout, temp_dir):
        """Verify unmatched files go to Unprocessed folder."""
        output_dir = os.path.join(temp_dir, "output")

        from unittest.mock import patch
        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    source_path=sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                result = orchestrator.process()

        # sample_takeout has video.mp4 without JSON
        unprocessed_dir = os.path.join(output_dir, "Unprocessed")
        if result.stats.unmatched_files > 0:
            assert os.path.exists(unprocessed_dir)
            # video.mp4 should be in Unprocessed
            assert os.path.exists(os.path.join(unprocessed_dir, "video.mp4"))

    def test_logs_created(self, sample_takeout, temp_dir):
        """Verify log files are created with content."""
        output_dir = os.path.join(temp_dir, "output")

        from unittest.mock import patch
        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    source_path=sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                result = orchestrator.process()

        # Check summary log exists and has content
        assert os.path.exists(result.log_file)
        with open(result.log_file, "r", encoding="utf-8") as f:
            log_content = f.read()
        assert "Processed:" in log_content
        assert "seconds" in log_content.lower()

        # Check detailed log exists
        detailed_log = os.path.join(output_dir, "detailed_logs.txt")
        assert os.path.exists(detailed_log)

    def test_state_file_created(self, sample_takeout, temp_dir):
        """Verify processing state file is created."""
        output_dir = os.path.join(temp_dir, "output")

        from unittest.mock import patch
        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    source_path=sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                orchestrator.process()

        # Verify state file exists and is valid JSON
        state_file = os.path.join(output_dir, "processing_state.json")
        assert os.path.exists(state_file)

        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)

        assert state["status"] == "completed"
        assert state["source_path"] == sample_takeout
        assert "processed_jsons" in state


@pytest.mark.integration
class TestResumeWorkflow:
    """Integration tests for resume functionality."""

    def test_resume_skips_processed_files(self, sample_takeout, temp_dir):
        """Verify resume skips already-processed files."""
        output_dir = os.path.join(temp_dir, "output")

        from unittest.mock import patch

        # First run - process everything
        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    source_path=sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                result1 = orchestrator.process()

        first_run_count = result1.stats.processed

        # Manually set state back to in_progress to simulate interruption
        state_file = os.path.join(output_dir, "processing_state.json")
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        state["status"] = "in_progress"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f)

        # Second run - should resume and skip already processed
        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator2 = PEFOrchestrator(
                    source_path=sample_takeout,
                    dest_path=output_dir,
                    write_exif=False
                )
                result2 = orchestrator2.process()

        # Should have resumed and skipped the already-processed files
        assert result2.resumed is True
        assert result2.skipped_count == first_run_count
        assert result2.stats.processed == 0  # Nothing new to process


@pytest.mark.integration
class TestEdgeCases:
    """Integration tests for edge cases."""

    def test_handles_duplicate_filenames(self, sample_duplicates, temp_dir):
        """Verify duplicate files are handled correctly."""
        output_dir = os.path.join(temp_dir, "output")

        from unittest.mock import patch
        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    source_path=sample_duplicates,
                    dest_path=output_dir,
                    write_exif=False
                )
                result = orchestrator.process()

        # Should process all 3 photos (original + 2 duplicates)
        assert result.stats.processed >= 3

        # Check all files were copied
        processed_dir = os.path.join(output_dir, "Processed", "Album")
        assert os.path.exists(os.path.join(processed_dir, "photo.jpg"))
        assert os.path.exists(os.path.join(processed_dir, "photo(1).jpg"))
        assert os.path.exists(os.path.join(processed_dir, "photo(2).jpg"))

    def test_handles_long_filenames(self, sample_long_filename, temp_dir):
        """Verify long filenames (51-char truncation) are handled."""
        output_dir = os.path.join(temp_dir, "output")

        from unittest.mock import patch
        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager'):
                orchestrator = PEFOrchestrator(
                    source_path=sample_long_filename,
                    dest_path=output_dir,
                    write_exif=False
                )
                result = orchestrator.process()

        # Should process the truncated file
        assert result.stats.processed >= 1

    def test_handles_empty_directory(self, temp_dir):
        """Verify empty directory is handled gracefully."""
        empty_source = os.path.join(temp_dir, "empty")
        os.makedirs(empty_source)
        output_dir = os.path.join(temp_dir, "output")

        orchestrator = PEFOrchestrator(
            source_path=empty_source,
            dest_path=output_dir,
            write_exif=False
        )
        result = orchestrator.dry_run()

        assert result.json_count == 0
        assert result.file_count == 0
        assert len(result.errors) > 0  # Should report no JSON files found


@pytest.mark.integration
class TestScannerIntegration:
    """Integration tests for FileScanner."""

    def test_iter_jsons_yields_all_paths(self, sample_takeout):
        """Verify iter_jsons yields all JSON paths."""
        scanner = FileScanner(sample_takeout)

        json_paths = list(scanner.iter_jsons())

        assert len(json_paths) == 3  # photo1, photo2, image
        assert all(p.endswith(".json") for p in json_paths)

    def test_iter_jsons_matches_scan(self, sample_takeout):
        """Verify iter_jsons finds same files as scan()."""
        scanner = FileScanner(sample_takeout)

        iter_paths = set(scanner.iter_jsons())

        scanner.scan()
        scan_paths = set(scanner.jsons)

        assert iter_paths == scan_paths
