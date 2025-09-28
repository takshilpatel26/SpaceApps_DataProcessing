"""Tests for intensity processor."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.sar_processor.processors.intensity_processor import IntensityProcessor
from src.sar_processor.config.settings import ProcessingConfig


class TestIntensityProcessor:
    """Test suite for IntensityProcessor."""

    @pytest.fixture
    def config(self):
        return ProcessingConfig()

    @pytest.fixture
    def processor(self, config):
        return IntensityProcessor(config)

    def test_initialization(self, processor):
        """Test processor initialization."""
        assert processor.config is not None
        assert isinstance(processor.config, ProcessingConfig)

    @patch('src.sar_processor.processors.intensity_processor.ProductIO')
    def test_process_intensity_maps_success(self, mock_product_io, processor, tmp_path):
        """Test successful intensity map processing."""
        # Mock setup
        mock_product = Mock()
        mock_product_io.readProduct.return_value = mock_product

        # Test file paths
        input_file = tmp_path / "S1A_IW_SLC__1SDV_20240720T004052.zip"
        input_file.touch()  # Create empty test file
        output_dir = tmp_path / "output"

        # This would need more sophisticated mocking for real tests
        # but demonstrates the testing approach
