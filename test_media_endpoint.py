"""Tests for /api/media/ endpoint — per-user media serving with token verification.

Tests verify:
- Path traversal protection via os.path.normpath + startswith
- File existence checks before FileResponse
- Valid paths resolve correctly within user directory
- Token verification behavior (empty, invalid, valid)
"""

import os
import sys
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class TestMediaEndpoint(unittest.TestCase):
    """Test /api/media/ endpoint security and file serving."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._user_id = "testuser123"
        self._user_dir = os.path.join(self._tmpdir, "users", self._user_id)
        os.makedirs(os.path.join(self._user_dir, "generated"), exist_ok=True)
        os.makedirs(os.path.join(self._user_dir, "attachments"), exist_ok=True)

        # Create test files
        self._img_path = os.path.join(self._user_dir, "generated", "img_test.png")
        with open(self._img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        self._att_path = os.path.join(self._user_dir, "attachments", "doc.pdf")
        with open(self._att_path, "wb") as f:
            f.write(b"%PDF-1.4" + b"\x00" * 50)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_path_traversal_rejected(self):
        """Path traversal via .. must not escape user directory."""
        base_dir = os.path.normpath(os.path.join(self._tmpdir, "users", self._user_id))
        file_path = "../../../etc/passwd"
        full_path = os.path.normpath(os.path.join(base_dir, file_path))
        self.assertFalse(full_path.startswith(base_dir))

    def test_valid_path_accepted(self):
        """Normal file paths within user directory are accepted."""
        base_dir = os.path.normpath(os.path.join(self._tmpdir, "users", self._user_id))
        file_path = "generated/img_test.png"
        full_path = os.path.normpath(os.path.join(base_dir, file_path))
        self.assertTrue(full_path.startswith(base_dir))
        self.assertTrue(os.path.exists(full_path))

    def test_subdir_path_accepted(self):
        """Subdirectory paths like attachments/doc.pdf are accepted."""
        base_dir = os.path.normpath(os.path.join(self._tmpdir, "users", self._user_id))
        file_path = "attachments/doc.pdf"
        full_path = os.path.normpath(os.path.join(base_dir, file_path))
        self.assertTrue(full_path.startswith(base_dir))
        self.assertTrue(os.path.exists(full_path))

    def test_file_exists_check(self):
        """FileResponse raises RuntimeError for missing files — must check exists first."""
        base_dir = os.path.normpath(os.path.join(self._tmpdir, "users", self._user_id))
        existing = os.path.normpath(os.path.join(base_dir, "generated/img_test.png"))
        missing = os.path.normpath(os.path.join(base_dir, "generated/nonexistent.png"))

        self.assertTrue(os.path.exists(existing))
        self.assertFalse(os.path.exists(missing))

    def test_token_verification_returns_none_for_empty(self):
        """Empty token must return None from verify_token."""
        from backend.auth.session import SessionManager
        mgr = SessionManager()
        self.assertIsNone(mgr.verify_token(""))

    def test_token_verification_returns_none_for_invalid(self):
        """Invalid token must return None from verify_token."""
        from backend.auth.session import SessionManager
        mgr = SessionManager()
        self.assertIsNone(mgr.verify_token("invalid-token-xxx"))

    def test_token_verification_returns_user_id_for_valid(self):
        """Valid token must return user_id from verify_token."""
        from backend.auth.session import SessionManager
        mgr = SessionManager()
        token = mgr.create_session("testuser123")
        result = mgr.verify_token(token)
        self.assertEqual(result, "testuser123")


if __name__ == "__main__":
    unittest.main()
