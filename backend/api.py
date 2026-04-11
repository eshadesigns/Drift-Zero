from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from run_rogue import run

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/rogue/events")
def get_events():
    flagged = run(norad_ids=[25544, 48274, 44713, 28190], days=30)
    return [
        {
            "norad_id": e.norad_id,
            "epoch": str(e.epoch),
            "severity": e.severity,
            "composite_score": round(e.composite_score, 3),
            "z_score_max": round(e.z_score_max, 3),
            "anomalous_features": e.anomalous_features,
            "description": e.description,
        }
        for e in flagged
    ]