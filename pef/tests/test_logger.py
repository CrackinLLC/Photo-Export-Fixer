"""Tests for pef.core.logger module."""

import os

from pef.core.logger import (
    BufferedLogger,
    SummaryLogger,
    NullLogger,
    create_logger,
)


class TestBufferedLogger:
    """Tests for BufferedLogger class."""

    def test_creates_log_file_on_first_log(self, temp_dir):
        logger = BufferedLogger(temp_dir, "test.log")
        filepath = os.path.join(temp_dir, "test.log")

        # File should not exist before first log (lazy opening)
        assert not os.path.exists(filepath)

        logger.log("Test message")
        logger.close()

        assert os.path.exists(filepath)

    def test_writes_timestamped_message(self, temp_dir):
        logger = BufferedLogger(temp_dir, "test.log")
        logger.log("Test message")
        logger.close()

        with open(os.path.join(temp_dir, "test.log")) as f:
            content = f.read()

        assert "Test message" in content
        # Should have timestamp format: YYYY-MM-DD HH:MM:SS
        assert " - " in content

    def test_multiple_messages(self, temp_dir):
        logger = BufferedLogger(temp_dir, "test.log")
        logger.log("Message 1")
        logger.log("Message 2")
        logger.log("Message 3")
        logger.close()

        with open(os.path.join(temp_dir, "test.log")) as f:
            lines = f.readlines()

        assert len(lines) == 3

    def test_context_manager(self, temp_dir):
        with BufferedLogger(temp_dir, "test.log") as logger:
            logger.log("Test")

        # File should be closed after context manager
        with open(os.path.join(temp_dir, "test.log")) as f:
            content = f.read()

        assert "Test" in content

    def test_is_open_property(self, temp_dir):
        logger = BufferedLogger(temp_dir, "test.log")
        # Before first log, handle is None
        assert not logger.is_open

        logger.log("Test")
        assert logger.is_open

        logger.close()
        assert not logger.is_open

    def test_flush(self, temp_dir):
        logger = BufferedLogger(temp_dir, "test.log")
        logger.log("Test")
        logger.flush()

        # Should be able to read content after flush
        with open(os.path.join(temp_dir, "test.log")) as f:
            content = f.read()
        assert "Test" in content

        logger.close()

    def test_creates_output_directory(self, temp_dir):
        subdir = os.path.join(temp_dir, "logs", "subdir")
        logger = BufferedLogger(subdir, "test.log")
        logger.log("Test")
        logger.close()

        assert os.path.exists(subdir)
        assert os.path.exists(os.path.join(subdir, "test.log"))

    def test_default_filename(self, temp_dir):
        logger = BufferedLogger(temp_dir)
        assert logger.filename == "detailed_logs.txt"
        logger.log("Test")
        logger.close()

        assert os.path.exists(os.path.join(temp_dir, "detailed_logs.txt"))


class TestSummaryLogger:
    """Tests for SummaryLogger class."""

    def test_writes_summary(self, temp_dir):
        logger = SummaryLogger(temp_dir, "logs.txt")
        logger.write_summary(
            processed=[
                {"filename": "photo.jpg", "filepath": "/orig/photo.jpg",
                 "procpath": "/out/photo.jpg", "jsonpath": "/orig/photo.json",
                 "time": "2021-01-01 12:00:00"}
            ],
            unprocessed=[
                {"filename": "video.mp4", "filepath": "/orig/video.mp4",
                 "procpath": "/out/video.mp4"}
            ],
            unprocessed_jsons=[
                {"filename": "orphan.json", "filepath": "/orig/orphan.json",
                 "title": "orphan.jpg", "time": "2021-01-01 12:00:00"}
            ],
            elapsed_time=5.5,
            start_time="2021-01-01 12:00:00",
            end_time="2021-01-01 12:00:05"
        )

        with open(os.path.join(temp_dir, "logs.txt")) as f:
            content = f.read()

        assert "Processed files:" in content
        assert "photo.jpg" in content
        assert "Unprocessed files:" in content
        assert "video.mp4" in content
        assert "Unprocessed jsons:" in content
        assert "orphan.json" in content
        assert "5.5 seconds" in content

    def test_empty_sections(self, temp_dir):
        logger = SummaryLogger(temp_dir, "logs.txt")
        logger.write_summary(
            processed=[],
            unprocessed=[],
            unprocessed_jsons=[],
            elapsed_time=0.1,
            start_time="2021-01-01 12:00:00",
            end_time="2021-01-01 12:00:00"
        )

        with open(os.path.join(temp_dir, "logs.txt")) as f:
            content = f.read()

        # Should still have summary stats
        assert "Processed: 0 files" in content

    def test_default_filename(self, temp_dir):
        logger = SummaryLogger(temp_dir)
        assert logger.filepath == os.path.join(temp_dir, "logs.txt")


class TestNullLogger:
    """Tests for NullLogger class."""

    def test_log_does_nothing(self):
        logger = NullLogger()
        # Should not raise
        logger.log("Test message")

    def test_flush_does_nothing(self):
        logger = NullLogger()
        logger.flush()

    def test_close_does_nothing(self):
        logger = NullLogger()
        logger.close()

    def test_context_manager(self):
        with NullLogger() as logger:
            logger.log("Test")
        # Should not raise

    def test_is_open_always_true(self):
        logger = NullLogger()
        assert logger.is_open is True


class TestCreateLogger:
    """Tests for create_logger() factory function."""

    def test_enabled_returns_buffered_logger(self, temp_dir):
        logger = create_logger(temp_dir, enabled=True)
        assert isinstance(logger, BufferedLogger)
        logger.close()

    def test_disabled_returns_null_logger(self, temp_dir):
        logger = create_logger(temp_dir, enabled=False)
        assert isinstance(logger, NullLogger)

    def test_default_is_enabled(self, temp_dir):
        logger = create_logger(temp_dir)
        assert isinstance(logger, BufferedLogger)
        logger.close()
