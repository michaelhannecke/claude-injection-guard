"""Tests for the injection guard logger."""

from guard.logger import setup_logger


class TestLogger:
    def test_logger_writes_to_stderr(self, capsys):
        logger = setup_logger({"level": "INFO"})
        logger.info("test message to stderr")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "test message to stderr" in captured.err

    def test_logger_never_writes_to_stdout(self, capsys):
        logger = setup_logger({"level": "DEBUG"})
        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warning msg")
        logger.error("error msg")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_logger_respects_level(self, capsys):
        logger = setup_logger({"level": "WARNING"})
        logger.info("should not appear")
        logger.warning("should appear")
        captured = capsys.readouterr()
        assert "should not appear" not in captured.err
        assert "should appear" in captured.err

    def test_logger_file_handler(self, tmp_path):
        log_file = tmp_path / "guard.log"
        logger = setup_logger({"level": "INFO", "file": str(log_file)})
        logger.info("file test message")
        # Flush handlers
        for handler in logger.handlers:
            handler.flush()
        content = log_file.read_text()
        assert "file test message" in content
