import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Rider, Driver, Ride

app = FastAPI(title="Ride Hailing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Ride Hailing Backend is running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# Helper to convert ObjectId to str

def _id(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    return obj

# Models for inputs that are not full schemas
class Location(BaseModel):
    lat: float
    lng: float

class RideRequest(BaseModel):
    rider_name: str
    rider_phone: str
    pickup: Location
    dropoff: Location

@app.post("/riders", status_code=201)
def create_rider(rider: Rider):
    rider_id = create_document("rider", rider)
    return {"id": rider_id}

@app.post("/drivers", status_code=201)
def create_driver(driver: Driver):
    driver_id = create_document("driver", driver)
    return {"id": driver_id}

@app.get("/drivers", response_model=List[dict])
def list_drivers():
    docs = get_documents("driver")
    for d in docs:
        d["_id"] = _id(d.get("_id"))
    return docs

@app.post("/rides/request", status_code=201)
def request_ride(req: RideRequest):
    # Create or reuse rider
    existing = db["rider"].find_one({"phone": req.rider_phone}) if db else None
    if existing:
        rider_id = str(existing["_id"])
    else:
        rider_id = create_document("rider", Rider(name=req.rider_name, phone=req.rider_phone))

    # Find nearest available driver (naive: any available)
    driver = db["driver"].find_one({"is_available": True}) if db else None
    ride = Ride(
        rider_id=rider_id,
        driver_id=str(driver["_id"]) if driver else None,
        pickup_lat=req.pickup.lat,
        pickup_lng=req.pickup.lng,
        dropoff_lat=req.dropoff.lat,
        dropoff_lng=req.dropoff.lng,
        status="accepted" if driver else "requested",
        fare_estimate=_estimate_fare(req.pickup, req.dropoff)
    )
    ride_id = create_document("ride", ride)

    # Mark driver unavailable if assigned
    if driver:
        db["driver"].update_one({"_id": driver["_id"]}, {"$set": {"is_available": False}})

    return {"ride_id": ride_id, "status": ride.status, "driver_id": ride.driver_id}

@app.get("/rides")
def list_rides():
    docs = get_documents("ride")
    for d in docs:
        d["_id"] = _id(d.get("_id"))
    return docs

@app.post("/rides/{ride_id}/complete")
def complete_ride(ride_id: str):
    ride = db["ride"].find_one({"_id": ObjectId(ride_id)}) if db else None
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    db["ride"].update_one({"_id": ride["_id"]}, {"$set": {"status": "completed"}})
    # Free up driver
    if ride.get("driver_id"):
        try:
            db["driver"].update_one({"_id": ObjectId(ride["driver_id"])}, {"$set": {"is_available": True}})
        except Exception:
            pass
    return {"message": "Ride completed"}

@app.post("/rides/{ride_id}/cancel")
def cancel_ride(ride_id: str):
    ride = db["ride"].find_one({"_id": ObjectId(ride_id)}) if db else None
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    db["ride"].update_one({"_id": ride["_id"]}, {"$set": {"status": "cancelled"}})
    # Free up driver
    if ride.get("driver_id"):
        try:
            db["driver"].update_one({"_id": ObjectId(ride["driver_id"])}, {"$set": {"is_available": True}})
        except Exception:
            pass
    return {"message": "Ride cancelled"}

# Simple straight-line fare estimate
from math import radians, sin, cos, sqrt, atan2

def _haversine_km(a: Location, b: Location) -> float:
    R = 6371.0
    lat1 = radians(a.lat)
    lon1 = radians(a.lng)
    lat2 = radians(b.lat)
    lon2 = radians(b.lng)
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    h = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(h), sqrt(1 - h))
    return R * c

def _estimate_fare(pickup: Location, dropoff: Location) -> float:
    distance_km = _haversine_km(pickup, dropoff)
    base = 2.5
    per_km = 1.2
    return round(base + per_km * distance_km, 2)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
