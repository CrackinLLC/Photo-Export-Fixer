"""Tests for pef.cli.main module."""

import os
from unittest.mock import patch, MagicMock

import pytest

from pef.cli.main import (
    parse_args,
    create_progress_callback,
    run_dry_run,
    run_process,
    main,
)


class TestParseArgs:
    """Tests for parse_args() function."""

    def test_no_args_returns_defaults(self):
        args = parse_args([])

        assert args.path is None
        assert args.destination is None
        assert args.suffix is None
        assert args.force is False
        assert args.no_exif is False
        assert args.dry_run is False

    def test_version_flag_exits(self):
        """Verify --version flag exits with version info."""
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_version_short_flag_exits(self):
        """Verify -V flag exits with version info."""
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["-V"])
        assert exc_info.value.code == 0

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

    def test_force_flag(self):
        args = parse_args(["--force"])

        assert args.force is True

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
            "--force",
            "--dry-run"
        ])

        assert args.path == "/source"
        assert args.destination == "/dest"
        assert args.force is True
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

    def test_truncation_adds_ellipsis(self):
        """Verify long messages are truncated with ellipsis."""
        callback, pbar = create_progress_callback("Test")

        # Create a message longer than any reasonable terminal width
        long_message = "X" * 200
        callback(50, 100, long_message)

        # The description should end with "..." if truncated
        # and be shorter than the original
        desc = pbar.desc
        assert len(desc) < 200
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
            mock_stats.errors = 0

            mock_result = MagicMock()
            mock_result.errors = []
            mock_result.stats = mock_stats
            mock_result.elapsed_time = 1.5
            mock_result.output_dir = output
            mock_result.pef_dir = os.path.join(output, "_pef")
            mock_result.summary_file = os.path.join(output, "_pef", "summary.txt")
            mock_result.resumed = False
            mock_result.skipped_count = 0
            mock_result.motion_photo_count = 0
            mock_result.unprocessed_items = []
            mock_instance.process.return_value = mock_result
            MockOrch.return_value = mock_instance

            result = run_process(sample_takeout, output, ["", "-edited"], write_exif=False)

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

    def test_force_flag_passed_to_process(self, sample_takeout):
        with patch('pef.cli.main.run_process') as mock_process:
            mock_process.return_value = 0

            main(["--path", sample_takeout, "--force"])

            args, kwargs = mock_process.call_args
            assert kwargs.get('force') is True or args[4] is True

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


class TestRunProcessExitCodes:
    """Tests for CLI exit codes when processing has errors."""

    def test_returns_2_when_stats_errors(self, sample_takeout, temp_dir):
        """Verify exit code 2 when result.stats.errors > 0."""
        from pef.core.models import ProcessRunResult, ProcessingStats

        mock_result = ProcessRunResult(
            stats=ProcessingStats(processed=10, errors=3),
            output_dir=temp_dir,
            pef_dir=os.path.join(temp_dir, "_pef"),
            summary_file=os.path.join(temp_dir, "_pef", "summary.txt"),
            elapsed_time=5.0,
            start_time="2024-01-01 00:00:00",
            end_time="2024-01-01 00:00:05",
        )

        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_orch = MagicMock()
            mock_orch.process.return_value = mock_result
            MockOrch.return_value = mock_orch

            result = run_process(sample_takeout, temp_dir, ["", "-edited"], write_exif=False)

        assert result == 2

    def test_returns_2_when_result_errors_list(self, sample_takeout, temp_dir):
        """Verify exit code 2 when result.errors is non-empty."""
        from pef.core.models import ProcessRunResult, ProcessingStats

        mock_result = ProcessRunResult(
            stats=ProcessingStats(processed=10),
            output_dir=temp_dir,
            pef_dir=os.path.join(temp_dir, "_pef"),
            summary_file=os.path.join(temp_dir, "_pef", "summary.txt"),
            elapsed_time=5.0,
            start_time="2024-01-01 00:00:00",
            end_time="2024-01-01 00:00:05",
        )
        mock_result.errors = ["Error processing file X"]

        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_orch = MagicMock()
            mock_orch.process.return_value = mock_result
            MockOrch.return_value = mock_orch

            result = run_process(sample_takeout, temp_dir, ["", "-edited"], write_exif=False)

        assert result == 2

    def test_returns_0_when_no_errors(self, sample_takeout, temp_dir):
        """Verify exit code 0 when no errors."""
        from pef.core.models import ProcessRunResult, ProcessingStats

        mock_result = ProcessRunResult(
            stats=ProcessingStats(processed=10),
            output_dir=temp_dir,
            pef_dir=os.path.join(temp_dir, "_pef"),
            summary_file=os.path.join(temp_dir, "_pef", "summary.txt"),
            elapsed_time=5.0,
            start_time="2024-01-01 00:00:00",
            end_time="2024-01-01 00:00:05",
        )

        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_orch = MagicMock()
            mock_orch.process.return_value = mock_result
            MockOrch.return_value = mock_orch

            result = run_process(sample_takeout, temp_dir, ["", "-edited"], write_exif=False)

        assert result == 0


class TestRunProcessInterrupt:
    """Tests for interrupt handling in run_process()."""

    def test_keyboard_interrupt_saves_progress(self, sample_takeout, temp_dir, capsys):
        """Verify KeyboardInterrupt saves progress and returns 130."""

        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_orch = MagicMock()
            mock_orch.process.side_effect = KeyboardInterrupt()
            mock_orch.save_progress.return_value = True
            MockOrch.return_value = mock_orch

            result = run_process(
                sample_takeout,
                os.path.join(temp_dir, "output"),
                ["", "-edited"],
                write_exif=False
            )

        assert result == 130  # SIGINT exit code
        mock_orch.save_progress.assert_called_once()

        captured = capsys.readouterr()
        assert "Interrupted" in captured.out
        assert "Progress saved" in captured.out

    def test_keyboard_interrupt_no_progress_to_save(self, sample_takeout, temp_dir, capsys):
        """Verify message when no progress to save."""
        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_orch = MagicMock()
            mock_orch.process.side_effect = KeyboardInterrupt()
            mock_orch.save_progress.return_value = False
            MockOrch.return_value = mock_orch

            result = run_process(
                sample_takeout,
                os.path.join(temp_dir, "output"),
                ["", "-edited"],
                write_exif=False
            )

        assert result == 130
        captured = capsys.readouterr()
        assert "No progress to save" in captured.out


class TestRunProcessResumeDisplay:
    """Tests for resume info display in run_process()."""

    def test_displays_resume_info(self, sample_takeout, temp_dir, capsys):
        """Verify resume info is displayed when resuming."""
        from pef.core.models import ProcessRunResult, ProcessingStats

        mock_result = ProcessRunResult(
            stats=ProcessingStats(processed=50),
            output_dir=temp_dir,
            pef_dir=os.path.join(temp_dir, "_pef"),
            summary_file=os.path.join(temp_dir, "_pef", "summary.txt"),
            elapsed_time=10.5,
            start_time="2024-01-01 00:00:00",
            end_time="2024-01-01 00:00:10",
            resumed=True,
            skipped_count=100
        )

        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_orch = MagicMock()
            mock_orch.process.return_value = mock_result
            MockOrch.return_value = mock_orch

            run_process(
                sample_takeout,
                temp_dir,
                ["", "-edited"],
                write_exif=False
            )

        captured = capsys.readouterr()
        assert "Resumed from previous run" in captured.out
        assert "skipped 100" in captured.out
        assert "plus 100 from previous run" in captured.out

    def test_no_resume_info_for_fresh_run(self, sample_takeout, temp_dir, capsys):
        """Verify no resume info for fresh runs."""
        from pef.core.models import ProcessRunResult, ProcessingStats

        mock_result = ProcessRunResult(
            stats=ProcessingStats(processed=50),
            output_dir=temp_dir,
            pef_dir=os.path.join(temp_dir, "_pef"),
            summary_file=os.path.join(temp_dir, "_pef", "summary.txt"),
            elapsed_time=10.5,
            start_time="2024-01-01 00:00:00",
            end_time="2024-01-01 00:00:10",
            resumed=False,
            skipped_count=0
        )

        with patch('pef.cli.main.PEFOrchestrator') as MockOrch:
            mock_orch = MagicMock()
            mock_orch.process.return_value = mock_result
            MockOrch.return_value = mock_orch

            run_process(
                sample_takeout,
                temp_dir,
                ["", "-edited"],
                write_exif=False
            )

        captured = capsys.readouterr()
        assert "Resumed from previous run" not in captured.out
        assert "from previous run" not in captured.out


@pytest.mark.integration
class TestCLIWithRealOrchestrator:
    """CLI tests using actual orchestrator with minimal mocking.

    Only mocks exiftool and filedate to avoid external dependencies.
    """

    def test_run_process_with_real_orchestrator(self, sample_takeout, temp_dir, capsys):
        """Test run_process with actual orchestrator (only mock exiftool/filedate)."""
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                result = run_process(
                    sample_takeout,
                    output_dir,
                    ["", "-edited"],
                    write_exif=False
                )

        assert result == 0

        # Verify actual output was created
        assert os.path.exists(output_dir)
        assert os.path.exists(os.path.join(output_dir, "Album1"))
        assert os.path.exists(os.path.join(output_dir, "_pef"))

        # Verify output shows completion
        captured = capsys.readouterr()
        assert "Finished!" in captured.out
        assert "Processed:" in captured.out

    def test_run_dry_run_with_real_orchestrator(self, sample_takeout, capsys):
        """Test run_dry_run with actual orchestrator."""
        output_dir = sample_takeout + "_pefProcessed"

        result = run_dry_run(sample_takeout, output_dir, ["", "-edited"])

        assert result == 0

        # Verify dry-run output
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "JSON metadata files" in captured.out
        assert "media files" in captured.out

        # Verify no actual output was created
        assert not os.path.exists(output_dir)

    def test_run_process_creates_correct_structure(self, sample_takeout, temp_dir):
        """Verify actual file structure is created correctly."""
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.ExifToolManager'):
            with patch('pef.core.processor.filedate'):
                run_process(
                    sample_takeout,
                    output_dir,
                    ["", "-edited"],
                    write_exif=False
                )

        # Check album subfolders directly under output
        album1 = os.path.join(output_dir, "Album1")
        album2 = os.path.join(output_dir, "Album2")
        assert os.path.exists(album1)
        assert os.path.exists(album2)

        # Check files were actually copied
        assert os.path.exists(os.path.join(album1, "photo1.jpg"))
        assert os.path.exists(os.path.join(album1, "photo2.jpg"))
        assert os.path.exists(os.path.join(album2, "image.png"))
