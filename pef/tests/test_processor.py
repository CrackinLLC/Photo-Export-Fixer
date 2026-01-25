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

        assert sample_file.output_path == dest
        assert sample_file.json_path == sample_metadata.filepath

    def test_copy_unmatched_file(self, output_dir, sample_file):
        with FileProcessor(output_dir, write_exif=False) as processor:
            dest = processor.copy_unmatched_file(sample_file)

        assert os.path.exists(dest)
        assert "Unprocessed" in dest
        assert processor.stats.unmatched_files == 1

    def test_unique_path_on_collision(self, output_dir, sample_file, sample_metadata):
        # Process same file twice
        with patch('pef.core.processor.filedate'):
            with FileProcessor(output_dir, write_exif=False) as processor:
                dest1 = processor.process_file(sample_file, sample_metadata)

                # Reset output_path and process again
                sample_file.output_path = None
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


class TestCopyUnmatchedFiles:
    """Tests for copy_unmatched_files() batch method."""

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
            result = processor.copy_unmatched_files(source_files)

        assert len(result) == 3
        for f in result:
            assert f.output_path is not None
            assert os.path.exists(f.output_path)

    def test_updates_stats(self, temp_dir, source_files):
        """Verify stats are updated for each file."""
        output_dir = os.path.join(temp_dir, "output")

        with FileProcessor(output_dir, write_exif=False) as processor:
            processor.copy_unmatched_files(source_files)

            assert processor.stats.unmatched_files == 3

    def test_progress_callback_called(self, temp_dir, source_files):
        """Verify progress callback is called."""
        output_dir = os.path.join(temp_dir, "output")
        calls = []

        def callback(current, total, message):
            calls.append((current, total, message))

        with FileProcessor(output_dir, write_exif=False) as processor:
            processor.copy_unmatched_files(source_files, on_progress=callback)

        assert len(calls) == 3
        assert calls[-1][0] == 3  # Final current == total

    def test_files_go_to_unprocessed_folder(self, temp_dir, source_files):
        """Verify files are copied to Unprocessed folder."""
        output_dir = os.path.join(temp_dir, "output")

        with FileProcessor(output_dir, write_exif=False) as processor:
            result = processor.copy_unmatched_files(source_files)

        for f in result:
            assert "Unprocessed" in f.output_path


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
                # Batch write returns False for the failing file
                mock_et.write_tags_batch.return_value = [False]
                MockET.return_value = mock_et

                with FileProcessor(output_dir, write_exif=True) as processor:
                    processor.process_file(file_info, metadata)
                    # Exit flushes the batch

                assert processor.stats.errors == 1
                assert processor.stats.processed == 1  # File still processed


class TestFileProcessorBatching:
    """Tests for batch metadata writing in FileProcessor."""

    @pytest.fixture
    def source_files_with_metadata(self, temp_dir):
        """Create multiple source files with GPS metadata."""
        album = os.path.join(temp_dir, "source", "Album")
        os.makedirs(album)

        files_and_metadata = []
        for i in range(5):
            filepath = os.path.join(album, f"photo{i}.jpg")
            with open(filepath, "wb") as f:
                f.write(f"data{i}".encode())

            file_info = FileInfo(f"photo{i}.jpg", filepath, "Album")
            metadata = JsonMetadata(
                filepath=f"/test{i}.json",
                title=f"photo{i}.jpg",
                date=datetime.now(),
                geo_data=GeoData(40.0 + i * 0.1, -74.0)
            )
            files_and_metadata.append((file_info, metadata))

        return files_and_metadata

    def test_batch_size_configurable(self, temp_dir):
        """Verify batch size can be configured."""
        with FileProcessor(temp_dir, write_exif=False, batch_size=100) as processor:
            assert processor._batch_size == 100

    def test_queue_metadata_write_accumulates(self, temp_dir):
        """Verify queued writes accumulate until flush."""
        with patch('pef.core.processor.ExifToolManager') as MockET:
            mock_et = MagicMock()
            mock_et.start.return_value = True
            MockET.return_value = mock_et

            with FileProcessor(temp_dir, write_exif=True, batch_size=10) as processor:
                # Queue 3 writes (less than batch size)
                processor.queue_metadata_write("/path/file1.jpg", {"GPS": 1})
                processor.queue_metadata_write("/path/file2.jpg", {"GPS": 2})
                processor.queue_metadata_write("/path/file3.jpg", {"GPS": 3})

                assert processor.pending_writes_count == 3
                mock_et.write_tags_batch.assert_not_called()

    def test_auto_flush_at_batch_size(self, temp_dir):
        """Verify automatic flush when batch size is reached."""
        with patch('pef.core.processor.ExifToolManager') as MockET:
            mock_et = MagicMock()
            mock_et.start.return_value = True
            mock_et.write_tags_batch.return_value = [True, True, True]
            MockET.return_value = mock_et

            with FileProcessor(temp_dir, write_exif=True, batch_size=3) as processor:
                processor.queue_metadata_write("/path/file1.jpg", {"GPS": 1})
                processor.queue_metadata_write("/path/file2.jpg", {"GPS": 2})

                # Not flushed yet
                assert processor.pending_writes_count == 2
                mock_et.write_tags_batch.assert_not_called()

                # This should trigger auto-flush
                processor.queue_metadata_write("/path/file3.jpg", {"GPS": 3})

                assert processor.pending_writes_count == 0
                mock_et.write_tags_batch.assert_called_once()

    def test_flush_on_context_exit(self, temp_dir):
        """Verify remaining writes are flushed on context exit."""
        with patch('pef.core.processor.ExifToolManager') as MockET:
            mock_et = MagicMock()
            mock_et.start.return_value = True
            mock_et.write_tags_batch.return_value = [True, True]
            MockET.return_value = mock_et

            with FileProcessor(temp_dir, write_exif=True, batch_size=100) as processor:
                processor.queue_metadata_write("/path/file1.jpg", {"GPS": 1})
                processor.queue_metadata_write("/path/file2.jpg", {"GPS": 2})

                # Not flushed during processing (batch size not reached)
                mock_et.write_tags_batch.assert_not_called()

            # Should be flushed after exiting context
            mock_et.write_tags_batch.assert_called_once()

    def test_batch_errors_tracked(self, temp_dir):
        """Verify batch write errors are tracked in stats."""
        with patch('pef.core.processor.ExifToolManager') as MockET:
            mock_et = MagicMock()
            mock_et.start.return_value = True
            # Partial failure: first succeeds, second fails
            mock_et.write_tags_batch.return_value = [True, False]
            MockET.return_value = mock_et

            with FileProcessor(temp_dir, write_exif=True, batch_size=2) as processor:
                processor.queue_metadata_write("/path/file1.jpg", {"GPS": 1})
                processor.queue_metadata_write("/path/file2.jpg", {"GPS": 2})
                # Batch size reached, auto-flush

            assert processor.stats.errors == 1

    def test_empty_tags_not_queued(self, temp_dir):
        """Verify empty tags dict is not queued."""
        with patch('pef.core.processor.ExifToolManager') as MockET:
            mock_et = MagicMock()
            mock_et.start.return_value = True
            MockET.return_value = mock_et

            with FileProcessor(temp_dir, write_exif=True) as processor:
                processor.queue_metadata_write("/path/file.jpg", {})

                assert processor.pending_writes_count == 0

    def test_process_file_queues_metadata(self, temp_dir, source_files_with_metadata):
        """Verify process_file queues metadata instead of immediate write."""
        output_dir = os.path.join(temp_dir, "output")

        with patch('pef.core.processor.filedate'):
            with patch('pef.core.processor.ExifToolManager') as MockET:
                mock_et = MagicMock()
                mock_et.start.return_value = True
                mock_et.write_tags_batch.return_value = [True] * 5
                MockET.return_value = mock_et

                with FileProcessor(output_dir, write_exif=True, batch_size=10) as processor:
                    for file_info, metadata in source_files_with_metadata:
                        processor.process_file(file_info, metadata)

                    # Should be queued, not written yet (batch size = 10)
                    assert processor.pending_writes_count == 5
                    mock_et.write_tags_batch.assert_not_called()

                # Flushed on exit
                mock_et.write_tags_batch.assert_called_once()

    def test_flush_metadata_writes_returns_count(self, temp_dir):
        """Verify flush returns count of successful writes."""
        with patch('pef.core.processor.ExifToolManager') as MockET:
            mock_et = MagicMock()
            mock_et.start.return_value = True
            mock_et.write_tags_batch.return_value = [True, True, False]
            MockET.return_value = mock_et

            with FileProcessor(temp_dir, write_exif=True) as processor:
                processor.queue_metadata_write("/path/file1.jpg", {"GPS": 1})
                processor.queue_metadata_write("/path/file2.jpg", {"GPS": 2})
                processor.queue_metadata_write("/path/file3.jpg", {"GPS": 3})

                count = processor.flush_metadata_writes()

                assert count == 2  # 2 succeeded, 1 failed

    def test_flush_empty_queue_returns_zero(self, temp_dir):
        """Verify flushing an empty queue returns 0 and doesn't error."""
        with patch('pef.core.processor.ExifToolManager') as MockET:
            mock_et = MagicMock()
            mock_et.start.return_value = True
            MockET.return_value = mock_et

            with FileProcessor(temp_dir, write_exif=True) as processor:
                # Flush without queueing anything
                count = processor.flush_metadata_writes()

                assert count == 0
                mock_et.write_tags_batch.assert_not_called()

    def test_flush_can_be_called_multiple_times(self, temp_dir):
        """Verify flush can be called multiple times safely."""
        with patch('pef.core.processor.ExifToolManager') as MockET:
            mock_et = MagicMock()
            mock_et.start.return_value = True
            mock_et.write_tags_batch.return_value = [True]
            MockET.return_value = mock_et

            with FileProcessor(temp_dir, write_exif=True) as processor:
                processor.queue_metadata_write("/path/file1.jpg", {"GPS": 1})
                count1 = processor.flush_metadata_writes()

                # Second flush with empty queue
                count2 = processor.flush_metadata_writes()

                # Third call after queueing more
                processor.queue_metadata_write("/path/file2.jpg", {"GPS": 2})
                count3 = processor.flush_metadata_writes()

                assert count1 == 1
                assert count2 == 0
                assert count3 == 1
                assert mock_et.write_tags_batch.call_count == 2

    def test_flush_when_exiftool_unavailable_counts_errors(self, temp_dir):
        """Verify queued writes become errors when ExifTool is unavailable."""
        with FileProcessor(temp_dir, write_exif=False) as processor:
            # Manually queue writes (bypasses the exiftool check)
            processor._pending_writes = [
                ("/path/file1.jpg", {"GPS": 1}),
                ("/path/file2.jpg", {"GPS": 2}),
            ]

            count = processor.flush_metadata_writes()

            assert count == 0
            assert processor.stats.errors == 2
            assert processor.pending_writes_count == 0

    def test_queue_cleared_even_on_complete_batch_failure(self, temp_dir):
        """Verify queue is cleared even when all writes fail."""
        with patch('pef.core.processor.ExifToolManager') as MockET:
            mock_et = MagicMock()
            mock_et.start.return_value = True
            # All writes fail
            mock_et.write_tags_batch.return_value = [False, False, False]
            MockET.return_value = mock_et

            with FileProcessor(temp_dir, write_exif=True) as processor:
                processor.queue_metadata_write("/path/file1.jpg", {"GPS": 1})
                processor.queue_metadata_write("/path/file2.jpg", {"GPS": 2})
                processor.queue_metadata_write("/path/file3.jpg", {"GPS": 3})

                count = processor.flush_metadata_writes()

                assert count == 0
                assert processor.pending_writes_count == 0
                assert processor.stats.errors == 3
