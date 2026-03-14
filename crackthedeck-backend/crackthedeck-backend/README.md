# CrackTheDeck Backend

AI-powered pitch deck analysis API. Upload a startup pitch deck, get a structured investment or founder report.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your OpenAI API key

# Run in mock mode (no API key needed)
MOCK_MODE=true uvicorn main:app --host 0.0.0.0 --port 8000

# Run in production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### `POST /api/analyze`
Upload a pitch deck for analysis.

**Parameters (multipart/form-data):**
- `file` — PDF or PPTX file (max 50MB)
- `report_type` — `"investor"` or `"startup"`

**Response:**
```json
{
  "report_id": "abc123",
  "report_type": "investor",
  "company_name": "Acme Corp",
  "pdf_url": "/api/report/abc123/investor/pdf",
  "data": { ... }
}
```

### `GET /api/report/{report_id}/{report_type}/pdf`
Download the generated PDF report.

### `GET /api/health`
Health check.

## Report Types

### Investor Report (3 pages)
For investors evaluating a deal. Focuses on investment merit only — not presentation quality.
- Investment score (0-100) across 10 criteria
- Key financial metrics
- Strengths and risks analysis

### Startup/Founder Report (4 pages)
For founders improving their pitch deck.
- 14-element completeness checklist
- Fundraising readiness assessment (HIGH/MEDIUM/LOW)
- Top 10 prioritized issues
- Recommended deck structure

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model for analysis |
| `MOCK_MODE` | `false` | Skip GPT-4o, return sample data |
| `MAX_FILE_SIZE_MB` | `50` | Max upload size |
| `PORT` | `8000` | Server port |

## Architecture

```
Upload → [PPTX→PDF] → PDF→Images → GPT-4o Vision → JSON → ReportLab PDF
```

- GPT-4o receives all slide images in a single vision API call
- Structured JSON response is validated against Pydantic schemas
- PDF reports generated with ReportLab canvas API (cyberpunk dark theme)
- JetBrains Mono + Inter fonts, auto-downloaded from GitHub
