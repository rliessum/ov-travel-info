#!/usr/bin/env python3
"""
Test script for NS APIs (Departures and Disruptions)
Tests using the subscription key from .env file
"""
import asyncio
import aiohttp
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
NS_API_KEY = os.getenv('ReisinformatiePrimaryKey')
NS_DEPARTURES_BASE_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2"
NS_DISRUPTIONS_BASE_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3"

# Test stations
TEST_STATIONS = [
    {"code": "Rtd", "name": "Rotterdam Centraal"},
    {"code": "Ut", "name": "Utrecht Centraal"},
    {"code": "Asd", "name": "Amsterdam Centraal"},
]


async def test_departures_api(session: aiohttp.ClientSession, station_code: str, station_name: str):
    """Test NS Departures API"""
    print(f"\n{'='*60}")
    print(f"Testing Departures API for {station_name} ({station_code})")
    print(f"{'='*60}")
    
    url = f"{NS_DEPARTURES_BASE_URL}/departures"
    params = {
        "station": station_code,
        "maxJourneys": 5,
    }
    headers = {
        "Ocp-Apim-Subscription-Key": NS_API_KEY,
    }
    
    try:
        async with session.get(url, params=params, headers=headers) as response:
            print(f"Status Code: {response.status}")
            print(f"URL: {response.url}")
            
            if response.status == 200:
                data = await response.json()
                print(f"✅ SUCCESS - Retrieved {len(data.get('payload', {}).get('departures', []))} departures")
                
                # Display first 3 departures
                departures = data.get('payload', {}).get('departures', [])[:3]
                print(f"\nNext departures:")
                for idx, dep in enumerate(departures, 1):
                    direction = dep.get('direction', 'Unknown')
                    planned_time = dep.get('plannedDateTime', '')
                    actual_time = dep.get('actualDateTime', planned_time)
                    train_category = dep.get('trainCategory', 'Unknown')
                    platform = dep.get('actualTrack', dep.get('plannedTrack', '?'))
                    
                    # Parse time
                    if actual_time:
                        dt = datetime.fromisoformat(actual_time.replace('Z', '+00:00'))
                        time_str = dt.strftime('%H:%M')
                    else:
                        time_str = '??:??'
                    
                    print(f"  {idx}. {time_str} - {train_category} to {direction} (Platform {platform})")
                
                return True
            else:
                error_text = await response.text()
                print(f"❌ FAILED - Status {response.status}")
                print(f"Response: {error_text}")
                return False
                
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False


async def test_disruptions_api(session: aiohttp.ClientSession, station_code: str = None, station_name: str = None):
    """Test NS Disruptions API"""
    print(f"\n{'='*60}")
    if station_code:
        print(f"Testing Disruptions API for {station_name} ({station_code})")
    else:
        print(f"Testing Disruptions API (All Current Disruptions)")
    print(f"{'='*60}")
    
    url = f"{NS_DISRUPTIONS_BASE_URL}/disruptions"
    params = {}
    if station_code:
        params['station'] = station_code
    params['isActive'] = 'true'
    
    headers = {
        "Ocp-Apim-Subscription-Key": NS_API_KEY,
    }
    
    try:
        async with session.get(url, params=params, headers=headers) as response:
            print(f"Status Code: {response.status}")
            print(f"URL: {response.url}")
            
            if response.status == 200:
                data = await response.json()
                # API returns a list directly, not wrapped in 'payload'
                disruptions = data if isinstance(data, list) else data.get('payload', [])
                print(f"✅ SUCCESS - Found {len(disruptions)} active disruption(s)")
                
                if disruptions:
                    print(f"\nDisruption Details:")
                    for idx, dis in enumerate(disruptions[:5], 1):  # Show max 5
                        title = dis.get('title', 'No title')
                        dis_type = dis.get('type', 'UNKNOWN')
                        impact = dis.get('impact', {}).get('value', 0)
                        start = dis.get('start', '')
                        expected_duration = dis.get('expectedDuration', {}).get('description', 'Unknown')
                        
                        print(f"\n  {idx}. {title}")
                        print(f"     Type: {dis_type}")
                        print(f"     Impact: {impact}/5")
                        print(f"     Start: {start}")
                        print(f"     Expected Duration: {expected_duration}")
                        
                        # Show affected sections
                        sections = dis.get('timespans', [{}])[0].get('situation', {}).get('label', '')
                        if sections:
                            print(f"     Affected: {sections}")
                else:
                    print(f"\n  ✅ No active disruptions")
                
                return True
            else:
                error_text = await response.text()
                print(f"❌ FAILED - Status {response.status}")
                print(f"Response: {error_text}")
                return False
                
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False


async def test_disruptions_station_endpoint(session: aiohttp.ClientSession, station_code: str, station_name: str):
    """Test NS Disruptions API with station-specific endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing Station Disruptions Endpoint for {station_name} ({station_code})")
    print(f"{'='*60}")
    
    url = f"{NS_DISRUPTIONS_BASE_URL}/disruptions/station/{station_code}"
    headers = {
        "Ocp-Apim-Subscription-Key": NS_API_KEY,
    }
    
    try:
        async with session.get(url, headers=headers) as response:
            print(f"Status Code: {response.status}")
            print(f"URL: {response.url}")
            
            if response.status == 200:
                data = await response.json()
                # API returns a list directly, not wrapped in 'payload'
                disruptions = data if isinstance(data, list) else data.get('payload', [])
                print(f"✅ SUCCESS - Found {len(disruptions)} disruption(s) affecting this station")
                
                if disruptions:
                    for idx, dis in enumerate(disruptions[:3], 1):
                        title = dis.get('title', 'No title')
                        dis_type = dis.get('type', 'UNKNOWN')
                        print(f"  {idx}. [{dis_type}] {title}")
                else:
                    print(f"  ✅ No disruptions affecting this station")
                
                return True
            else:
                error_text = await response.text()
                print(f"❌ FAILED - Status {response.status}")
                print(f"Response: {error_text}")
                return False
                
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False


async def main():
    """Main test execution"""
    print("="*60)
    print("NS API Testing Script")
    print("="*60)
    print(f"API Key: {NS_API_KEY[:8]}...{NS_API_KEY[-8:]}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        'departures': [],
        'disruptions_general': False,
        'disruptions_station': [],
    }
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Departures API for each station
        print(f"\n\n{'#'*60}")
        print("TEST 1: NS DEPARTURES API")
        print(f"{'#'*60}")
        
        for station in TEST_STATIONS:
            success = await test_departures_api(session, station['code'], station['name'])
            results['departures'].append({'station': station['name'], 'success': success})
            await asyncio.sleep(0.5)  # Rate limiting
        
        # Test 2: General Disruptions API (all current disruptions)
        print(f"\n\n{'#'*60}")
        print("TEST 2: NS DISRUPTIONS API (GENERAL)")
        print(f"{'#'*60}")
        
        results['disruptions_general'] = await test_disruptions_api(session)
        await asyncio.sleep(0.5)
        
        # Test 3: Station-specific disruptions
        print(f"\n\n{'#'*60}")
        print("TEST 3: NS DISRUPTIONS API (STATION-SPECIFIC)")
        print(f"{'#'*60}")
        
        for station in TEST_STATIONS:
            success = await test_disruptions_api(session, station['code'], station['name'])
            results['disruptions_station'].append({'station': station['name'], 'success': success})
            await asyncio.sleep(0.5)
        
        # Test 4: Alternative station endpoint
        print(f"\n\n{'#'*60}")
        print("TEST 4: NS DISRUPTIONS API (STATION ENDPOINT)")
        print(f"{'#'*60}")
        
        for station in TEST_STATIONS[:1]:  # Test just one station
            await test_disruptions_station_endpoint(session, station['code'], station['name'])
    
    # Summary
    print(f"\n\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    print("\nDepartures API:")
    for result in results['departures']:
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        print(f"  {status} - {result['station']}")
    
    print("\nDisruptions API (General):")
    status = "✅ PASS" if results['disruptions_general'] else "❌ FAIL"
    print(f"  {status}")
    
    print("\nDisruptions API (Station-specific):")
    for result in results['disruptions_station']:
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        print(f"  {status} - {result['station']}")
    
    # Overall status
    all_departures = all(r['success'] for r in results['departures'])
    all_disruptions = all(r['success'] for r in results['disruptions_station'])
    
    print(f"\n{'='*60}")
    if all_departures and results['disruptions_general'] and all_disruptions:
        print("🎉 ALL TESTS PASSED - APIs are working correctly!")
    else:
        print("⚠️  SOME TESTS FAILED - Check details above")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
