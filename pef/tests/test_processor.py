"""Tests for pef.core.processor module."""

import os
import warnings
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest

from pef.core.processor import FileProcessor, copy_modify
from pef.core.models import FileInfo, JsonMetadata, GeoData, Person, ProcessingStats


class TestFileProcessor:
    """Tests for FileProcessor class."""

    @pytest.fixture
    def output_dir(self, temp_dir):
        """Create output directory structure."""
        return temp_dir

    @pytest.fixture
    def sample_file(self, temp_dir):
        """Create a sample file for testing."""
        album = os.path.join(temp_dir, "source", "Album1")
        os.makedirs(album)
        filepath = os.path.join(album, "photo.jpg")
        with open(filepath, "wb") as f:
            f.write(b"fake jpg data")
        return FileInfo("photo.jpg", filepath, "Album1")

    @pytest.fixture
    def sample_metadata(self):
        """Create sample metadata."""
        return JsonMetadata(
            filepath="/source/Album1/photo.jpg.json",
            title="photo.jpg",
            date=datetime(2021, 1, 1, 12, 0, 0),
            geo_data=GeoData(40.7128, -74.0060, 10),
            people=[Person("Alice"), Person("Bob")]
        )

    def test_creates_processed_dir(self, output_dir, sample_file, sample_metadata):
        with patch('pef.core.processor.filedate'):
            with FileProcessor(output_dir, write_exif=False) as processor:
                processor.process_file(sample_file, sample_metadata)

        assert os.path.exists(os.path.join(output_dir, "Processed"))

    def test_creates_album_subdir(self, output_dir, sample_file, sample_metadata):
        with patch('pef.core.processor.filedate'):
            with FileProcessor(output_dir, write_exif=False) as processor:
                processor.process_file(sample_file, sample_metadata)

        assert os.path.exists(os.path.join(output_dir, "Processed", "Album1"))

    def test_copies_file(self, output_dir, sample_file, sample_metadata):
        with patch('pef.core.processor.filedate'):
            with FileProcessor(output_dir, write_exif=False) as processor:
                dest = processor.process_file(sample_file, sample_metadata)

        assert os.path.exists(dest)
        with open(dest, "rb") as f:
            assert f.read() == b"fake jpg data"

    def test_updates_stats(self, output_dir, sample_file, sample_metadata):
        with patch('pef.core.processor.filedate'):
            with FileProcessor(output_dir, write_exif=False) as processor:
                processor.process_file(sample_file, sample_metadata)
                assert processor.stats.processed == 1

    def test_updates_file_info(self, output_dir, sample_file, sample_metadata):
        with patch('pef.core.processor.filedate'):
            with FileProcessor(output_dir, write_exif=False) as processor:
                dest = processor.process_file(sample_file, sample_metadata)

        assert sample_file.procpath == dest
        assert sample_file.jsonpath == sample_metadata.filepath

    def test_process_unmatched_file(self, output_dir, sample_file):
        with FileProcessor(output_dir, write_exif=False) as processor:
            dest = processor.process_unmatched_file(sample_file)

        assert os.path.exists(dest)
        assert "Unprocessed" in dest
        assert processor.stats.unmatched_files == 1

    def test_unique_path_on_collision(self, output_dir, sample_file, sample_metadata):
        # Process same file twice
        with patch('pef.core.processor.filedate'):
            with FileProcessor(output_dir, write_exif=False) as processor:
                dest1 = processor.process_file(sample_file, sample_metadata)

                # Reset procpath and process again
                sample_file.procpath = None
                dest2 = processor.process_file(sample_file, sample_metadata)

        assert dest1 != dest2
        assert "(1)" in dest2

    def test_context_manager_stops_exiftool(self, output_dir):
        with patch('pef.core.processor.ExifToolManager') as MockManager:
            mock_instance = MagicMock()
            MockManager.return_value = mock_instance

            with FileProcessor(output_dir, write_exif=True) as processor:
                pass

            mock_instance.stop.assert_called_once()

    def test_extend_metadata(self, output_dir, sample_file, sample_metadata):
        # Copy file to output first
        dest = os.path.join(output_dir, "photo.jpg")
        with open(sample_file.filepath, "rb") as src:
            with open(dest, "wb") as dst:
                dst.write(src.read())

        with patch('pef.core.processor.ExifToolManager') as MockManager:
            mock_instance = MagicMock()
            mock_instance.start.return_value = True
            mock_instance.write_tags.return_value = True
            MockManager.return_value = mock_instance

            with FileProcessor(output_dir, write_exif=True) as processor:
                result = processor.extend_metadata(dest, sample_metadata)

            assert result is True
            mock_instance.write_tags.assert_called()


class TestCopyModify:
    """Tests for copy_modify() backwards-compatible function."""

    @pytest.fixture
    def source_file(self, temp_dir):
        """Create a source file."""
        album = os.path.join(temp_dir, "Album1")
        os.makedirs(album)
        filepath = os.path.join(album, "photo.jpg")
        with open(filepath, "wb") as f:
            f.write(b"fake data")
        return {
            "filename": "photo.jpg",
            "filepath": filepath,
            "albumname": "Album1"
        }

    @pytest.fixture
    def output_dir(self, temp_dir):
        return os.path.join(temp_dir, "output")

    def test_emits_deprecation_warning(self, source_file, output_dir):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch('pef.core.processor.filedate'):
                copy_modify(source_file, datetime.now(), output_dir)

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)

    def test_copies_file(self, source_file, output_dir):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with patch('pef.core.processor.filedate'):
                dest = copy_modify(source_file, datetime.now(), output_dir)

        assert os.path.exists(dest)

    def test_creates_album_dir(self, source_file, output_dir):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with patch('pef.core.processor.filedate'):
                copy_modify(source_file, datetime.now(), output_dir)

        assert os.path.exists(os.path.join(output_dir, "Album1"))

    def test_returns_dest_path(self, source_file, output_dir):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with patch('pef.core.processor.filedate'):
                dest = copy_modify(source_file, datetime.now(), output_dir)

        assert dest.endswith("photo.jpg")
        assert "Album1" in dest


class TestFileProcessorStats:
    """Tests for FileProcessor statistics tracking."""

    def test_initial_stats_zero(self, temp_dir):
        with FileProcessor(temp_dir, write_exif=False) as processor:
            assert processor.stats.processed == 0
            assert processor.stats.errors == 0
            assert processor.stats.unmatched_files == 0

    def test_stats_accumulate(self, temp_dir):
        # Create multiple source files
        album = os.path.join(temp_dir, "source", "Album")
        os.makedirs(album)

        files = []
        for i in range(3):
            filepath = os.path.join(album, f"photo{i}.jpg")
            with open(filepath, "wb") as f:
                f.write(b"data")
            files.append(FileInfo(f"photo{i}.jpg", filepath, "Album"))

        metadata = JsonMetadata(
            filepath="/test.json",
            title="photo.jpg",
            date=datetime.now()
        )

        with patch('pef.core.processor.filedate'):
            with FileProcessor(temp_dir, write_exif=False) as processor:
                for f in files:
                    processor.process_file(f, metadata)

                assert processor.stats.processed == 3


class TestProcessUnmatchedFiles:
    """Tests for process_unmatched_files() batch method."""

    @pytest.fixture
    def source_files(self, temp_dir):
        """Create multiple source files for testing."""
        album = os.path.join(temp_dir, "source", "Album")
        os.makedirs(album)

        files = []
        for i in range(3):
            filepath = os.path.join(album, f"photo{i}.jpg")
            with open(filepath, "wb") as f:
                f.write(f"data{i}".encode())
            files.append(FileInfo(f"photo{i}.jpg", filepath, "Album"))

        return files

    def test_copies_all_files(self, temp_dir, source_files):
        """Verify all unmatched files are copied."""
        output_dir = os.path.join(temp_dir, "output")

        with FileProcessor(output_dir, write_exif=False) as processor:
            result = processor.process_unmatched_files(source_files)

        assert len(result) == 3
        for f in result:
            assert f.procpath is not None
            assert os.path.exists(f.procpath)

    def test_updates_stats(self, temp_dir, source_files):
        """Verify stats are updated for each file."""
        output_dir = os.path.join(temp_dir, "output")

        with FileProcessor(output_dir, write_exif=False) as processor:
            processor.process_unmatched_files(source_files)

            assert processor.stats.unmatched_files == 3

    def test_progress_callback_called(self, temp_dir, source_files):
        """Verify progress callback is called."""
        output_dir = os.path.join(temp_dir, "output")
        calls = []

        def callback(current, total, message):
            calls.append((current, total, message))

        with FileProcessor(output_dir, write_exif=False) as processor:
            processor.process_unmatched_files(source_files, on_progress=callback)

        assert len(calls) == 3
        assert calls[-1][0] == 3  # Final current == total

    def test_files_go_to_unprocessed_folder(self, temp_dir, source_files):
        """Verify files are copied to Unprocessed folder."""
        output_dir = os.path.join(temp_dir, "output")

        with FileProcessor(output_dir, write_exif=False) as processor:
            result = processor.process_unmatched_files(source_files)

        for f in result:
            assert "Unprocessed" in f.procpath


class TestFileProcessorErrorHandling:
    """Tests for error handling in FileProcessor."""

    def test_exiftool_write_failure_increments_errors(self, temp_dir):
        """Verify ExifTool write failure increments error count."""
        # Create source file
        album = os.path.join(temp_dir, "source", "Album")
        os.makedirs(album)
        filepath = os.path.join(album, "photo.jpg")
        with open(filepath, "wb") as f:
            f.write(b"fake jpg")

        file_info = FileInfo("photo.jpg", filepath, "Album")
        metadata = JsonMetadata(
            filepath="/test.json",
            title="photo.jpg",
            date=datetime.now(),
            geo_data=GeoData(40.7, -74.0)  # Has GPS data to trigger write
        )

        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager') as MockET:
                mock_et = MagicMock()
                mock_et.start.return_value = True
                mock_et.write_tags.side_effect = Exception("ExifTool error")
                MockET.return_value = mock_et

                with FileProcessor(output_dir, write_exif=True) as processor:
                    processor.process_file(file_info, metadata)

                    assert processor.stats.errors == 1
                    assert processor.stats.processed == 1  # File still processed
