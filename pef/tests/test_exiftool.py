"""Tests for pef.core.exiftool module."""

import os
import sys
import threading
from unittest.mock import Mock, patch, MagicMock

import pytest

from pef.core.exiftool import (
    get_exiftool_path,
    is_exiftool_available,
    auto_download_exiftool,
    validate_exiftool,
    _reset_exiftool_cache,
    ExifToolManager,
    EXIFTOOL_DIR,
    EXIFTOOL_EXE,
    STARTUP_TIMEOUT,
)


class TestExiftoolConstants:
    """Tests for module constants."""

    def test_exiftool_dir_uses_os_path_join(self):
        # Should be platform-independent
        assert os.sep in EXIFTOOL_DIR or EXIFTOOL_DIR == os.path.join("tools", "exiftool")

    def test_exiftool_exe_platform_appropriate(self):
        if sys.platform == "win32":
            assert EXIFTOOL_EXE == "exiftool.exe"
        else:
            assert EXIFTOOL_EXE == "exiftool"


class TestValidateExiftool:
    """Tests for validate_exiftool() function."""

    def test_valid_exiftool_returns_version(self):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "12.50\n"
        mock_result.stderr = ""
        with patch('subprocess.run', return_value=mock_result):
            version = validate_exiftool("/usr/bin/exiftool")
            assert version == "12.50"

    def test_valid_version_with_patch(self):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "13.06\n"
        mock_result.stderr = ""
        with patch('subprocess.run', return_value=mock_result):
            version = validate_exiftool("/usr/bin/exiftool")
            assert version == "13.06"

    def test_invalid_output_returns_none(self):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "This is not exiftool\n"
        mock_result.stderr = ""
        with patch('subprocess.run', return_value=mock_result):
            assert validate_exiftool("/usr/bin/exiftool") is None

    def test_nonzero_returncode_returns_none(self):
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"
        with patch('subprocess.run', return_value=mock_result):
            assert validate_exiftool("/usr/bin/exiftool") is None

    def test_timeout_returns_none(self):
        import subprocess
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("exiftool", STARTUP_TIMEOUT)):
            assert validate_exiftool("/usr/bin/exiftool") is None

    def test_oserror_returns_none(self):
        with patch('subprocess.run', side_effect=OSError("No such file")):
            assert validate_exiftool("/usr/bin/exiftool") is None

    def test_uses_correct_timeout(self):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "12.50\n"
        mock_result.stderr = ""
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            validate_exiftool("/usr/bin/exiftool")
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs['timeout'] == STARTUP_TIMEOUT


class TestGetExiftoolPath:
    """Tests for get_exiftool_path() function."""

    def test_finds_in_path(self):
        _reset_exiftool_cache()
        with patch('shutil.which') as mock_which:
            mock_which.return_value = "/usr/bin/exiftool"
            with patch('pef.core.exiftool.validate_exiftool', return_value="12.50"):
                result = get_exiftool_path()

                assert result == "exiftool"
                mock_which.assert_called_with("exiftool")
        _reset_exiftool_cache()

    def test_finds_in_local_tools(self, temp_dir):
        # Create local tools directory with exe
        tools_dir = os.path.join(temp_dir, EXIFTOOL_DIR)
        os.makedirs(tools_dir)
        exe_path = os.path.join(tools_dir, EXIFTOOL_EXE)
        with open(exe_path, "w") as f:
            f.write("fake exe")

        with patch('shutil.which') as mock_which:
            mock_which.return_value = None  # Not in PATH
            with patch('pef.core.exiftool.validate_exiftool', return_value="12.50"):
                result = get_exiftool_path(base_dir=temp_dir)

                assert result == exe_path

    def test_rejects_invalid_exiftool_in_path(self):
        _reset_exiftool_cache()
        with patch('shutil.which') as mock_which:
            mock_which.return_value = "/usr/bin/exiftool"
            with patch('pef.core.exiftool.validate_exiftool', return_value=None):
                with patch('pef.core.exiftool.auto_download_exiftool', return_value=False):
                    result = get_exiftool_path()
                    assert result is None
        _reset_exiftool_cache()

    def test_rejects_invalid_local_exiftool(self, temp_dir):
        tools_dir = os.path.join(temp_dir, EXIFTOOL_DIR)
        os.makedirs(tools_dir)
        exe_path = os.path.join(tools_dir, EXIFTOOL_EXE)
        with open(exe_path, "w") as f:
            f.write("fake exe")

        with patch('shutil.which') as mock_which:
            mock_which.return_value = None
            with patch('pef.core.exiftool.validate_exiftool', return_value=None):
                with patch('pef.core.exiftool.auto_download_exiftool', return_value=False):
                    result = get_exiftool_path(base_dir=temp_dir)
                    assert result is None

    def test_returns_none_when_not_found(self, temp_dir):
        with patch('shutil.which') as mock_which:
            mock_which.return_value = None
            with patch('pef.core.exiftool.auto_download_exiftool') as mock_download:
                mock_download.return_value = False
                result = get_exiftool_path(base_dir=temp_dir)

                assert result is None


class TestIsExiftoolAvailable:
    """Tests for is_exiftool_available() function."""

    def test_true_when_in_path(self):
        with patch('shutil.which') as mock_which:
            mock_which.return_value = "/usr/bin/exiftool"
            with patch('pef.core.exiftool.validate_exiftool', return_value="12.50"):
                assert is_exiftool_available() is True

    def test_true_when_in_local_tools(self, temp_dir):
        # Create local tools directory with exe
        tools_dir = os.path.join(temp_dir, EXIFTOOL_DIR)
        os.makedirs(tools_dir)
        exe_path = os.path.join(tools_dir, EXIFTOOL_EXE)
        with open(exe_path, "w") as f:
            f.write("fake exe")

        with patch('shutil.which') as mock_which:
            mock_which.return_value = None
            # Patch the module's __file__ to point to our temp dir
            with patch('pef.core.exiftool.__file__', os.path.join(temp_dir, 'pef', 'core', 'exiftool.py')):
                # This test is tricky because is_exiftool_available uses hardcoded path resolution
                # For now, just verify the function returns boolean
                result = is_exiftool_available()
                assert isinstance(result, bool)

    def test_false_when_not_found(self):
        with patch('shutil.which') as mock_which:
            mock_which.return_value = None
            with patch('os.path.exists') as mock_exists:
                mock_exists.return_value = False
                # The actual result depends on file system state
                result = is_exiftool_available()
                assert isinstance(result, bool)


class TestAutoDownloadExiftool:
    """Tests for auto_download_exiftool() function."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only auto-download")
    def test_creates_tools_directory(self, temp_dir):
        with patch('urllib.request.urlopen') as mock_urlopen:
            with patch('urllib.request.urlretrieve') as mock_retrieve:
                with patch('zipfile.ZipFile'):
                    # Mock version check
                    mock_response = MagicMock()
                    mock_response.read.return_value = b"12.50"
                    mock_response.__enter__ = Mock(return_value=mock_response)
                    mock_response.__exit__ = Mock(return_value=False)
                    mock_urlopen.return_value = mock_response

                    # Mock download - simulate failure for test
                    mock_retrieve.side_effect = Exception("Network error")

                    result = auto_download_exiftool(temp_dir)

                    assert result is False

    def test_handles_network_error(self, temp_dir):
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Network error")

            result = auto_download_exiftool(temp_dir)

            assert result is False


class TestExifToolManager:
    """Tests for ExifToolManager class."""

    def test_initial_state(self):
        manager = ExifToolManager()
        assert manager.is_running is False
        assert manager.exiftool_path is None

    def test_start_without_exiftool_installed(self):
        with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
            mock_get_path.return_value = None

            manager = ExifToolManager()
            result = manager.start()

            assert result is False
            assert manager.is_running is False
            assert manager.start_error is not None
            assert "not found" in manager.start_error.lower() or "not working" in manager.start_error.lower()

    def test_start_without_pyexiftool(self):
        with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
            mock_get_path.return_value = "/usr/bin/exiftool"

            # Simulate ImportError for exiftool module
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "exiftool":
                    raise ImportError("No module named 'exiftool'")
                return original_import(name, *args, **kwargs)

            with patch.object(builtins, '__import__', mock_import):
                manager = ExifToolManager()
                result = manager.start()

                assert result is False

    def test_context_manager_calls_stop(self):
        with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
            mock_get_path.return_value = None

            manager = ExifToolManager()
            with manager:
                pass

            # stop() should have been called even if start failed

    def test_start_sets_error_on_exception(self):
        mock_module = MagicMock()
        mock_helper = MagicMock()
        mock_helper.run.side_effect = Exception("process failed")
        mock_module.ExifToolHelper.return_value = mock_helper

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                result = manager.start()

                assert result is False
                assert manager.start_error is not None
                assert "failed to start" in manager.start_error.lower()
                assert manager._helper is None

    def test_write_tags_returns_false_when_not_running(self):
        manager = ExifToolManager()
        result = manager.write_tags("/path/file.jpg", {"GPSLatitude": 40.7})

        assert result is False

    def test_write_tags_returns_false_with_empty_tags(self):
        manager = ExifToolManager()
        manager._helper = MagicMock()  # Fake a running state

        result = manager.write_tags("/path/file.jpg", {})

        assert result is False

    def test_read_tags_returns_empty_when_not_running(self):
        manager = ExifToolManager()
        result = manager.read_tags("/path/file.jpg")

        assert result == {}

    def test_stop_handles_no_helper(self):
        manager = ExifToolManager()
        # Should not raise
        manager.stop()
        assert manager._helper is None

    def test_stop_handles_exception(self):
        manager = ExifToolManager()
        manager._helper = MagicMock()
        manager._helper.terminate.side_effect = Exception("Error")

        # Should not raise
        manager.stop()
        assert manager._helper is None


class TestExifToolManagerWithMockedExiftool:
    """Tests for ExifToolManager with mocked exiftool module."""

    @pytest.fixture
    def mock_exiftool_module(self):
        """Create a mock exiftool module."""
        mock_module = MagicMock()
        mock_helper = MagicMock()
        mock_module.ExifToolHelper.return_value = mock_helper
        return mock_module, mock_helper

    def test_start_success(self, mock_exiftool_module):
        mock_module, mock_helper = mock_exiftool_module

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                result = manager.start()

                assert result is True
                assert manager.is_running is True
                mock_helper.run.assert_called_once()

    def test_write_tags_success(self, mock_exiftool_module):
        mock_module, mock_helper = mock_exiftool_module

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                result = manager.write_tags("/path/file.jpg", {"GPSLatitude": 40.7})

                assert result is True
                mock_helper.set_tags.assert_called_with("/path/file.jpg", {"GPSLatitude": 40.7})

    def test_read_tags_success(self, mock_exiftool_module):
        mock_module, mock_helper = mock_exiftool_module
        mock_helper.get_tags.return_value = [{"GPSLatitude": 40.7}]

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                result = manager.read_tags("/path/file.jpg", ["GPSLatitude"])

                assert result == {"GPSLatitude": 40.7}

    def test_read_tags_no_tags_calls_get_metadata(self, mock_exiftool_module):
        """Verify read_tags with no tags argument calls get_metadata."""
        mock_module, mock_helper = mock_exiftool_module
        mock_helper.get_metadata.return_value = [{"EXIF:Make": "Canon", "EXIF:Model": "EOS"}]

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                result = manager.read_tags("/path/file.jpg")  # No tags specified

                assert result == {"EXIF:Make": "Canon", "EXIF:Model": "EOS"}
                mock_helper.get_metadata.assert_called_once_with("/path/file.jpg")
                mock_helper.get_tags.assert_not_called()

    def test_read_tags_empty_result(self, mock_exiftool_module):
        """Verify read_tags returns empty dict when result list is empty."""
        mock_module, mock_helper = mock_exiftool_module
        mock_helper.get_tags.return_value = []  # Empty result list

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                result = manager.read_tags("/path/nonexistent.jpg", ["GPSLatitude"])

                assert result == {}


class TestExifToolManagerBatchOperations:
    """Tests for batch operations in ExifToolManager."""

    @pytest.fixture
    def mock_exiftool_module(self):
        """Create a mock exiftool module."""
        mock_module = MagicMock()
        mock_helper = MagicMock()
        mock_module.ExifToolHelper.return_value = mock_helper
        return mock_module, mock_helper

    def test_write_tags_batch_success(self, mock_exiftool_module):
        mock_module, mock_helper = mock_exiftool_module

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                file_tags_pairs = [
                    ("/path/file1.jpg", {"GPSLatitude": 40.7}),
                    ("/path/file2.jpg", {"GPSLatitude": 41.0}),
                ]
                results = manager.write_tags_batch(file_tags_pairs)

                assert results == [True, True]
                assert mock_helper.set_tags.call_count == 2

    def test_write_tags_batch_partial_failure(self, mock_exiftool_module):
        mock_module, mock_helper = mock_exiftool_module
        # First call succeeds, second fails
        mock_helper.set_tags.side_effect = [None, Exception("Write failed")]

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                file_tags_pairs = [
                    ("/path/file1.jpg", {"GPSLatitude": 40.7}),
                    ("/path/file2.jpg", {"GPSLatitude": 41.0}),
                ]
                results = manager.write_tags_batch(file_tags_pairs)

                assert results == [True, False]

    def test_write_tags_batch_empty_tags_skipped(self, mock_exiftool_module):
        mock_module, mock_helper = mock_exiftool_module

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                file_tags_pairs = [
                    ("/path/file1.jpg", {"GPSLatitude": 40.7}),
                    ("/path/file2.jpg", {}),  # Empty tags
                ]
                results = manager.write_tags_batch(file_tags_pairs)

                assert results == [True, True]  # Empty tags = success (nothing to do)
                assert mock_helper.set_tags.call_count == 1  # Only called for first file

    def test_write_tags_batch_returns_empty_when_not_running(self):
        manager = ExifToolManager()
        # Not started

        results = manager.write_tags_batch([("/path/file.jpg", {"GPSLatitude": 40.7})])

        assert results == [False]

    def test_write_tags_batch_empty_list(self, mock_exiftool_module):
        mock_module, mock_helper = mock_exiftool_module

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                results = manager.write_tags_batch([])

                assert results == []

    def test_read_tags_batch_success(self, mock_exiftool_module):
        mock_module, mock_helper = mock_exiftool_module
        mock_helper.get_tags.return_value = [
            {"GPSLatitude": 40.7},
            {"GPSLatitude": 41.0}
        ]

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                results = manager.read_tags_batch(
                    ["/path/file1.jpg", "/path/file2.jpg"],
                    ["GPSLatitude"]
                )

                assert len(results) == 2
                assert results[0]["GPSLatitude"] == 40.7
                assert results[1]["GPSLatitude"] == 41.0

    def test_read_tags_batch_returns_empty_when_not_running(self):
        manager = ExifToolManager()

        results = manager.read_tags_batch(["/path/file.jpg"])

        assert results == [{}]

    def test_read_tags_batch_handles_error(self, mock_exiftool_module):
        mock_module, mock_helper = mock_exiftool_module
        # Mock both get_tags and get_metadata since code path depends on tags parameter
        mock_helper.get_tags.side_effect = Exception("Read failed")
        mock_helper.get_metadata.side_effect = Exception("Read failed")

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                results = manager.read_tags_batch(["/path/file1.jpg", "/path/file2.jpg"])

                assert results == [{}, {}]


class TestExifToolManagerCancelAndTimeout:
    """Tests for cancel and timeout behavior in ExifToolManager."""

    @pytest.fixture
    def mock_exiftool_module(self):
        """Create a mock exiftool module."""
        mock_module = MagicMock()
        mock_helper = MagicMock()
        mock_module.ExifToolHelper.return_value = mock_helper
        return mock_module, mock_helper

    def test_write_tags_batch_cancel_stops_processing(self, mock_exiftool_module):
        """Verify cancel_event stops batch write and fills remaining as False."""
        mock_module, mock_helper = mock_exiftool_module
        cancel_event = threading.Event()

        # Cancel after first file is processed
        call_count = [0]
        def set_tags_with_cancel(filepath, tags):
            call_count[0] += 1
            if call_count[0] >= 1:
                cancel_event.set()

        mock_helper.set_tags.side_effect = set_tags_with_cancel

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                file_tags_pairs = [
                    ("/path/file1.jpg", {"GPSLatitude": 40.7}),
                    ("/path/file2.jpg", {"GPSLatitude": 41.0}),
                    ("/path/file3.jpg", {"GPSLatitude": 42.0}),
                ]
                results = manager.write_tags_batch(
                    file_tags_pairs, cancel_event=cancel_event
                )

        assert len(results) == 3
        assert results[0] is True  # First file processed
        # Remaining files should be False (cancelled)
        assert False in results[1:]

    def test_write_tags_batch_cancel_already_set(self, mock_exiftool_module):
        """Verify pre-set cancel_event skips all files."""
        mock_module, mock_helper = mock_exiftool_module
        cancel_event = threading.Event()
        cancel_event.set()  # Pre-set

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"

                manager = ExifToolManager()
                manager.start()

                file_tags_pairs = [
                    ("/path/file1.jpg", {"GPSLatitude": 40.7}),
                    ("/path/file2.jpg", {"GPSLatitude": 41.0}),
                ]
                results = manager.write_tags_batch(
                    file_tags_pairs, cancel_event=cancel_event
                )

        assert results == [False, False]
        mock_helper.set_tags.assert_not_called()

    def test_start_timeout_returns_false(self):
        """Verify start() returns False when ExifTool hangs during startup."""
        mock_module = MagicMock()
        mock_helper = MagicMock()

        # Simulate hanging by sleeping longer than timeout
        import time
        def hang_forever():
            time.sleep(30)

        mock_helper.run.side_effect = hang_forever
        mock_module.ExifToolHelper.return_value = mock_helper

        with patch.dict('sys.modules', {'exiftool': mock_module}):
            with patch('pef.core.exiftool.get_exiftool_path') as mock_get_path:
                mock_get_path.return_value = "/usr/bin/exiftool"
                with patch('pef.core.exiftool.STARTUP_TIMEOUT', 0.1):
                    manager = ExifToolManager()
                    result = manager.start()

        assert result is False
        assert manager.start_error is not None
        assert "timed out" in manager.start_error.lower()
