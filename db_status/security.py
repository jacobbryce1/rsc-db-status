"""
db_status/security.py

Shared security utilities used across runners and reports.

SECURITY F-02: safe_input_path() prevents path traversal on --input args.
SECURITY F-05: secure_open_write() sets 0o600 permissions on all output files.
"""
import os
import pathlib


def safe_input_path(user_path: str, work_dir: str) -> str:
    """
    Resolve and validate that user_path is within work_dir.
    Raises ValueError on path traversal attempts.

    SECURITY F-02: prevents --input ../../../../etc/passwd style attacks.
    """
    work_dir_resolved  = pathlib.Path(work_dir).resolve()
    user_path_resolved = pathlib.Path(user_path).resolve()

    try:
        user_path_resolved.relative_to(work_dir_resolved)
    except ValueError:
        raise ValueError(
            f"Invalid --input path: '{user_path}' is outside the work "
            f"directory '{work_dir}'. Only files within the work directory "
            "are permitted."
        )

    if not user_path_resolved.exists():
        raise FileNotFoundError(f"Input file not found: {user_path}")

    if not user_path_resolved.is_file():
        raise ValueError(
            f"--input must point to a file, not a directory: {user_path}"
        )

    return str(user_path_resolved)


def secure_open_write(path: str, encoding: str = "utf-8"):
    """
    Open a file for writing and immediately set permissions to 0o600
    so no other OS user can read the output.

    SECURITY F-05: prevents sensitive report data being world-readable.

    Usage:
        with secure_open_write("report.json") as f:
            json.dump(data, f)
    """
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    return os.fdopen(fd, "w", encoding=encoding)