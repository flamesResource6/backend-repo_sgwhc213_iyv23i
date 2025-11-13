"""
Database Schemas

Ride-hailing (Uber-like) app schemas using Pydantic models.
Each class name maps to a MongoDB collection with its lowercase name.
- Rider -> rider
- Driver -> driver
- Ride -> ride
"""

from pydantic import BaseModel, Field
from typing import Optional

class Rider(BaseModel):
    name: str = Field(..., description="Rider full name")
    phone: str = Field(..., description="Contact phone number")

class Driver(BaseModel):
    name: str = Field(..., description="Driver full name")
    car_model: str = Field(..., description="Car model")
    plate: str = Field(..., description="License plate")
    lat: float = Field(..., description="Current latitude")
    lng: float = Field(..., description="Current longitude")
    is_available: bool = Field(True, description="Availability for rides")

class Ride(BaseModel):
    rider_id: str = Field(..., description="Rider document id (string)")
    driver_id: Optional[str] = Field(None, description="Driver document id (string)")
    pickup_lat: float = Field(..., description="Pickup latitude")
    pickup_lng: float = Field(..., description="Pickup longitude")
    dropoff_lat: float = Field(..., description="Dropoff latitude")
    dropoff_lng: float = Field(..., description="Dropoff longitude")
    status: str = Field("requested", description="requested|accepted|enroute|completed|cancelled")
    fare_estimate: Optional[float] = Field(None, description="Estimated fare in USD")
