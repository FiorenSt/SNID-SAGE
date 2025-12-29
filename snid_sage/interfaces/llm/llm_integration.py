"""
Simplified LLM Integration for SNID AI Assistant

This module provides a unified interface for LLM interactions with:
- OpenRouter-only backend support
- Single comprehensive summary generation
- Chat functionality with context awareness
- User metadata integration
- Enhanced SNID result formatting
"""

import os
import json
from typing import Dict, List, Optional, Any, Union
import traceback

try:
    from snid_sage.interfaces.llm.openrouter.openrouter_llm import (
        call_openrouter_api,
        configure_openrouter_dialog,
        get_openrouter_config,
        get_openrouter_api_key,
        DEFAULT_MODEL,
    )
    from snid_sage.interfaces.llm.analysis.llm_utils import build_enhanced_context_with_metadata
    OPENROUTER_AVAILABLE = True
except ImportError as e:
    print(f"OpenRouter integration not available: {e}")
    OPENROUTER_AVAILABLE = False


class LLMIntegration:
    """
    Simplified LLM Integration class with OpenRouter-only support.
    
    Features:
    - Single comprehensive summary generation
    - Context-aware chat functionality
    - User metadata integration
    - Enhanced SNID result formatting
    """
    
    def __init__(self, gui_instance=None):
        """Initialize LLM integration."""
        self.gui = gui_instance
        self.llm_available = OPENROUTER_AVAILABLE
        self.current_model = None
        self.api_key = None
        
        # Initialize OpenRouter configuration
        if OPENROUTER_AVAILABLE:
            self._load_openrouter_config()
    
    def _load_openrouter_config(self):
        """Load OpenRouter configuration."""
        try:
            config = get_openrouter_config()
            # Prefer secure storage for API key
            try:
                self.api_key = get_openrouter_api_key()
            except Exception:
                self.api_key = None
            if not self.api_key:
                # Backward compatibility if key was stored previously
                self.api_key = config.get('api_key')

            # Prefer saved model; if none is set, allow runtime to auto-pick a free model.
            # (call_openrouter_api() will persist the chosen model after the first successful call)
            self.current_model = config.get('model_id') or None
            
            # Check if configuration is valid
            if self.api_key:
                self.llm_available = True
            else:
                self.llm_available = False
                
        except Exception as e:
            print(f"Error loading OpenRouter config: {e}")
            self.llm_available = False
    
    def configure_openrouter(self):
        """Configure OpenRouter settings."""
        if not OPENROUTER_AVAILABLE:
            raise Exception("OpenRouter integration not available")
        
        # Reload configuration after setup
        self._load_openrouter_config()
    
    def _open_comprehensive_openrouter_config(self):
        """Open comprehensive OpenRouter configuration dialog."""
        if not OPENROUTER_AVAILABLE:
            raise Exception("OpenRouter integration not available")
        
        try:
            # Import and show configuration dialog
            configure_openrouter_dialog(parent=None)
            
            # Reload configuration
            self._load_openrouter_config()
            
        except Exception as e:
            raise Exception(f"Failed to open OpenRouter configuration: {str(e)}")
    
    def generate_summary(self, snid_results: Union[Dict[str, Any], Any], user_metadata: Dict[str, str] = None) -> str:
        """
        Generate a comprehensive AI summary of SNID results.
        
        Args:
            snid_results: SNID analysis results (can be Dict or SNIDResult object)
            user_metadata: User-provided observation metadata
            
        Returns:
            str: Generated summary text
        """
        if not self.llm_available:
            raise Exception("LLM backend not configured. Please configure OpenRouter in settings.")
        
        try:
            # Format SNID results for LLM
            formatted_data = self.format_snid_results_for_llm(snid_results)
            
            # Add user metadata if available (support multiple key variants from GUI)
            if user_metadata and any(user_metadata.values()):
                def first_nonempty(keys):
                    for k in keys:
                        v = user_metadata.get(k)
                        if v:
                            return v
                    return None

                metadata_parts = ["📋 OBSERVATION DETAILS:"]

                object_name = first_nonempty(['object_name', 'target', 'source_name'])
                telescope = first_nonempty(['telescope_instrument', 'telescope', 'instrument'])
                obs_date = first_nonempty(['observation_date', 'date'])
                reporting_group = first_nonempty(['reporting_group', 'group', 'team', 'observer', 'observer_name'])
                notes = first_nonempty(['additional_notes', 'notes', 'specific_request'])

                if object_name:
                    metadata_parts.append(f"   Object Name: {object_name}")
                if telescope:
                    metadata_parts.append(f"   Telescope/Instrument: {telescope}")
                if obs_date:
                    metadata_parts.append(f"   Observation Date: {obs_date}")
                if reporting_group:
                    metadata_parts.append(f"   Reporting Group/Name: {reporting_group}")
                if notes:
                    metadata_parts.append(f"   Additional Notes: {notes}")

                formatted_data += "\n\n" + "\n".join(metadata_parts)
            
            # Build directive prompt with explicit structure and constraints
            system_prompt = """You are AstroSage, a world-renowned expert in supernova spectroscopy with decades of experience in stellar evolution, spectral analysis, and observational astronomy. You have published extensively on Type Ia, Type II, and exotic supernovae classifications.

You are analyzing results from SNID-SAGE, a spectral template matching pipeline that performs cross-correlation analysis between observed spectra and template libraries to identify supernova types and estimate redshifts.

Provide a concise, scientifically rigorous summary that includes the key classification results, confidence assessment, and main findings. Focus on the most important information for researchers and observers."""

            # Optional additional user instruction (from GUI "specific_request")
            additional_instruction = None
            if user_metadata:
                # Accept either specific_request or an alias
                additional_instruction = (
                    user_metadata.get('specific_request') or
                    user_metadata.get('additional_notes') or
                    user_metadata.get('notes')
                )
                if additional_instruction:
                    additional_instruction = additional_instruction.strip()
                    if not additional_instruction:
                        additional_instruction = None

            user_prompt = (
                "Using the SNID-SAGE summary below, produce a compact text-only summary (≤160 words). Do not reproduce tables.\n\n"
                "1) Optional lead-in: If observation metadata (Reporting Group/Name, Telescope/Instrument, Observation Date) is present in the data, include them in one short clause; otherwise omit this entirely. Avoid personal attributions; use neutral, professional wording.\n\n"
                "2) Classification focus:\n"
                "   - Identify the best subtype (from ‘Best Subtype’) and the subtype of the best template (from ‘Best Template’).\n"
                "   - If subtypes match: mention the best template by name with the (type/subtype) and briefly qualify match quality in a few words (e.g., ‘high match quality’, ‘moderate confidence’).\n"
                "   - If subtypes differ: explicitly note the disagreement (best subtype vs best-template subtype) and add a short qualifier (e.g., margin/consistency). Proceed with the best subtype as the primary conclusion.\n\n"
                "3) Key measurements: Report redshift ± uncertainty (prefer enhanced/cluster-weighted if present) and age ± uncertainty if available; keep to one compact sentence.\n\n"
                "4) Spectral features: If user-identified or detected spectral lines are listed, comment on each briefly by name with a quick relevance note for the inferred type/subtype (e.g., ‘Si II 6150 Å: hallmark of Type Ia’; ‘Hα: consistent with Type II’). If only wavelengths are given, infer cautiously and indicate uncertainty.\n\n"
                "5) Caveat: Add a single clause about uncertainty only if confidence is low or redshift spread is large.\n\n"
                "Data:\n" + formatted_data
            )

            if additional_instruction:
                user_prompt = (
                    user_prompt
                    + "\n\nAdditional user instruction (apply if compatible with scientific rigor and brevity):\n"
                    + additional_instruction
                )

            full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
            
            # Generate summary using OpenRouter
            response = call_openrouter_api(
                prompt=full_prompt,
                max_tokens=2000
            )
            
            if response:
                return self._format_summary_response(response)
            else:
                raise Exception("No response received from AI model")
                
        except Exception as e:
            raise Exception(f"Summary generation failed: {str(e)}")
    
    def chat_with_llm(self, message: str, conversation_history: List[Dict] = None, 
                     user_metadata: Dict[str, str] = None, max_tokens: int = 1500) -> str:
        """
        Chat with the LLM with context awareness.
        
        Args:
            message: User message
            conversation_history: Previous conversation messages
            user_metadata: User-provided observation metadata
            max_tokens: Maximum tokens for response (default: 1500)
            
        Returns:
            str: AI response
        """
        if not self.llm_available:
            raise Exception("LLM backend not configured. Please configure OpenRouter in settings.")
        
        try:
            # Build context-aware chat prompt
            chat_prompt = self._build_chat_prompt(message, conversation_history, user_metadata)
            
            # Get response from OpenRouter
            response = call_openrouter_api(
                prompt=chat_prompt,
                max_tokens=max_tokens
            )
            
            if response:
                return self._format_chat_response(response)
            else:
                raise Exception("No response received from AI model")
                
        except Exception as e:
            raise Exception(f"Chat failed: {str(e)}")
    
    def _build_chat_prompt(self, message: str, conversation_history: List[Dict] = None, 
                          user_metadata: Dict[str, str] = None) -> str:
        """Build context-aware chat prompt."""
        system_prompt = """You are AstroSage, an expert AI assistant specializing in supernova spectroscopy and the SNID-SAGE analysis pipeline.

Strict response policy:
- Always refer to the pipeline as "SNID-SAGE" (not just SNID).
- Do not fabricate data, files, tables, headings, or code. Use only facts present in the provided context and the user's message.
- Do not include markdown tables or code blocks unless the user supplied data/code or explicitly asks for code. Avoid headings; answer in plain prose or concise bullet points only when helpful.
- If essential information is missing (e.g., number of template matches), state that it is not available in the current context and ask for the specific snippet needed (e.g., the 'TEMPLATE MATCHES' section) rather than guessing.
- Keep answers concise and professional (aim for ≤120 words unless the user requests more detail).
- Do not propose shell commands unless explicitly asked. If the user asks for commands, provide Windows PowerShell-compatible commands and separate commands with ';' (never '&&')."""

        # Build conversation context
        context_parts = []

        # Add available SNID-SAGE analysis facts if accessible from GUI
        try:
            snid_context = ""
            if hasattr(self, 'gui') and self.gui:
                # Prefer main-window attached results
                if hasattr(self.gui, 'snid_results') and self.gui.snid_results:
                    snid_context = self.format_snid_results_for_llm(self.gui.snid_results)
                # Fallback: dialog-attached results (e.g., current_snid_results on assistant dialog)
                elif hasattr(self.gui, 'current_snid_results') and getattr(self.gui, 'current_snid_results'):
                    snid_context = self.format_snid_results_for_llm(getattr(self.gui, 'current_snid_results'))
                # Fallback: controller-held results
                elif hasattr(self.gui, 'app_controller') and getattr(self.gui.app_controller, 'snid_results', None):
                    snid_context = self.format_snid_results_for_llm(self.gui.app_controller.snid_results)
                # Alternative name sometimes used
                elif hasattr(self.gui, 'analysis_results') and getattr(self.gui, 'analysis_results', None):
                    snid_context = self.format_snid_results_for_llm(self.gui.analysis_results)
            if snid_context:
                context_parts.append("Available SNID-SAGE context (facts only):")
                # Truncate overly long context to keep prompt size reasonable
                snid_lines = snid_context.strip().split('\n')
                if len(snid_lines) > 120:
                    snid_lines = snid_lines[:120] + ["... (truncated)"]
                context_parts.extend(snid_lines)
        except Exception:
            pass
        
        # Add user metadata if available
        if user_metadata and any(user_metadata.values()):
            context_parts.append("Current observation context:")
            for key, value in user_metadata.items():
                if value:
                    context_parts.append(f"- {key.replace('_', ' ').title()}: {value}")
        
        # Add conversation history
        if conversation_history:
            context_parts.append("\nRecent conversation:")
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                if role == 'user':
                    context_parts.append(f"User: {content}")
                elif role == 'assistant':
                    context_parts.append(f"Assistant: {content}")
        
        # Combine everything
        if context_parts:
            context_str = "\n".join(context_parts)
            full_prompt = f"{system_prompt}\n\n{context_str}\n\nUser: {message}\n\nAssistant:"
        else:
            full_prompt = f"{system_prompt}\n\nUser: {message}\n\nAssistant:"
        
        return full_prompt
    
    def _format_summary_response(self, response: str) -> str:
        """Format and clean up summary response."""
        # Remove any system artifacts
        cleaned = response.strip()
        
        # Ensure proper formatting (remove emojis; keep model-agnostic and avoid duplicate headings)
        # Do not prepend a fixed heading here to avoid double titles in the final summary
        
        return cleaned
    
    def _format_chat_response(self, response: str) -> str:
        """Format and clean up chat response."""
        # Remove any system artifacts and clean up
        cleaned = response.strip()

        # Strip common AI prefixes
        prefixes_to_remove = [
            "Assistant:",
            "AI Assistant:",
            "AstroSage:",
            "Response:",
            "System:",
            "User:"
        ]
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()

        # Enforce no tables/code blocks unless user asked; convert simple fenced blocks to plain text sentences
        if "```" in cleaned:
            cleaned = cleaned.replace("```", "").strip()
        # Remove markdown table lines
        lines = []
        for line in cleaned.split('\n'):
            if line.strip().startswith('|') and '|' in line.strip()[1:]:
                continue
            if set(line.strip()) <= set('-|:'):
                continue
            lines.append(line)
        cleaned = '\n'.join(lines).strip()

        return cleaned
    
    def format_snid_results_for_llm(self, snid_results: Union[Dict[str, Any], Any]) -> str:
        """
        Format SNID results for LLM consumption using unified formatter.
        
        Args:
            snid_results: SNID analysis results (can be Dict or SNIDResult object)
            
        Returns:
            str: Formatted results string
        """
        if not snid_results:
            return "No SNID results available."
        
        try:
            # Handle both dictionary and SNIDResult object inputs
            if hasattr(snid_results, 'consensus_type'):
                # snid_results is a SNIDResult object
                result = snid_results
            else:
                # snid_results is a dictionary
                result = snid_results.get('result')
            
            if not result:
                return "No SNID result object found."
            
            # Check if it's a successful result
            if not hasattr(result, 'success') or not result.success:
                return "SNID analysis was not successful or incomplete."
            
            # Use the unified formatter to get the display summary
            # This ensures consistency with what the user sees in the GUI
            try:
                from snid_sage.shared.utils.results_formatter import create_unified_formatter
                spectrum_name = getattr(result, 'spectrum_name', 'Unknown')
                formatter = create_unified_formatter(result, spectrum_name)
                summary_text = formatter.get_display_summary()
                
                # Ensure we only show top 5 templates by truncating if needed
                lines = summary_text.split('\n')
                template_section_started = False
                template_count = 0
                filtered_lines = []
                
                for line in lines:
                    if '🏆 TEMPLATE MATCHES' in line:
                        template_section_started = True
                        filtered_lines.append(line)
                    elif template_section_started and line.strip() and not line.startswith('#') and not line.startswith('-'):
                        # This is a template match line
                        if template_count < 5:
                            filtered_lines.append(line)
                            template_count += 1
                        # Skip remaining template lines after 5
                    elif template_section_started and (line.startswith('#') or line.startswith('-')):
                        # Header lines in template section
                        filtered_lines.append(line)
                    elif not template_section_started:
                        # Lines before template section
                        filtered_lines.append(line)
                    elif template_section_started and not line.strip():
                        # Empty line after template section - end of templates
                        filtered_lines.append(line)
                        template_section_started = False
                    else:
                        # Lines after template section
                        filtered_lines.append(line)
                
                # Add emission lines context if available (if we have access to GUI)
                if hasattr(self, 'gui') and self.gui:
                    emission_lines_text = self._format_emission_lines_for_llm()
                    if emission_lines_text:
                        filtered_lines.extend(['', emission_lines_text])
                
                return '\n'.join(filtered_lines)
                
            except ImportError:
                # Fallback if unified formatter not available
                from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
                return f"SNID analysis completed for {getattr(result, 'spectrum_name', 'Unknown')}\n" \
                       f"Type: {result.consensus_type}\n" \
                       f"Redshift: {result.redshift:.6f}\n" \
                       f"Quality: {get_best_metric_value(best_match):.2f} {get_best_metric_name(best_match)}"
            
        except Exception as e:
            return f"Error formatting SNID results: {str(e)}"
    
    def _format_emission_lines_for_llm(self):
        """Format detected emission lines for LLM context
        
        Returns:
            str: Formatted emission lines text or empty string if none detected
        """
        try:
            # This method requires access to GUI instance for spectrum data
            if not hasattr(self, 'gui') or not self.gui:
                return ""
            
            gui = self.gui
            
            # Try to get spectrum data from SNID results
            spectrum_data = None
            if hasattr(gui, 'snid_results') and gui.snid_results:
                if hasattr(gui.snid_results, 'processed_spectrum') and gui.snid_results.processed_spectrum:
                    processed = gui.snid_results.processed_spectrum
                    if 'log_wave' in processed and 'flat_flux' in processed:
                        # Convert log wavelength to linear
                        import numpy as np
                        wavelength = np.power(10, processed['log_wave'])
                        flux = processed['flat_flux']
                        spectrum_data = {'wavelength': wavelength, 'flux': flux}
            
            # Fallback to GUI processed spectrum
            if spectrum_data is None and hasattr(gui, 'processed_spectrum') and gui.processed_spectrum:
                if 'log_wave' in gui.processed_spectrum and 'flat_flux' in gui.processed_spectrum:
                    import numpy as np
                    wavelength = np.power(10, gui.processed_spectrum['log_wave'])
                    flux = gui.processed_spectrum['flat_flux']
                    spectrum_data = {'wavelength': wavelength, 'flux': flux}
            
            if spectrum_data is None:
                return ""
            
            # Detect emission lines using Tk-free detection utilities
            try:
                from snid_sage.shared.utils.line_detection.detection import detect_and_fit_lines
                
                wavelength = spectrum_data['wavelength']
                flux = spectrum_data['flux']
                
                # Filter out zero/invalid regions
                import numpy as np
                valid_mask = (flux != 0) & np.isfinite(flux) & np.isfinite(wavelength)
                if not np.any(valid_mask):
                    return ""
                
                wavelength = wavelength[valid_mask]
                flux = flux[valid_mask]
                
                # Detect lines with conservative parameters
                detected_lines = detect_and_fit_lines(
                    wavelength, flux, 
                    min_width=2, max_width=15, min_snr=3.0,
                    max_fit_window=30, smoothing_window=5, use_smoothing=True
                )
                
                if not detected_lines:
                    return ""
                
                # Format detected lines for LLM
                emission_lines = [line for line in detected_lines if line.get('type') == 'emission']
                absorption_lines = [line for line in detected_lines if line.get('type') == 'absorption']
                
                if not emission_lines and not absorption_lines:
                    return ""
                
                lines_text = ["🌟 DETECTED SPECTRAL LINES:"]
                
                if emission_lines:
                    lines_text.append("   Emission Lines:")
                    # Sort by SNR (strongest first) and limit to top 10
                    emission_lines.sort(key=lambda x: x.get('snr', 0), reverse=True)
                    for i, line in enumerate(emission_lines[:10], 1):
                        wavelength_val = line.get('wavelength', 0)
                        snr = line.get('snr', 0)
                        lines_text.append(f"   {i:2d}. {wavelength_val:7.1f} Å  (S/N: {snr:.1f})")
                
                if absorption_lines:
                    lines_text.append("   Absorption Lines:")
                    # Sort by SNR (strongest first) and limit to top 5
                    absorption_lines.sort(key=lambda x: x.get('snr', 0), reverse=True)
                    for i, line in enumerate(absorption_lines[:5], 1):
                        wavelength_val = line.get('wavelength', 0)
                        snr = line.get('snr', 0)
                        lines_text.append(f"   {i:2d}. {wavelength_val:7.1f} Å  (S/N: {snr:.1f})")
                
                return '\n'.join(lines_text)
                
            except ImportError:
                # Line detection utilities not available
                return ""
            except Exception as e:
                # Log debug message but don't fail
                return ""
                
        except Exception as e:
            # Log debug message but don't fail
            return ""

