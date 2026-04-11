# Drift Zero — API Data Source Explorer

A tool for testing and understanding the 5 data sources that power the Drift Zero space domain intelligence platform.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` and add:

```env
# Space-Track.org credentials
SPACETRACK_EMAIL=your_email@example.com
SPACETRACK_PASSWORD=your_password

# ESA DISCOS API token (optional)
ESA_DISCOS_TOKEN=your_token_here
```

#### Getting credentials

**Space-Track (required)**
1. Go to https://www.space-track.org
2. Click **Register** → fill out the form (name, email, organization, intended use)
3. Verify your email
4. Use your email + password in `.env`

**ESA DISCOS Token (optional but recommended)**
1. Register at https://account.sdo.esoc.esa.int/auth/register?referrer=discosweb
2. Log in and go to https://account.sdo.esoc.esa.int/settings
3. Find your **API Token** and copy it to `.env`

**NOAA SWPC (no credentials needed)**
Fully public API — no auth required.

### 3. Run the explorer

```bash
python -u test_apis.py
```

This will:
- Test all 5 data sources
- Print a schema table for each source (field names, types, pipeline roles)
- Show live values from ISS for each API
- Save a complete example JSON to `example_data.json`

## Data Sources

| # | Source | Data | Used By |
|---|--------|------|---------|
| 1 | Space-Track TLE | Orbital elements | Shield + Rogue |
| 2 | Space-Track CDM | Conjunction warnings | Shield |
| 3 | Space-Track Historical | Time-series orbits | Rogue |
| 4 | ESA DISCOS | Physical properties | Shield + Rogue |
| 5 | NOAA SWPC | Solar weather | Shield |

## Output

**Console output** shows:
- Schema table for each source (for data pipeline design)
- Live values from one API call (to see real data)
- Field explanations (for understanding each field's role)

**example_data.json** contains:
- One complete JSON record from each source
- Endpoint URLs and authentication methods
- Field descriptions and join keys
- Use this to document your data pipeline schemas

## For the Data Pipeline Team

1. Read the schema tables printed to console (field names, types, pipeline roles)
2. Check `example_data.json` for actual field values and structure
3. Use the join keys documented in each schema:
   - **Space-Track TLE** joins to **ESA DISCOS** on `NORAD_CAT_ID` = `satno`
   - **Space-Track CDM** joins to both via `SAT_1_ID` and `SAT_2_ID`
   - **NOAA SWPC** is keyed by timestamp — join on time range

## Files

- `test_apis.py` — main explorer script
- `.env` — your credentials (DO NOT push to GitHub)
- `.env.example` — template for `.env`
- `example_data.json` — live example output (gitignored)
- `.gitignore` — prevents pushing `.env`, credentials, and generated files
- `requirements.txt` — Python dependencies
- `README.md` — this file
