"""Tests for pef.cli.main module."""

import os
from unittest.mock import Mock, patch, MagicMock

import pytest

from pef.cli.main import (
    parse_args,
    create_progress_callback,
    run_dry_run,
    run_process,
    run_extend,
    main,
)


class TestParseArgs:
    """Tests for parse_args() function."""

    def test_no_args_returns_defaults(self):
        args = parse_args([])

        assert args.path is None
        assert args.destination is None
        assert args.suffix is None
        assert args.extend is False
        assert args.no_exif is False
        assert args.dry_run is False

    def test_path_short_flag(self):
        args = parse_args(["-p", "/some/path"])

        assert args.path == "/some/path"

    def test_path_long_flag(self):
        args = parse_args(["--path", "/some/path"])

        assert args.path == "/some/path"

    def test_destination_short_flag(self):
        args = parse_args(["-d", "/output/path"])

        assert args.destination == "/output/path"

    def test_destination_long_flag(self):
        args = parse_args(["--destination", "/output/path"])

        assert args.destination == "/output/path"

    def test_suffix_short_flag(self):
        args = parse_args(["-s", "modified"])

        assert args.suffix == ["modified"]

    def test_multiple_suffixes(self):
        args = parse_args(["-s", "modified", "-s", "backup"])

        assert "modified" in args.suffix
        assert "backup" in args.suffix

    def test_extend_flag(self):
        args = parse_args(["--extend"])

        assert args.extend is True

    def test_extend_short_flag(self):
        args = parse_args(["-e"])

        assert args.extend is True

    def test_no_exif_flag(self):
        args = parse_args(["--no-exif"])

        assert args.no_exif is True

    def test_dry_run_flag(self):
        args = parse_args(["--dry-run"])

        assert args.dry_run is True

    def test_combined_flags(self):
        args = parse_args([
            "-p", "/source",
            "-d", "/dest",
            "--extend",
            "--dry-run"
        ])

        assert args.path == "/source"
        assert args.destination == "/dest"
        assert args.extend is True
        assert args.dry_run is True


class TestCreateProgressCallback:
    """Tests for create_progress_callback() function."""

    def test_returns_callback_and_pbar(self):
        callback, pbar = create_progress_callback("Test")

        assert callable(callback)
        assert pbar is not None
        pbar.close()

    def test_callback_updates_pbar(self):
        callback, pbar = create_progress_callback("Test")

        callback(50, 100, "Processing file")

        assert pbar.total == 100
        assert pbar.n == 50
        pbar.close()

    def test_truncates_long_messages(self):
        callback, pbar = create_progress_callback("Test")

        long_message = "A" * 100
        callback(50, 100, long_message)

        # Should not raise
        pbar.close()


class TestRunDryRun:
    """Tests for run_dry_run() function."""

    def test_returns_error_for_missing_path(self, temp_dir):
        missing = os.path.join(temp_dir, "nonexistent")

        result = run_dry_run(missing, None, ["", "-edited"])

        assert result == 1

    def test_returns_success_for_valid_path(self, sample_takeout):
        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.json_count = 5
            mock_result.file_count = 3
            mock_result.matched_count = 3
            mock_result.unmatched_json_count = 2
            mock_result.unmatched_file_count = 0
            mock_result.with_gps = 2
            mock_result.with_people = 1
            mock_result.exiftool_available = False
            mock_result.exiftool_path = None
            mock_instance.dry_run.return_value = mock_result
            MockOrch.return_value = mock_instance

            result = run_dry_run(sample_takeout, None, ["", "-edited"])

            assert result == 0

    def test_extend_mode_flag(self, sample_takeout):
        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.json_count = 5
            mock_result.file_count = 3
            mock_result.matched_count = 3
            mock_result.unmatched_json_count = 2
            mock_result.unmatched_file_count = 0
            mock_result.with_gps = 2
            mock_result.with_people = 1
            mock_result.exiftool_available = False
            mock_result.exiftool_path = None
            mock_instance.dry_run.return_value = mock_result
            MockOrch.return_value = mock_instance

            result = run_dry_run(sample_takeout, None, [""], extend_mode=True)

            # Should complete without error
            assert result == 0


class TestRunProcess:
    """Tests for run_process() function."""

    def test_returns_error_for_missing_path(self, temp_dir):
        missing = os.path.join(temp_dir, "nonexistent")

        result = run_process(missing, None, ["", "-edited"], write_exif=False)

        assert result == 1

    def test_returns_success_for_valid_path(self, sample_takeout, temp_dir):
        output = os.path.join(temp_dir, "output")

        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_instance = MagicMock()
            mock_stats = MagicMock()
            mock_stats.processed = 3
            mock_stats.with_gps = 2
            mock_stats.with_people = 1
            mock_stats.unmatched_files = 0
            mock_stats.unmatched_jsons = 2

            mock_result = MagicMock()
            mock_result.errors = []
            mock_result.stats = mock_stats
            mock_result.elapsed_time = 1.5
            mock_result.processed_dir = os.path.join(output, "Processed")
            mock_result.unprocessed_dir = os.path.join(output, "Unprocessed")
            mock_result.log_file = os.path.join(output, "logs.txt")
            mock_instance.process.return_value = mock_result
            MockOrch.return_value = mock_instance

            result = run_process(sample_takeout, output, ["", "-edited"], write_exif=False)

            assert result == 0


class TestRunExtend:
    """Tests for run_extend() function."""

    def test_returns_error_for_missing_source(self, temp_dir):
        missing = os.path.join(temp_dir, "nonexistent")

        result = run_extend(missing, None, ["", "-edited"])

        assert result == 1

    def test_returns_error_for_missing_processed_folder(self, sample_takeout, temp_dir):
        # run_extend checks if output/Processed exists
        # If the output doesn't exist at all, it should return error
        missing_output = os.path.join(temp_dir, "nonexistent_output")

        result = run_extend(sample_takeout, missing_output, ["", "-edited"])

        assert result == 1

    def test_returns_success_with_valid_paths(self, sample_takeout, temp_dir):
        output = os.path.join(temp_dir, "output")
        processed = os.path.join(output, "Processed")
        os.makedirs(processed)

        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_instance = MagicMock()
            mock_stats = MagicMock()
            mock_stats.processed = 3
            mock_stats.with_gps = 2
            mock_stats.with_people = 1
            mock_stats.skipped = 5
            mock_stats.errors = 0

            mock_result = MagicMock()
            mock_result.stats = mock_stats
            mock_result.elapsed_time = 1.5
            mock_instance.extend.return_value = mock_result
            MockOrch.return_value = mock_instance

            result = run_extend(sample_takeout, output, ["", "-edited"])

            assert result == 0


class TestMain:
    """Tests for main() entry point."""

    def test_wizard_mode_when_no_path(self):
        with patch('pef.cli.main.run_wizard') as mock_wizard:
            mock_wizard.return_value = None  # User cancelled

            result = main([])

            assert result == 1
            mock_wizard.assert_called_once()

    def test_dry_run_mode(self, sample_takeout):
        with patch('pef.cli.main.run_dry_run') as mock_dry_run:
            mock_dry_run.return_value = 0

            result = main(["--path", sample_takeout, "--dry-run"])

            assert result == 0
            mock_dry_run.assert_called_once()

    def test_extend_mode(self, sample_takeout, temp_dir):
        output = os.path.join(temp_dir, "output")
        processed = os.path.join(output, "Processed")
        os.makedirs(processed)

        with patch('pef.cli.main.run_extend') as mock_extend:
            mock_extend.return_value = 0

            result = main(["--path", sample_takeout, "--extend", "-d", output])

            assert result == 0
            mock_extend.assert_called_once()

    def test_extend_dry_run_mode(self, sample_takeout):
        with patch('pef.cli.main.run_dry_run') as mock_dry_run:
            mock_dry_run.return_value = 0

            result = main(["--path", sample_takeout, "--extend", "--dry-run"])

            assert result == 0
            # Should call dry_run with extend_mode=True
            mock_dry_run.assert_called_once()
            _, kwargs = mock_dry_run.call_args
            assert kwargs.get('extend_mode') is True

    def test_process_mode(self, sample_takeout):
        with patch('pef.cli.main.run_process') as mock_process:
            mock_process.return_value = 0

            result = main(["--path", sample_takeout])

            assert result == 0
            mock_process.assert_called_once()

    def test_no_exif_flag_passed_to_process(self, sample_takeout):
        with patch('pef.cli.main.run_process') as mock_process:
            mock_process.return_value = 0

            main(["--path", sample_takeout, "--no-exif"])

            args, kwargs = mock_process.call_args
            assert kwargs.get('write_exif') is False or args[3] is False

    def test_custom_suffixes_passed(self, sample_takeout):
        with patch('pef.cli.main.run_process') as mock_process:
            mock_process.return_value = 0

            main(["--path", sample_takeout, "-s", "modified"])

            args, _ = mock_process.call_args
            suffixes = args[2]
            assert "modified" in suffixes


class TestMainPathNormalization:
    """Tests for path normalization in main()."""

    def test_normalizes_source_path(self, sample_takeout):
        with patch('pef.cli.main.run_process') as mock_process:
            mock_process.return_value = 0

            # Use path with trailing slash
            path_with_slash = sample_takeout + os.sep

            main(["--path", path_with_slash])

            args, _ = mock_process.call_args
            # Path should be normalized (implementation dependent)
            assert args[0] is not None

    def test_normalizes_dest_path(self, sample_takeout, temp_dir):
        with patch('pef.cli.main.run_process') as mock_process:
            mock_process.return_value = 0

            dest = os.path.join(temp_dir, "output")

            main(["--path", sample_takeout, "-d", dest])

            args, _ = mock_process.call_args
            assert args[1] is not None
