
import json
import statistics
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Load data at startup
DATA_FILE = r"c:\Users\Aryan\Desktop\Templates\TDS\q-vercel-latency.json"
latency_data = []

try:
    with open(DATA_FILE, 'r') as f:
        latency_data = json.load(f)
except Exception as e:
    print(f"Error loading data: {e}")

class LatencyRequest(BaseModel):
    regions: List[str]
    threshold_ms: float

@app.post("/api/latency")
async def check_latency(request: LatencyRequest):
    regions_set = set(request.regions)
    threshold = request.threshold_ms
    
    results = []
    
    # Process each requested region
    for region in request.regions: # Loop over requested regions to return result for each
        # Filter data for this region
        region_data = [d for d in latency_data if d["region"] == region]
        
        if not region_data:
            # Handle empty data case if necessary, assuming 0/None or skip
            results.append({
                "region": region,
                "avg_latency": 0,
                "p95_latency": 0,
                "avg_uptime": 0,
                "breaches": 0
            })
            continue
            
        latencies = [d["latency_ms"] for d in region_data]
        uptimes = [d["uptime_pct"] for d in region_data]
        
        avg_latency = statistics.mean(latencies)
        # p95
        # statistics.quantiles was added in 3.8. Vercel env is likely 3.9+.
        # method='exclusive' is default. 
        # numpy.percentile is standard but we should avoid extra deps if poss.
        # Let's implement simple percentile
        latencies_sorted = sorted(latencies)
        k = len(latencies_sorted)
        # 95th percentile index. 
        # p95: 95% of values are below this.
        # index = 0.95 * (k - 1)
        # using statistics.quantiles if available
        try:
             # quantiles gives cut points. n=100 -> percentiles.
             # but quantiles might not be in older python.
             # standard definition:
             index = int(0.95 * len(latencies_sorted)) 
             # Note: simple nearest rank or linear interpolation?
             # "p95_latency (95th percentile)"
             # Let's use quantile logic
             import math
             idx = 0.95 * (len(latencies_sorted) - 1)
             lower = math.floor(idx)
             upper = math.ceil(idx)
             if lower == upper:
                 p95 = latencies_sorted[int(idx)]
             else:
                 p95 = latencies_sorted[lower] * (upper - idx) + latencies_sorted[upper] * (idx - lower)
                 
             # Or just use statistics.quantiles(latencies, n=20)[18] if n>=20?
             if len(latencies) >= 20: 
                 # 20 quantiles (vigintiles). 1st cut is 5%, 19th cut is 95%.
                 # statistics.quantiles returns n-1 cut points.
                 # This is safer if standard library has it.
                 # Let's rely on manual interpolation for safety across versions without numpy.
                 pass
        except:
             pass

        # Using nearest rank for simplicity if strict definition not given?
        # Re-implementing linear interpolation style (numpy default)
        def percentile(data, p):
             if not data: return 0
             data = sorted(data)
             k = (len(data) - 1) * p
             f = math.floor(k)
             c = math.ceil(k)
             if f == c:
                 return data[int(k)]
             d0 = data[int(f)]
             d1 = data[int(c)]
             return d0 + (d1 - d0) * (k - f)
             
        p95_latency = percentile(latencies, 0.95)
        
        avg_uptime = statistics.mean(uptimes)
        
        breaches = sum(1 for d in region_data if d["latency_ms"] > threshold)
        
        results.append({
            "region": region,
            "avg_latency": avg_latency,
            "p95_latency": p95_latency,
            "avg_uptime": avg_uptime,
            "breaches": breaches
        })
        
    return results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
