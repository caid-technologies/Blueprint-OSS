# Blueprint Open-Source: AI-Native Hardware Design Generator

Blueprint is an open-source, prompt-to-verifiable hardware project compiler. Users enter a natural-language idea for any physical/electronic project and the system produces a structured, electrically validated, and buildable hardware project package.

It mimics the core features of [blueprint.am](https://blueprint.am/), but with an advanced multi-agent backend orchestrated by Google's Agent Development Kit (ADK) and a rich React Flow circuit canvas UI.

---

## 🚀 Key Features

1. **7-Agent Hardware Assembly Pipeline**
   * Coordinated via Google ADK, transforming raw prompts into structured hardware compilations.
2. **Typed Hardware Intermediate Representation (IR)**
   * Every project compiles into a robust, typed Pydantic JSON graph with strict schema validation.
3. **Automated Circuit Safety Auditor**
   * Evaluates the compiled circuit netlist against 5 crucial physical and electrical rules:
     * **Short Circuit Protection**: Detects direct power-to-ground connections.
     * **Voltage Mismatch Warning**: Warns of direct logic links between mismatched voltage lines (e.g. 5.0V MCU pin to 3.3V sensor pin).
     * **Floating IC Check**: Flags microcontrollers/integrated circuits lacking VCC or ground references.
     * **Pin Conflict Auditor**: Disallows digital pin reuse across multiple signal lines.
     * **Over-current Risk Alert**: Protects MCU internal regulators from peak draw from power-hungry servos or relays.
4. **Self-Healing Connection Loop**
   * If the circuit auditor discovers critical violations, it pipes the validation reports back into the Wiring/Netlist agent for auto-correction before final compilation.
5. **Interactive CAD Schematic Viewer**
   * Zoomable and pannable React Flow layout showing color-coded wires (Power, Ground, I2C, SPI, Digital) and physical part pinouts.
6. **BOM, Assembly & Mechanical Slicing**
   * Instantly calculates total cost, formats step-by-step assembly walkthroughs, and outputs 3D printing parameter specs.

---

## 📂 Repository Structure

```directory
├── backend/
│   ├── agents/
│   │   ├── __init__.py
│   │   └── orchestrator.py        # Google ADK agent configurations & workflow pipeline
│   ├── main.py                    # FastAPI server routers, seed, and project endpoints
│   ├── models.py                  # Pydantic models for the structured Hardware IR
│   ├── database.py                # PostgreSQL / SQLAlchemy storage backend
│   ├── seed_db.py                 # Inventory database populated with seed components
│   ├── validation.py              # 5-rule electrical circuit auditor
│   ├── utils.py                   # SVG Schematic & Mermaid generator helpers
│   └── requirements.txt           # Backend python dependencies
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── globals.css            # Custom styles & React Flow edge animations
│   │   └── page.tsx               # CAD dashboard UI
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── package.json               # Next.js dependencies
└── examples/
    ├── plant_watering.json        # Auto-Grow Moisture monitor preset
    ├── smart_thermostat.json      # Climate controller thermostat preset
    └── biometric_deadbolt.json    # Bluetooth keyless deadbolt lock preset
```

---

## ⚡ Quick Start Guide

### Prerequisites
* Python 3.11+
* Node.js v18+
* PostgreSQL database (Optional: falls back gracefully to standard SQLite `blueprint.db` locally if Postgres connection is not set up, ensuring 100% out-of-the-box local reliability).

---

### 1. Set Up and Run the Backend

Navigate to the `backend/` folder:
```bash
cd backend
```

Create a virtual environment and activate it:
```bash
python3 -m venv venv
source venv/bin/activate
```

Install the required python packages:
```bash
pip install -r requirements.txt
```

#### Database Setup
Create a `.env` file inside `backend/` to point to your PostgreSQL instance and specify your Gemini API Key:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/blueprint
GEMINI_API_KEY=your_gemini_api_key_here
```

Populate the database with our seed component templates (ESP32, Arduino Nano, sensors, displays, relays, and batteries):
```bash
python3 seed_db.py
```

Run the FastAPI backend server:
```bash
uvicorn main:app --reload --port 8000
```
Your backend will run on [http://localhost:8000](http://localhost:8000) and documentation is available at `/docs`.

*Note: If no `GEMINI_API_KEY` is provided, the backend automatically transitions to high-fidelity, offline simulation fallback mode, loading pre-compiled example structures depending on your prompt keywords. This allows immediate interface testing!*

---

### 2. Set Up and Run the Frontend

Navigate to the `frontend/` folder:
```bash
cd ../frontend
```

Install Node dependencies:
```bash
npm install
```

Start the Next.js development server:
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser to experience the CAD interface!

---

## 🧪 Experience the Core Workflows

1. **Preset One-Click Loading**: Click Smart Watering, Thermostat, or Smart Deadbolt in the top header to instantly render complex pin-to-pin wiring schematics and assembly steps.
2. **AI-Native Compiling**: Enter a prompt like `"Build an automated weather station measuring barometric pressure using ESP32 and BMP280, displaying on OLED screen."` and watch the 7-Agent pipeline run in real-time.
3. **Downloadable Hardware IR Packages**: Export your validated project as a JSON structure using the **Export Package** button.
