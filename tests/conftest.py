import sys
import os
import pytest

# Make scrape.py importable from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def tmp_output(tmp_path):
    """Temporary directory tree matching scrape.py output structure."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "items").mkdir()
    (data / "temp").mkdir()
    return tmp_path


@pytest.fixture
def mock_toc_response():
    """Factory for mock TOC HTTP responses with N items."""
    def _make(n_items):
        from unittest.mock import MagicMock
        items_xml = "".join(
            f"<item><link>https://example.com/law{i}/xml.zip</link></item>"
            for i in range(n_items)
        )
        xml = f"<?xml version='1.0'?><root>{items_xml}</root>"
        mock = MagicMock()
        mock.content = xml.encode()
        mock.text = xml
        return mock
    return _make
