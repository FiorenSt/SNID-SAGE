# AI Assistant

SNID SAGE includes an optional AI-powered assistant to help interpret your classification results.

## Setup

### 1. Get an OpenRouter API Key
1. Visit [OpenRouter.ai](https://openrouter.ai/) and create an account
2. Go to **API Keys** and create a new key (starts with `sk-or-...`)

### 2. Configure in SNID SAGE
1. **Load and analyze a spectrum** first
2. Click the **AI Assistant** button (deep blue - enabled after analysis)
3. Go to **Settings** tab → enter your API key → **Test Connection**

## Features

| Feature | Description |
|---------|-------------|
| Quick Summary | Short explanation of classification |
| Detailed Analysis | Structured scientific interpretation |
| Scientific Context | Literature-style discussion |
| Publication Text | Methods/results text blocks |
| Interactive Chat | Ask follow-up questions |

## Usage

1. Complete your SNID analysis
2. Click **AI Assistant** button
3. Choose analysis type and model
4. Review output; copy or export

### Recommended Models

| Model | Best For |
|-------|----------|
| GPT-3.5 Turbo | Fast, everyday analysis |
| GPT-4 Turbo | Complex cases, best quality |
| Claude 3 Opus | Scientific writing |
| Gemini Pro | Multilingual support |

Select models in **Settings** → **Model Selection** → **Fetch All Models**.

## Tips for Astronomers

- Treat AI output as a draft; verify line IDs and claims
- Include uncertainties and caveats; ask follow-up questions
- Use lower temperature for deterministic summaries

## What the AI Sees

The AI receives your SNID results (never your raw spectrum):
- Classification (type, subtype, confidence)
- Redshift and age estimates
- Template matches and scores
- User metadata (observer, telescope, date)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| API key not working | Check format (`sk-or-...`), test in Settings |
| Model not available | Try a different model |
| Analysis fails | Ensure SNID analysis completed first |
| `401 Unauthorized` | Verify API key in OpenRouter dashboard |
| `429 Too Many Requests` | Wait or check billing |

## Privacy

- **Spectrum data**: Never sent to AI
- **API keys**: Stored locally only
- **Results**: Only classification summaries sent
- Review provider terms for data retention
