# Developer Project Validator

Developer Project Validator is a Flask web app that helps you evaluate a project idea before you build it.

You enter an idea and the app generates a practical validation report with:
- Market competition
- Monetization potential
- Target users
- Feature suggestions
- MVP plan
- Risk score and final verdict

## Tech Stack
- Backend: Python, Flask
- AI: Google Gemini API (`gemini-2.5-flash` by default)
- Frontend: HTML, CSS, JavaScript

## Project Structure
```text
.
├── app.py
├── requirements.txt
├── .env.example
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── app.js
```

## Prerequisites
- Python 3.9+
- A Gemini API key

## Setup
1. Create a virtual environment:
```bash
python -m venv .venv
```

2. Activate it:
```bash
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create environment file:
```bash
cp .env.example .env
```

5. Update `.env` with your key:
```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

## Run the App
```bash
python app.py
```

Open:
- `http://127.0.0.1:5000/`

Health check:
- `http://127.0.0.1:5000/health`

## How to Use
1. Open the app in your browser.
2. Enter your project idea in the text box.
3. Click **Analyze Idea**.
4. Review the generated report sections.

## Troubleshooting

### 1) Module not found errors
If you see errors like `ModuleNotFoundError`, dependencies are missing.

Fix:
```bash
pip install -r requirements.txt
```

### 2) Gemini API permission errors (403)
If you see `PERMISSION_DENIED` or `API_KEY_SERVICE_BLOCKED`:
- Confirm your API key is valid.
- Make sure the Generative Language API is enabled for the key's project.
- Check API key restrictions.

### 3) Browser shows local 403 but server is running
If one browser fails and another works, the issue is usually browser/network restrictions for localhost.
Try another browser profile, disable VPN/proxy/shields for localhost, or switch port.

Run on another port:
```bash
PORT=8000 python app.py
```

## Notes
- This app is intended for local development.
- Do not use the Flask dev server as-is for production deployment.

## License
Add your preferred license here.
