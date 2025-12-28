"""
OpenRouter API integration for SNID Spectrum Analyzer

This module provides the OpenRouter LLM integration with all functions
needed for the SNID SAGE GUI.
"""
import os
import re
import json
import requests
from datetime import datetime

# Import centralized logging system
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('llm.openrouter')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('llm.openrouter')

# OpenRouter API endpoints
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Default free model if nothing else works (must remain a free variant).
# OpenRouter model IDs change over time; do not rely on this always existing.
DEFAULT_MODEL = "deepseek/deepseek-chat-v3-0324:free"


def _get_openrouter_config_dir() -> str:
    """
    Return the directory where OpenRouter config is stored.

    By default this is ``<state_root>/LLM`` where ``state_root`` is
    resolved via :func:`snid_sage.shared.utils.paths.state_root.get_state_root_dir`,
    typically a ``SNID_SAGE`` subdirectory of the current working directory.
    Advanced users can still override the root via ``SNID_SAGE_STATE_DIR``.
    """
    try:
        from snid_sage.shared.utils.paths.state_root import get_state_root_dir

        return str(get_state_root_dir() / "LLM")
    except Exception:
        # Fallback: keep config next to the current working directory
        return os.path.join(os.getcwd(), "SNID_SAGE", "LLM")


def get_openrouter_api_key():
    """Get OpenRouter API key from secure storage or config file"""
    # Try secure storage first
    try:
        from snid_sage.shared.utils.secure_storage import retrieve_api_key
        api_key = retrieve_api_key("openrouter")
        if api_key:
            return api_key
    except ImportError:
        _LOGGER.debug("Secure storage not available, using config storage")
    except Exception as e:
        _LOGGER.warning(f"Failed to retrieve from secure storage: {e}")
    
    # Fallback to config file
    config_path = os.path.join(_get_openrouter_config_dir(), "openrouter_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get('api_key')
                
                # Migrate to secure storage if available
                if api_key:
                    try:
                        from snid_sage.shared.utils.secure_storage import store_api_key
                        if store_api_key("openrouter", api_key):
                            _LOGGER.info("Migrated API key to secure storage")
                            # Remove from config file for security
                            config.pop('api_key', None)
                            with open(config_path, 'w') as f:
                                json.dump(config, f)
                    except ImportError:
                        pass
                    except Exception as e:
                        _LOGGER.warning(f"Failed to migrate API key to secure storage: {e}")
                
                return api_key
        except (json.JSONDecodeError, IOError):
            pass

    return None


def save_openrouter_api_key(api_key):
    """Save OpenRouter API key using secure storage"""
    if not api_key or not api_key.strip():
        _LOGGER.warning("Empty API key provided, skipping save")
        return
    
    # Try secure storage first
    try:
        from snid_sage.shared.utils.secure_storage import store_api_key
        if store_api_key("openrouter", api_key.strip()):
            _LOGGER.info("OpenRouter API key saved to secure storage")
            return
    except ImportError:
        _LOGGER.debug("Secure storage not available, using config storage")
    except Exception as e:
        _LOGGER.warning(f"Failed to save to secure storage: {e}")
    
    # Fallback to config file (but don't store API key in plain text)
    config_dir = _get_openrouter_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    
    config_path = os.path.join(config_dir, "openrouter_config.json")
    
    # Load existing config if it exists
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            _LOGGER.warning("Could not load existing OpenRouter config file")
    
    # Don't store API key in plain text - just mark that one exists
    config['api_key_exists'] = True
    config['api_key_storage'] = 'legacy_fallback'
    
    # Save updated config
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f)
        _LOGGER.warning("OpenRouter API key saved to config storage (consider installing cryptography for secure storage)")
    except IOError as e:
        _LOGGER.error(f"Failed to save OpenRouter API key: {e}")
        raise


def save_openrouter_config(api_key, model_id, model_name=None, is_tested=False):
    """Save OpenRouter config to file with enhanced model information"""
    config_dir = _get_openrouter_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    
    config_path = os.path.join(config_dir, "openrouter_config.json")
    
    # Load existing config if it exists
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            _LOGGER.warning("Could not load existing OpenRouter config file")
    
    # Update config with new values
    if api_key:
        # Don't store API key in plain text anymore - it's handled by secure storage
        config['api_key_exists'] = True
    if model_id:
        config['model_id'] = model_id
        config['model_name'] = model_name or model_id
        config['model_tested'] = is_tested
        config['last_updated'] = datetime.now().isoformat()
    
    # Save updated config
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        _LOGGER.info(f"OpenRouter configuration saved successfully (model: {model_name or model_id})")
    except IOError as e:
        _LOGGER.error(f"Failed to save OpenRouter configuration: {e}")
        raise


def get_model_test_status(model_id):
    """Get the test status of a specific model"""
    config = get_openrouter_config()
    if config.get('model_id') == model_id:
        return config.get('model_tested', False)
    return False


def set_model_test_status(model_id, model_name=None, is_tested=True):
    """Set the test status of a specific model"""
    config = get_openrouter_config()
    api_key = get_openrouter_api_key()  # Get from secure storage
    save_openrouter_config(api_key, model_id, model_name, is_tested)


def get_openrouter_config():
    """Get saved OpenRouter configuration"""
    config_path = os.path.join(_get_openrouter_config_dir(), "openrouter_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            _LOGGER.warning("Could not load OpenRouter config file")
    return {}


def strip_thinking(text):
    """Remove thinking tags from AI responses"""
    # Remove thinking blocks
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove reasoning blocks  
    text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Clean up extra whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    return text.strip()


def fetch_all_models(api_key=None, free_only=False):
    """Fetch all available models from OpenRouter with enhanced information"""
    if not api_key:
        api_key = get_openrouter_api_key()
    
    if not api_key:
        _LOGGER.error("No API key available for fetching models")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(OPENROUTER_MODELS_URL, headers=headers)
        
        if response.status_code == 200:
            models_data = response.json()
            all_models = []
            
            for model in models_data.get("data", []):
                model_id = model.get("id", "")
                model_name = model.get("name", "")
                
                # Get pricing information
                pricing = model.get("pricing", {})
                prompt_price = float(pricing.get("prompt", "0")) 
                completion_price = float(pricing.get("completion", "0"))
                
                # Determine if model is free
                is_free = "(free)" in model_name.lower() or (prompt_price == 0 and completion_price == 0)
                
                # Skip non-free models if free_only is True
                if free_only and not is_free:
                    continue
                
                # Get model capabilities
                context_length = model.get("context_length", 4096)
                formatted_context = format_context_length(context_length)
                
                supported_params = model.get("supported_parameters", [])
                supports_reasoning = "reasoning" in supported_params if supported_params else False
                
                # Clean up display name
                display_name = model_name.replace(" (free)", "") if "(free)" in model_name else model_name
                
                # Format pricing for display
                if is_free:
                    price_display = "Free"
                else:
                    price_display = f"${prompt_price:.6f}/${completion_price:.6f}"
                
                all_models.append({
                    "id": model_id,
                    "name": display_name,
                    "context_length": context_length,
                    "context_display": formatted_context,
                    "supports_reasoning": supports_reasoning,
                    "is_free": is_free,
                    "prompt_price": prompt_price,
                    "completion_price": completion_price,
                    "price_display": price_display,
                    "provider": model_id.split("/")[0] if "/" in model_id else "Unknown"
                })
            
            _LOGGER.info(f"Successfully fetched {len(all_models)} models from OpenRouter")
            return all_models
        else:
            _LOGGER.error(f"Failed to fetch models from OpenRouter: {response.status_code}")
            return None
    except Exception as e:
        _LOGGER.error(f"Error fetching models: {str(e)}")
        return None


def fetch_free_models(api_key=None):
    """Fetch available free models from OpenRouter"""
    if not api_key:
        api_key = get_openrouter_api_key()
    
    if not api_key:
        _LOGGER.error("No API key available for fetching models")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(OPENROUTER_MODELS_URL, headers=headers)
        
        if response.status_code == 200:
            models_data = response.json()
            free_models = []
            
            for model in models_data.get("data", []):
                model_id = model.get("id", "")
                model_name = model.get("name", "")
                
                # Pricing
                pricing = model.get("pricing", {})
                prompt_price = float(pricing.get("prompt", "1"))
                completion_price = float(pricing.get("completion", "1"))
                
                # Determine if model is free
                is_free = "(free)" in model_name.lower() or (prompt_price == 0 and completion_price == 0)
                if not is_free:
                    continue
                
                # Context length
                context_length = model.get("context_length", 4096)
                formatted_context = format_context_length(context_length)
                
                # Capabilities
                supported_params = model.get("supported_parameters", [])
                supports_reasoning = "reasoning" in supported_params if supported_params else False
                
                # Clean display name
                display_name = model_name.replace(" (free)", "") if "(free)" in model_name else model_name
                
                # Price display
                price_display = "Free" if is_free else f"${prompt_price:.6f}/${completion_price:.6f}"
                
                free_models.append({
                    "id": model_id,
                    "name": display_name,
                    "context_length": context_length,
                    "context_display": formatted_context,
                    "supports_reasoning": supports_reasoning,
                    "is_free": True,
                    "prompt_price": 0.0,
                    "completion_price": 0.0,
                    "price_display": price_display,
                    "provider": model_id.split("/")[0] if "/" in model_id else "Unknown",
                })
            
            _LOGGER.info(f"Successfully fetched {len(free_models)} free models from OpenRouter")
            return free_models
        else:
            _LOGGER.error(f"API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        _LOGGER.error(f"Error fetching models: {str(e)}")
        return None


def _extract_openrouter_error_message(response: requests.Response) -> str:
    """Best-effort extraction of an OpenRouter error message."""
    try:
        if response is None:
            return ""
        if not getattr(response, "text", None):
            return ""
        payload = response.json()
        # OpenRouter typically responds with {"error": {"message": "..."}}
        if isinstance(payload, dict):
            err = payload.get("error", {})
            if isinstance(err, dict):
                msg = err.get("message")
                if isinstance(msg, str):
                    return msg
            # Fallback: sometimes nested differently
            msg = payload.get("message")
            if isinstance(msg, str):
                return msg
        return str(payload)
    except Exception:
        try:
            return (response.text or "").strip()
        except Exception:
            return ""


def _is_model_not_found_response(response: requests.Response) -> bool:
    """Return True if OpenRouter indicates the selected model does not exist/ isn't available."""
    try:
        if response is None:
            return False
        if getattr(response, "status_code", None) == 404:
            return True
        msg = _extract_openrouter_error_message(response).lower()
        return ("model" in msg) and ("not found" in msg or "no such model" in msg)
    except Exception:
        return False


def _pick_best_free_model(api_key: str, exclude_ids=None):
    """
    Pick an available free model from OpenRouter.

    Returns:
        tuple[str, str] | None: (model_id, model_name) or None if none can be fetched.
    """
    exclude = set(exclude_ids or [])
    models = fetch_free_models(api_key)
    if not models:
        return None

    candidates = [m for m in models if m.get("id") and m.get("id") not in exclude]
    if not candidates:
        candidates = [m for m in models if m.get("id")]
    if not candidates:
        return None

    # Prefer larger context and (secondarily) models that advertise reasoning support.
    candidates.sort(
        key=lambda m: (
            int(m.get("context_length") or 0),
            1 if m.get("supports_reasoning") else 0,
            str(m.get("name") or ""),
        ),
        reverse=True,
    )
    best = candidates[0]
    return best["id"], (best.get("name") or best["id"])


def format_context_length(length):
    """Format context length to be more readable"""
    try:
        length = int(length)
        if length >= 1000000:
            return f"{length/1000000:.1f}M"
        elif length >= 1000:
            return f"{length/1000:.0f}K"
        else:
            return str(length)
    except (ValueError, TypeError):
        return str(length)


def configure_openrouter_dialog(parent):
    """Show dialog to configure OpenRouter settings"""
    # Import here to avoid circular imports
    try:
        import PySide6.QtWidgets as QtWidgets
        import PySide6.QtCore as QtCore
        
        # Create PySide6 dialog
        dialog = QtWidgets.QDialog(parent)
        dialog.setWindowTitle("Configure OpenRouter")
        dialog.resize(800, 600)
        dialog.setModal(True)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Title
        title_label = QtWidgets.QLabel("OpenRouter API Configuration")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Description
        desc_label = QtWidgets.QLabel(
            "OpenRouter provides access to various LLM models for enhanced AI analysis features. "
            "This is optional but enables powerful AI summaries and chat functionality."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("margin-bottom: 20px;")
        layout.addWidget(desc_label)
        
        # API Key input
        api_group = QtWidgets.QGroupBox("API Configuration")
        api_layout = QtWidgets.QFormLayout(api_group)
        
        current_api_key = get_openrouter_api_key() or ""
        api_key_input = QtWidgets.QLineEdit(current_api_key)
        api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        api_layout.addRow("API Key:", api_key_input)
        
        # Show/hide toggle
        show_key_btn = QtWidgets.QPushButton("Show")
        show_key_btn.setFixedWidth(60)
        
        def toggle_show_key():
            if api_key_input.echoMode() == QtWidgets.QLineEdit.Password:
                api_key_input.setEchoMode(QtWidgets.QLineEdit.Normal)
                show_key_btn.setText("Hide")
            else:
                api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
                show_key_btn.setText("Show")
        
        show_key_btn.clicked.connect(toggle_show_key)
        
        key_layout = QtWidgets.QHBoxLayout()
        key_layout.addWidget(api_key_input)
        key_layout.addWidget(show_key_btn)
        api_layout.addRow("API Key:", key_layout)
        
        layout.addWidget(api_group)
        
        # Model selection
        model_group = QtWidgets.QGroupBox("Model Selection")
        model_layout = QtWidgets.QVBoxLayout(model_group)
        
        model_list = QtWidgets.QListWidget()
        model_layout.addWidget(model_list)
        
        fetch_btn = QtWidgets.QPushButton("Fetch Available Models")
        model_layout.addWidget(fetch_btn)
        
        layout.addWidget(model_group)
        
        # Status label
        status_label = QtWidgets.QLabel("Ready")
        layout.addWidget(status_label)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        save_btn = QtWidgets.QPushButton("Save Configuration")
        save_btn.setDefault(True)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        def fetch_models():
            api_key = api_key_input.text().strip()
            if not api_key:
                status_label.setText("Please enter an API key first")
                return
            
            status_label.setText("Fetching models...")
            models = fetch_free_models(api_key)
            
            if models:
                model_list.clear()
                for model in models:
                    item_text = f"{model['name']} (Context: {model['context_length']})"
                    item = QtWidgets.QListWidgetItem(item_text)
                    item.setData(QtCore.Qt.UserRole, model['id'])
                    model_list.addItem(item)
                status_label.setText(f"Found {len(models)} free models")
            else:
                status_label.setText("Failed to fetch models")
        
        def save_config():
            api_key = api_key_input.text().strip()
            if not api_key:
                status_label.setText("Please enter an API key")
                return
            
            selected_items = model_list.selectedItems()
            model_id = None
            if selected_items:
                model_id = selected_items[0].data(QtCore.Qt.UserRole)
            
            try:
                save_openrouter_config(api_key, model_id)
                dialog.accept()
            except Exception as e:
                status_label.setText(f"Error saving config: {e}")
        
        fetch_btn.clicked.connect(fetch_models)
        save_btn.clicked.connect(save_config)
        cancel_btn.clicked.connect(dialog.reject)
        
        return dialog.exec() == QtWidgets.QDialog.Accepted
        
    except ImportError:
        # PySide6 not available; no GUI configuration
        return False


## GUI-only implementation; no GUI fallback


def call_openrouter_api(prompt, max_tokens=2000):
    """Call the OpenRouter API with the given prompt"""
    config = get_openrouter_config()

    # Always prefer secure storage for the API key; fall back to config only if present
    try:
        api_key = get_openrouter_api_key()
    except Exception:
        api_key = None
    if not api_key:
        api_key = config.get('api_key')  # backward compatibility

    model_id = config.get('model_id')
    
    if not api_key:
        _LOGGER.error("OpenRouter API key not configured")
        raise ValueError("OpenRouter API key not configured")

    # If no model is configured, auto-select an available free model (and persist it),
    # instead of relying on a potentially stale hardcoded DEFAULT_MODEL.
    if not model_id:
        picked = _pick_best_free_model(api_key)
        if picked:
            model_id, model_name = picked
            _LOGGER.info(f"No model configured; auto-selected free model: {model_id}")
            try:
                api_key_for_save = get_openrouter_api_key() or api_key
            except Exception:
                api_key_for_save = api_key
            try:
                save_openrouter_config(api_key_for_save, model_id, model_name, False)
            except Exception:
                pass
        else:
            model_id = DEFAULT_MODEL
            _LOGGER.warning(
                f"No model configured and could not fetch models; falling back to built-in default: {model_id}"
            )
    else:
        _LOGGER.info(f"Using configured model: {model_id}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://snid-spectrum-analyzer.io",
        "X-Title": "SNID SAGE"
    }
    
    # Set up the API request parameters
    # Do NOT fall back to a paid non-free model. When a free model is selected, keep routing within that model only.
    data = {
        "model": model_id,
        # Keep provider fallbacks for the chosen model, but do not change models implicitly
        "route": "fallback",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "include_reasoning": False,
        "reasoning": {"exclude": True}
    }
    
    try:
        _LOGGER.debug(f"Sending request to OpenRouter API with model: {model_id}")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data)

        # Handle different error cases
        if response.status_code == 401:
            _LOGGER.error("OpenRouter API key is invalid or expired")
            raise ValueError("API key is invalid or expired")
        elif _is_model_not_found_response(response):
            # Model not found; fall back to an available free model fetched live from /models.
            _LOGGER.error(f"Model '{model_id}' not found on OpenRouter")

            picked = _pick_best_free_model(api_key, exclude_ids=[model_id])
            if not picked:
                msg = _extract_openrouter_error_message(response)
                raise ValueError(
                    f"Model '{model_id}' not found. Also failed to fetch an alternative free model from OpenRouter. "
                    f"Please open the AI/OpenRouter settings, click 'Fetch Available Models', and select a model. "
                    f"OpenRouter message: {msg or '(no details)'}"
                )

            fallback_model_id, fallback_model_name = picked
            _LOGGER.info(f"Falling back to available free model: {fallback_model_id}")

            try:
                api_key_for_save = get_openrouter_api_key() or api_key
            except Exception:
                api_key_for_save = api_key
            try:
                save_openrouter_config(api_key_for_save, fallback_model_id, fallback_model_name, False)
            except Exception:
                pass

            data["model"] = fallback_model_id
            response = requests.post(OPENROUTER_API_URL, headers=headers, json=data)
            if _is_model_not_found_response(response):
                msg = _extract_openrouter_error_message(response)
                raise ValueError(
                    f"Model '{model_id}' not found, and fallback model '{fallback_model_id}' also appears unavailable. "
                    f"Please fetch models in settings and pick a different one. "
                    f"OpenRouter message: {msg or '(no details)'}"
                )
            elif response.status_code >= 400:
                error_message = _extract_openrouter_error_message(response)
                _LOGGER.error(f"OpenRouter API request failed after fallback: {error_message}")
                raise ValueError(f"API request failed: {error_message}")
        elif response.status_code >= 400:
            error_message = _extract_openrouter_error_message(response)
            _LOGGER.error(f"OpenRouter API request failed: {error_message}")
            raise ValueError(f"API request failed: {error_message}")

        response.raise_for_status()
        result = response.json()
        _LOGGER.debug("OpenRouter API request completed successfully")

        # Extract the completion text from the response
        try:
            completion_text = result["choices"][0]["message"]["content"]

            # Check if response was truncated due to length
            finish_reason = result.get("choices", [{}])[0].get("finish_reason", "")
            if finish_reason == "length":
                _LOGGER.warning(f"⚠️ Warning: Response was truncated due to token limit. Consider increasing max_tokens.")

            # Apply the strip_thinking function to remove any thinking tags
            completion_text = strip_thinking(completion_text)
            _LOGGER.info(f"Successfully received response from OpenRouter API (length: {len(completion_text)} chars)")
            return completion_text
        except (KeyError, IndexError) as e:
            _LOGGER.error(f"❌ Error parsing API response structure: {str(e)}")
            _LOGGER.error(f"Available keys in result: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            if "choices" in result:
                _LOGGER.error(f"Choices available: {len(result['choices'])}")
                if result["choices"]:
                    choice = result["choices"][0]
                    _LOGGER.error(f"First choice keys: {list(choice.keys()) if isinstance(choice, dict) else 'Not a dict'}")
            raise ValueError(f"Could not parse response structure: {str(e)}")
    except requests.exceptions.RequestException as e:
        _LOGGER.error(f"Network error during OpenRouter API call: {str(e)}")
        raise Exception(f"Network error: {str(e)}")
    except Exception as e:
        _LOGGER.error(f"OpenRouter API call failed: {str(e)}")
        raise Exception(f"OpenRouter API call failed: {str(e)}")