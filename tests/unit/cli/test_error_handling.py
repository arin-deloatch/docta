"""Unit tests for docta.cli._error_handling module."""

from __future__ import annotations

import pytest
import requests
import typer

from docta.cli._error_handling import _sanitize_error, handle_cli_errors, handle_qa_errors


class TestHandleCliErrors:
    """Tests for handle_cli_errors decorator."""

    def test_successful_function_execution(self) -> None:
        """Test that successful functions execute normally."""

        @handle_cli_errors
        def successful_func(value: int) -> int:
            return value * 2

        result = successful_func(5)
        assert result == 10

    def test_file_not_found_error(self) -> None:
        """Test handling of FileNotFoundError."""

        @handle_cli_errors
        def raises_file_not_found() -> None:
            raise FileNotFoundError("test.txt not found")

        with pytest.raises(SystemExit) as exc_info:
            raises_file_not_found()

        assert exc_info.value.code == 1

    def test_keyboard_interrupt(self) -> None:
        """Test handling of KeyboardInterrupt."""

        @handle_cli_errors
        def raises_keyboard_interrupt() -> None:
            raise KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            raises_keyboard_interrupt()

        assert exc_info.value.code == 0

    @pytest.mark.parametrize(
        "exception_type",
        [OSError, ValueError, RuntimeError],
    )
    def test_generic_exceptions(self, exception_type: type[Exception]) -> None:
        """Test handling of generic exceptions."""

        @handle_cli_errors
        def raises_generic_error() -> None:
            raise exception_type("Something went wrong")

        with pytest.raises(SystemExit) as exc_info:
            raises_generic_error()

        assert exc_info.value.code == 1

    def test_preserves_function_metadata(self) -> None:
        """Test that decorator preserves function metadata."""

        @handle_cli_errors
        def example_function() -> None:
            """Example docstring."""

        assert example_function.__name__ == "example_function"
        assert example_function.__doc__ == "Example docstring."

    def test_passes_arguments_correctly(self) -> None:
        """Test that arguments are passed correctly to wrapped function."""

        @handle_cli_errors
        def func_with_args(a: int, b: str, c: bool = False) -> tuple:
            return (a, b, c)

        result = func_with_args(42, "test", c=True)
        assert result == (42, "test", True)


class TestHandleQaErrors:
    """Tests for handle_qa_errors decorator."""

    def test_successful_function_execution(self) -> None:
        """Test that successful functions execute normally."""

        @handle_qa_errors
        def successful_func(value: str) -> str:
            return value.upper()

        result = successful_func("hello")
        assert result == "HELLO"

    def test_file_not_found_error(self) -> None:
        """Test handling of FileNotFoundError."""

        @handle_qa_errors
        def raises_file_not_found() -> None:
            raise FileNotFoundError("config.yaml not found")

        with pytest.raises(typer.Exit) as exc_info:
            raises_file_not_found()

        assert exc_info.value.exit_code == 1

    def test_value_error(self) -> None:
        """Test handling of ValueError."""

        @handle_qa_errors
        def raises_value_error() -> None:
            raise ValueError("Invalid input")

        with pytest.raises(typer.Exit) as exc_info:
            raises_value_error()

        assert exc_info.value.exit_code == 1

    def test_import_error(self) -> None:
        """Test handling of ImportError for missing dependencies."""

        @handle_qa_errors
        def raises_import_error() -> None:
            raise ImportError("Missing qa_generation module")

        with pytest.raises(typer.Exit) as exc_info:
            raises_import_error()

        assert exc_info.value.exit_code == 1

    def test_keyboard_interrupt(self) -> None:
        """Test handling of KeyboardInterrupt."""

        @handle_qa_errors
        def raises_keyboard_interrupt() -> None:
            raise KeyboardInterrupt()

        # KeyboardInterrupt is caught and converted to Exit with code 130
        with pytest.raises(typer.Exit) as exc_info:
            raises_keyboard_interrupt()

        assert exc_info.value.exit_code == 130

    def test_preserves_function_metadata(self) -> None:
        """Test that decorator preserves function metadata."""

        @handle_qa_errors
        def qa_function() -> None:
            """QA function docstring."""

        assert qa_function.__name__ == "qa_function"
        assert qa_function.__doc__ == "QA function docstring."

    def test_passes_arguments_correctly(self) -> None:
        """Test that arguments are passed correctly to wrapped function."""

        @handle_qa_errors
        def func_with_kwargs(name: str, count: int = 5) -> dict:
            return {"name": name, "count": count}

        result = func_with_kwargs("test", count=10)
        assert result == {"name": "test", "count": 10}

    def test_generic_exception_handling(self) -> None:
        """Test handling of generic exceptions."""

        @handle_qa_errors
        def raises_generic_exception() -> None:
            raise RuntimeError("Unexpected error")

        with pytest.raises(typer.Exit) as exc_info:
            raises_generic_exception()

        assert exc_info.value.exit_code == 1


class TestSanitizeError:
    """Tests for _sanitize_error helper."""

    def test_http_error_with_response_returns_status_only(self) -> None:
        """Test that HTTPError messages are reduced to the status code."""
        response = requests.Response()
        response.status_code = 401
        response.url = "https://user:secret@api.host.com/token?client_secret=abc123"
        error = requests.HTTPError("401 Unauthorized for url: https://user:secret@api.host.com/token?client_secret=abc123", response=response)

        result = _sanitize_error(error)

        assert result == "HTTP 401 error from server"
        assert "secret" not in result
        assert "user" not in result
        assert "token" not in result

    def test_http_error_without_response_returns_unknown_status(self) -> None:
        """Test that HTTPError with no response uses 'unknown' status."""
        error = requests.HTTPError("connection failed")

        result = _sanitize_error(error)

        assert result == "HTTP unknown error from server"

    def test_non_http_error_returns_str(self) -> None:
        """Test that non-HTTP exceptions pass through as str(e)."""
        error = ValueError("bad value")

        assert _sanitize_error(error) == "bad value"

    def test_http_error_sanitized_in_handle_cli_errors(self, capsys) -> None:
        """Test that HTTPError is sanitized before reaching stderr."""
        sentinel = "xyzSensitiveToken99"
        response = requests.Response()
        response.status_code = 403
        response.url = f"https://api.host.com/token?access_token={sentinel}"

        @handle_cli_errors
        def raises_http_error() -> None:
            raise requests.HTTPError(response=response)

        with pytest.raises(SystemExit):
            raises_http_error()

        captured = capsys.readouterr()
        assert sentinel not in captured.err
        assert "HTTP 403" in captured.err


class TestErrorHandlerIntegration:
    """Integration tests for error handlers."""

    def test_nested_decorators(self) -> None:
        """Test that decorators can be nested if needed."""

        def custom_decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        @custom_decorator
        @handle_cli_errors
        def decorated_function(x: int) -> int:
            return x + 1

        result = decorated_function(5)
        assert result == 6

    def test_multiple_error_types_in_sequence(self) -> None:
        """Test handling multiple different error types."""
        errors_to_test = [
            FileNotFoundError("file.txt"),
            ValueError("bad value"),
            RuntimeError("runtime issue"),
        ]

        def create_error_raiser(exc: Exception):
            """Create a function that raises the given exception."""

            @handle_cli_errors
            def raises_error() -> None:
                raise exc

            return raises_error

        for error in errors_to_test:
            error_func = create_error_raiser(error)
            with pytest.raises(SystemExit):
                error_func()
