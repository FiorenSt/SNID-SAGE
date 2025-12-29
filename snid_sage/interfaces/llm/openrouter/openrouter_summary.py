"""
OpenRouter Summary Generation for SNID SAGE
===========================================

Enhanced summary generation using OpenRouter's LLM API.
"""

import json
import requests
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('llm.openrouter.summary')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('llm.openrouter.summary')

from .openrouter_llm import get_openrouter_config, OPENROUTER_API_URL


# AstroSage system prompt for supernova analysis
ASTROSAGE_SYSTEM_PROMPT = """You are AstroSage, a world-renowned expert in supernova spectroscopy with decades of experience in stellar evolution, spectral analysis, and observational astronomy. You have published extensively on Type Ia, Type II, and exotic supernovae classifications.

You are analyzing results from SNID-SAGE, a spectral template matching pipeline that performs cross-correlation analysis between observed spectra and template libraries to identify supernova types and estimate redshifts.

Provide a concise, scientifically rigorous summary that includes the key classification results, confidence assessment, and main findings. Focus on the most important information for researchers and observers.

Guidelines:
- Use clear, professional astronomical terminology
- Highlight classification confidence and uncertainties
- Mention key spectral features when relevant
- Be concise but thorough
- Always respond in English
- Do NOT introduce information not present in the provided data
- Avoid converting or inferring physical quantities unless explicitly present"""


class EnhancedOpenRouterSummary:
    """Enhanced summarization interface for OpenRouter API"""
    
    def __init__(self, api_key=None, model_id=None):
        """Initialize the enhanced summarization interface"""
        # Load config if not provided
        config = get_openrouter_config()
        self.api_key = api_key or config.get('api_key')
        self.model_id = model_id or config.get('model_id') or 'openai/gpt-3.5-turbo'
        
        # Track the last generation ID and response metadata
        self.last_generation_id = None
        self.last_response_metadata = {}
    
    def generate_summary(self, data: str, analysis_type: str = 'comprehensive', 
                        custom_instructions: Optional[str] = None, max_tokens: int = 3000, 
                        temperature: float = 0.7, stream_callback=None) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
        """Generate enhanced summary with different analysis types
        
        Args:
            data: Formatted text data from SNID analysis
            analysis_type: Type of analysis ('comprehensive', 'quick_summary', 'classification_focus', 'redshift_analysis')
            custom_instructions: Custom instructions to override defaults
            max_tokens: Maximum tokens for response
            temperature: Model temperature
            stream_callback: Callback for streaming (not yet implemented)
            
        Returns:
            tuple: (summary_text, error_message, metadata)
        """
        if not self.api_key:
            return None, "API key not configured", {}
        
        if not self.model_id:
            return None, "Model not configured", {}
        
        if not data:
            return None, "Data to summarize cannot be empty", {}
        
        # Create prompt
        prompt = self._create_prompt(data, analysis_type, custom_instructions)
        
        # Prepare API request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://snid-spectrum-analyzer.io",
            "X-Title": "SNID SAGE - Supernova Analysis"
        }
        
        # Build request data
        messages = []
        if prompt.get('system'):
            messages.append({"role": "system", "content": prompt['system']})
        messages.append({"role": "user", "content": prompt['user']})
        
        request_data = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": bool(stream_callback),
            "reasoning": {
                "exclude": True  # Exclude reasoning tokens
            }
        }
        
        try:
            if stream_callback:
                _LOGGER.warning("Streaming not yet implemented for OpenRouter")
            
            return self._handle_response(headers, request_data)
                
        except Exception as e:
            _LOGGER.error(f"Error in generate_summary: {str(e)}")
            return None, f"Generation error: {str(e)}", {}
    
    def _create_prompt(self, data: str, analysis_type: str, custom_instructions: Optional[str] = None) -> Dict[str, str]:
        """Create structured prompt for the API"""
        # Use the simplified system prompt
        system_msg = ASTROSAGE_SYSTEM_PROMPT
        
        # Build the user message with clear structure
        user_msg = f"Please analyze the following supernova spectroscopy data:\n\n{data}"
        
        # Add specific formatting instructions if provided
        if custom_instructions:
            user_msg += f"\n\nSpecific formatting request: {custom_instructions}"
        
        return {
            'system': system_msg,
            'user': user_msg
        }
    
    def _handle_response(self, headers: Dict[str, str], request_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
        """Handle API response"""
        try:
            response = requests.post(OPENROUTER_API_URL, headers=headers, json=request_data, timeout=30)
            
            # Check for errors
            if response.status_code != 200:
                error_info = response.json() if response.text else {"error": "Unknown error"}
                error_message = error_info.get("error", {}).get("message", str(error_info))
                _LOGGER.error(f"API error: {error_message}")
                return None, f"API error: {error_message}", {}
            
            # Extract the response
            result = response.json()
            _LOGGER.debug(f"API response received")
            
            # Get generation ID and metadata
            generation_id = result.get('id', 'unknown')
            self.last_generation_id = generation_id
            
            # Extract metadata
            metadata = {
                'generation_id': generation_id,
                'model': result.get('model', self.model_id),
                'usage': result.get('usage', {}),
                'timestamp': datetime.now().isoformat()
            }
            self.last_response_metadata = metadata
            
            # Extract the completion
            try:
                completion_text = result["choices"][0]["message"]["content"]
                
                # Check if response was truncated
                finish_reason = result.get("choices", [{}])[0].get("finish_reason", "")
                if finish_reason == "length":
                    _LOGGER.warning("Response was truncated due to token limit")
                
                # Clean up the response
                completion_text = self._clean_response(completion_text)
                
                _LOGGER.info(f"Summary generated successfully (length: {len(completion_text)} chars)")
                return completion_text, None, metadata
                
            except (KeyError, IndexError) as e:
                _LOGGER.error(f"Error parsing API response structure: {str(e)}")
                return None, f"Could not parse response structure: {str(e)}", metadata
            
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"Network error during API call: {str(e)}")
            return None, f"Network error: {str(e)}", {}
        except Exception as e:
            _LOGGER.error(f"API call failed: {str(e)}")
            return None, f"API call failed: {str(e)}", {}
    
    def _clean_response(self, text: str) -> str:
        """Clean up the response text"""
        if not text:
            return ""
        
        # Remove any thinking tags or similar artifacts
        import re
        text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
        text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL)
        
        return text.strip()


def create_openrouter_summary(api_key=None, model_id=None):
    """Factory function to create summary instance"""
    return EnhancedOpenRouterSummary(api_key=api_key, model_id=model_id)