import pytest
import os
import json
from datetime import datetime
from cytaxii2.cytaxii2 import cytaxii2

class TestCytaxii2:
    @pytest.fixture
    def taxii_client(self):
        """Create a test TAXII client"""
        return cytaxii2(
            discovery_url="https://test.taxii.server/taxii2",
            username="test_user",
            password="test_pass"
        )

    @pytest.fixture
    def mock_indicator_response(self):
        """Create a mock indicator response"""
        return {
            'status': True,
            'response': {
                'objects': [{
                    'type': 'indicator',
                    'id': 'test-indicator--1234',
                    'created': '2024-01-01T00:00:00Z',
                    'modified': '2024-01-01T00:00:00Z',
                    'pattern': '[file:hashes.md5 = "d41d8cd98f00b204e9800998ecf8427e"]',
                    'valid_from': '2024-01-01T00:00:00Z'
                }]
            }
        }

    def test_download_indicator_default_filename(self, taxii_client, mocker, mock_indicator_response):
        """Test downloading indicator with default filename"""
        mocker.patch.object(taxii_client, 'poll_request', return_value=mock_indicator_response)
        
        collection_id = "test-collection"
        object_id = "test-indicator--1234"
        
        result = taxii_client.download_indicator(collection_id, object_id)
        assert result == True
        
        # Verify file was created with expected naming pattern
        files = [f for f in os.listdir('.') if f.startswith('indicator_') and 
                                               f.endswith('.txt') and 
                                               'test_collection' in f and 
                                               'test_indicator__1234' in f]
        assert len(files) == 1
        
        # Verify file contents
        with open(files[0], 'r') as f:
            content = json.load(f)
            assert content['type'] == 'indicator'
            assert content['id'] == 'test-indicator--1234'
        
        # Clean up
        os.remove(files[0])

    def test_download_indicator_custom_filename(self, taxii_client, mocker, mock_indicator_response):
        """Test downloading indicator with custom filename"""
        mocker.patch.object(taxii_client, 'poll_request', return_value=mock_indicator_response)
        
        custom_filename = "custom_indicator.txt"
        result = taxii_client.download_indicator("test-collection", "test-indicator--1234", filename=custom_filename)
        assert result == True
        assert os.path.exists(custom_filename)
        
        # Verify file contents
        with open(custom_filename, 'r') as f:
            content = json.load(f)
            assert content['type'] == 'indicator'
            assert content['id'] == 'test-indicator--1234'
        
        # Clean up
        os.remove(custom_filename)

    def test_download_indicator_failure_no_data(self, taxii_client, mocker):
        """Test handling of empty response data"""
        mock_response = {
            'status': True,
            'response': {'objects': []}
        }
        mocker.patch.object(taxii_client, 'poll_request', return_value=mock_response)
        
        result = taxii_client.download_indicator("test-collection", "test-indicator--1234")
        assert result == False

    def test_download_indicator_invalid_inputs(self, taxii_client):
        """Test input validation"""
        with pytest.raises(ValueError, match="collection_id cannot be empty"):
            taxii_client.download_indicator("", "test-indicator--1234")
        
        with pytest.raises(ValueError, match="object_id cannot be empty"):
            taxii_client.download_indicator("test-collection", "")

    def test_download_indicator_request_failure(self, taxii_client, mocker):
        """Test handling of failed request"""
        mock_response = {
            'status': False,
            'response': 'Error fetching indicator'
        }
        mocker.patch.object(taxii_client, 'poll_request', return_value=mock_response)
        
        result = taxii_client.download_indicator("test-collection", "test-indicator--1234")
        assert result == False 