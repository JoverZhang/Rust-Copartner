"""Tests for llm_client module"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.llm_client import LLMClient, LLMConfig, LLMResponse
from tests.mocks.mock_llm_responses import mock_llm_call


class TestLLMConfig:
    def test_from_env(self, mock_env):
        """Test creating LLM config from environment variables"""
        with patch.dict('os.environ', mock_env):
            config = LLMConfig.from_env()
            
            assert config.api_key == "test-api-key"
            assert config.base_url == "https://openrouter.ai/api/v1"
            assert config.model == "deepseek/deepseek-r1:free"
    
    def test_from_env_missing_key(self):
        """Test error when API key is missing"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY not found"):
                LLMConfig.from_env()
    
    def test_from_env_defaults(self):
        """Test default values when optional env vars are missing"""
        env = {"OPENROUTER_API_KEY": "test-key"}
        with patch.dict('os.environ', env, clear=True):
            config = LLMConfig.from_env()
            
            assert config.api_key == "test-key"
            assert config.base_url == "https://openrouter.ai/api/v1"  # default
            assert config.model == "deepseek/deepseek-r1:free"  # default


class TestLLMClient:
    @pytest.fixture
    def llm_config(self):
        return LLMConfig(
            api_key="test-api-key",
            base_url="https://openrouter.ai/api/v1",
            model="deepseek/deepseek-r1:free"
        )
    
    @pytest.fixture
    def mock_client(self, llm_config):
        return LLMClient(config=llm_config, use_mock=True)
    
    @pytest.fixture
    def real_client(self, llm_config):
        return LLMClient(config=llm_config, use_mock=False)
    
    def test_client_initialization_mock(self, mock_client):
        """Test client initializes correctly with mock enabled"""
        assert mock_client.use_mock is True
        assert mock_client.config.api_key == "test-api-key"
        assert mock_client.openai_client is None  # Should not initialize real client in mock mode
    
    def test_client_initialization_real(self, real_client):
        """Test client initializes correctly with real mode"""
        assert real_client.use_mock is False
        assert real_client.openai_client is not None
    
    @pytest.mark.asyncio
    async def test_generate_mock_response(self, mock_client):
        """Test generating response in mock mode"""
        prompt = "Based on the diff showing Point -> Point3D rename, suggest improvements"
        
        response = await mock_client.generate(prompt)
        
        assert isinstance(response, LLMResponse)
        assert response.content is not None
        assert len(response.content) > 0
        assert response.model == "mock-model"
        assert response.usage is not None
    
    @pytest.mark.asyncio
    async def test_generate_mock_struct_rename(self, mock_client):
        """Test mock response for struct rename scenario"""
        prompt = "diff showing Point to Point3D rename"
        
        response = await mock_client.generate(prompt)
        
        assert "Point3D" in response.content
        assert "---" in response.content and "+++" in response.content  # Check for diff format
    
    @pytest.mark.asyncio
    async def test_generate_with_system_message(self, mock_client):
        """Test generating response with system message"""
        system_message = "You are a Rust code assistant"
        prompt = "Help with Point to Point3D refactoring"
        
        response = await mock_client.generate(prompt, system_message=system_message)
        
        assert isinstance(response, LLMResponse)
        assert response.content is not None
    
    @pytest.mark.asyncio
    async def test_generate_with_temperature(self, mock_client):
        """Test generating response with custom temperature"""
        prompt = "test prompt"
        
        response = await mock_client.generate(prompt, temperature=0.7)
        
        assert isinstance(response, LLMResponse)
        assert response.content is not None
    
    @pytest.mark.asyncio
    async def test_generate_real_mode_success(self, real_client):
        """Test generating response in real mode (mocked OpenAI call)"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is a real response"
        mock_response.model = "deepseek/deepseek-r1:free"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        
        with patch.object(real_client.openai_client.chat.completions, 'create', 
                         return_value=mock_response):
            response = await real_client.generate("test prompt")
            
            assert response.content == "This is a real response"
            assert response.model == "deepseek/deepseek-r1:free"
            assert response.usage["prompt_tokens"] == 10
            assert response.usage["completion_tokens"] == 5
            assert response.usage["total_tokens"] == 15
    
    @pytest.mark.asyncio
    async def test_generate_real_mode_error_handling(self, real_client):
        """Test error handling in real mode"""
        with patch.object(real_client.openai_client.chat.completions, 'create', 
                         side_effect=Exception("API Error")):
            with pytest.raises(Exception, match="API Error"):
                await real_client.generate("test prompt")
    
    def test_toggle_mock_mode(self, llm_config):
        """Test toggling between mock and real mode"""
        client = LLMClient(config=llm_config, use_mock=True)
        assert client.use_mock is True
        
        client.set_mock_mode(False)
        assert client.use_mock is False
        assert client.openai_client is not None
        
        client.set_mock_mode(True)
        assert client.use_mock is True
    
    @pytest.mark.asyncio
    async def test_batch_generate_mock(self, mock_client):
        """Test batch generation in mock mode"""
        prompts = [
            "First prompt about Point to Point3D",
            "Second prompt about function rename"
        ]
        
        responses = await mock_client.batch_generate(prompts)
        
        assert len(responses) == 2
        for response in responses:
            assert isinstance(response, LLMResponse)
            assert response.content is not None
    
    @pytest.mark.asyncio
    async def test_estimate_tokens(self, mock_client):
        """Test token estimation"""
        prompt = "This is a test prompt for token estimation"
        
        tokens = mock_client.estimate_tokens(prompt)
        
        assert isinstance(tokens, int)
        assert tokens > 0
    
    def test_client_from_env(self, mock_env):
        """Test creating client from environment variables"""
        with patch.dict('os.environ', mock_env):
            client = LLMClient.from_env(use_mock=True)
            
            assert client.config.api_key == "test-api-key"
            assert client.use_mock is True