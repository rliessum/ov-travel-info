#!/usr/bin/env python3
"""Test the integration's API clients directly."""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Add custom_components to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components'))

from aiohttp import ClientSession
from ret_ns_departures.api_ns import NSAPIClient
from ret_ns_departures.api_disruptions import NSDisruptionsAPIClient

# Load environment variables
load_dotenv()
NS_API_KEY = os.getenv('ReisinformatiePrimaryKey')


async def test_integration_clients():
    """Test the integration's API clients."""
    print("="*60)
    print("Testing Integration API Clients")
    print("="*60)
    print(f"API Key: {NS_API_KEY[:8]}...{NS_API_KEY[-8:]}\n")
    
    async with ClientSession() as session:
        # Test NS Departures Client
        print("\n" + "="*60)
        print("Testing NS Departures Client")
        print("="*60)
        
        ns_client = NSAPIClient(session, NS_API_KEY)
        
        try:
            departures = await ns_client.async_get_departures("Rtd", max_journeys=3)
            print(f"✅ SUCCESS - Retrieved {len(departures)} departures")
            
            for idx, dep in enumerate(departures, 1):
                print(f"\n{idx}. {dep.get('direction', 'Unknown')}")
                print(f"   Departure: {dep.get('planned_time', 'Unknown')}")
                print(f"   Track: {dep.get('track', '?')}")
                print(f"   Product: {dep.get('product', 'Unknown')}")
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
        
        # Test NS Disruptions Client
        print("\n" + "="*60)
        print("Testing NS Disruptions Client")
        print("="*60)
        
        disruptions_client = NSDisruptionsAPIClient(session, NS_API_KEY)
        
        try:
            # Test general disruptions
            disruptions = await disruptions_client.async_get_disruptions(is_active=True)
            print(f"✅ SUCCESS - Found {len(disruptions)} active disruptions")
            
            if disruptions:
                print("\nFirst 3 disruptions:")
                for idx, dis in enumerate(disruptions[:3], 1):
                    print(f"\n{idx}. {dis.get('title', 'No title')}")
                    print(f"   Type: {dis.get('type', 'UNKNOWN')}")
                    print(f"   Impact: {dis.get('impact', 0)}/5")
                    print(f"   Active: {dis.get('is_active', False)}")
                    if dis.get('stations'):
                        print(f"   Stations: {', '.join(dis['stations'][:3])}")
            else:
                print("  No active disruptions")
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
        
        # Test station-specific disruptions
        print("\n" + "="*60)
        print("Testing Station-Specific Disruptions (Rotterdam Centraal)")
        print("="*60)
        
        try:
            station_disruptions = await disruptions_client.async_get_station_disruptions("Rtd")
            print(f"✅ SUCCESS - Found {len(station_disruptions)} disruptions for Rotterdam Centraal")
            
            if station_disruptions:
                for idx, dis in enumerate(station_disruptions[:3], 1):
                    print(f"\n{idx}. [{dis.get('type', 'UNKNOWN')}] {dis.get('title', 'No title')}")
            else:
                print("  No disruptions affecting Rotterdam Centraal")
                
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("Test Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_integration_clients())
