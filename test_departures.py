#!/usr/bin/env python3
"""Quick test to view departures from specific stations."""
import asyncio
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Add custom_components to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components'))

from aiohttp import ClientSession
from ret_ns_departures.api_ns import NSAPIClient
from ret_ns_departures.api_ret import RETAPIClient

# Load environment variables
load_dotenv()
NS_API_KEY = os.getenv('ReisinformatiePrimaryKey')


async def test_ns_station(client, station_code, station_name):
    """Test NS departures for a station."""
    print(f"\n{'='*70}")
    print(f"NS Departures: {station_name} ({station_code})")
    print(f"{'='*70}")
    
    try:
        departures = await client.async_get_departures(station_code)
        
        if not departures:
            print("❌ No departures found")
            return
        
        print(f"✅ Found {len(departures)} departures\n")
        
        for idx, dep in enumerate(departures[:10], 1):
            destination = dep.get('destination', 'Unknown')
            actual = dep.get('actual_time')
            scheduled = dep.get('scheduled_time')
            platform = dep.get('platform', '?')
            train_type = dep.get('train_type', 'Unknown')
            delay = dep.get('delay', 0)
            cancelled = dep.get('cancelled', False)
            
            # Use actual or scheduled time
            time_to_display = actual if actual else scheduled
            
            # Parse time for display
            if time_to_display:
                if isinstance(time_to_display, datetime):
                    time_str = time_to_display.strftime('%H:%M')
                elif isinstance(time_to_display, str):
                    try:
                        dt = datetime.fromisoformat(time_to_display.replace('Z', '+00:00'))
                        time_str = dt.strftime('%H:%M')
                    except:
                        time_str = time_to_display
                else:
                    time_str = str(time_to_display)
            else:
                time_str = "??:??"
            
            if cancelled:
                status = " [CANCELLED]"
            elif delay and delay > 0:
                status = f" (+{delay})"
            else:
                status = ""
            
            print(f"{idx:2d}. {time_str}{status:15s} | {train_type:8s} | Track {platform:3s} | {destination}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_ret_station(client, station_code, station_name):
    """Test RET departures for a station."""
    print(f"\n{'='*70}")
    print(f"RET Departures: {station_name} ({station_code})")
    print(f"{'='*70}")
    
    try:
        departures = await client.async_get_departures(station_code)
        
        if not departures:
            print("❌ No departures found")
            return
        
        print(f"✅ Found {len(departures)} departures\n")
        
        for idx, dep in enumerate(departures[:10], 1):
            destination = dep.get('destination', 'Unknown')
            actual = dep.get('actual_time')
            scheduled = dep.get('scheduled_time')
            line = dep.get('line', '?')
            transport_type = dep.get('transport_type', 'Unknown')
            delay = dep.get('delay', 0)
            platform = dep.get('platform', '')
            
            # Use actual or scheduled time
            time_to_display = actual if actual else scheduled
            
            # Parse time for display
            if time_to_display:
                if isinstance(time_to_display, datetime):
                    time_str = time_to_display.strftime('%H:%M')
                elif isinstance(time_to_display, str):
                    try:
                        dt = datetime.fromisoformat(time_to_display.replace('Z', '+00:00'))
                        time_str = dt.strftime('%H:%M')
                    except:
                        time_str = time_to_display
                else:
                    time_str = str(time_to_display)
            else:
                time_str = "??:??"
            
            status = f" (+{delay})" if delay > 0 else ""
            platform_str = f"Platform {platform}" if platform else ""
            
            print(f"{idx:2d}. {time_str}{status:15s} | {transport_type:8s} {line:4s} | {platform_str:12s} | {destination}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Test departures from Rotterdam Centraal and Barendrecht."""
    print("="*70)
    print("Testing Departures: Rotterdam Centraal & Barendrecht")
    print("="*70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"NS API Key: {NS_API_KEY[:8]}...{NS_API_KEY[-8:]}\n")
    
    async with ClientSession() as session:
        # NS Client for train stations
        ns_client = NSAPIClient(session, NS_API_KEY)
        
        # RET Client for Rotterdam metro/tram/bus
        ret_client = RETAPIClient(session)
        
        # Test Rotterdam Centraal (NS - Trains)
        await test_ns_station(ns_client, "Rtd", "Rotterdam Centraal")
        
        # Test Rotterdam Centraal (RET - Metro/Tram/Bus)
        await test_ret_station(ret_client, "rotterdam-centraal", "Rotterdam Centraal")
        
        # Test Barendrecht (NS - Trains)
        await test_ns_station(ns_client, "Brd", "Barendrecht")
    
    print("\n" + "="*70)
    print("Testing Complete")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
