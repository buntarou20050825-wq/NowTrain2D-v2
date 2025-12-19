"""
Debug script to check TripUpdate raw data and route_id values.
"""
import asyncio
import os
import httpx
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2

load_dotenv()

# Use the correct challenge API URL
TRIP_UPDATE_URL = "https://api-challenge.odpt.org/api/v4/gtfs/realtime/jreast_odpt_train_trip_update"

async def main():
    api_key = os.getenv("ODPT_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ODPT_API_KEY not set")
        return
    
    # Output to file
    with open("debug_output.txt", "w") as f:
        f.write(f"API Key (first 10 chars): {api_key[:10]}...\n")
        f.write(f"URL: {TRIP_UPDATE_URL}\n")
        f.write("Fetching TripUpdate...\n")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    TRIP_UPDATE_URL,
                    params={"acl:consumerKey": api_key},
                    timeout=30
                )
                f.write(f"Status: {response.status_code}\n")
                
                if response.status_code != 200:
                    f.write(f"Error: {response.text[:500]}\n")
                    return
                
                feed = gtfs_realtime_pb2.FeedMessage()
                feed.ParseFromString(response.content)
                
                f.write(f"Feed timestamp: {feed.header.timestamp}\n")
                f.write(f"Total entities: {len(feed.entity)}\n")
                
                # Check entities
                trip_update_count = 0
                route_ids = set()
                trip_id_samples = []
                
                for entity in feed.entity:
                    if entity.HasField("trip_update"):
                        trip_update_count += 1
                        trip = entity.trip_update.trip
                        
                        if trip.route_id:
                            route_ids.add(trip.route_id)
                        
                        if len(trip_id_samples) < 10:
                            trip_id_samples.append(trip.trip_id)
                
                f.write(f"\nTripUpdate entities: {trip_update_count}\n")
                f.write(f"Unique route_ids: {route_ids}\n")
                f.write(f"\nTrip ID samples (first 10): {trip_id_samples}\n")
        except Exception as e:
            f.write(f"Exception: {e}\n")
    
    print("Output written to debug_output.txt")

if __name__ == "__main__":
    asyncio.run(main())
