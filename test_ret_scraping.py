"""Quick test script for the new RET web scraping implementation."""
import asyncio
import aiohttp
from custom_components.ret_ns_departures.api_ret import RETAPIClient


async def test_ret_client():
    """Test the RET client with real data."""
    async with aiohttp.ClientSession() as session:
        client = RETAPIClient(session)
        
        print("Testing RET client with Schiekade stop...")
        try:
            departures = await client.async_get_departures("schiekade", max_results=10)
            
            print(f"\n✅ Found {len(departures)} departures:")
            for dep in departures:
                print(f"  Line {dep['line']} → {dep['destination']}")
                print(f"    Scheduled: {dep['scheduled_time'].strftime('%H:%M')}")
                print(f"    Actual: {dep['actual_time'].strftime('%H:%M')}")
                if dep['delay'] > 0:
                    print(f"    Delay: {dep['delay']} min")
                print()
                
            # Test with line filter
            print("\nTesting with line filter (line 8 only)...")
            filtered = await client.async_get_departures(
                "schiekade", max_results=5, line_filter=["8"]
            )
            print(f"✅ Found {len(filtered)} departures for line 8")
            
            # Test stop validation
            print("\nTesting stop validation...")
            is_valid = await client.async_validate_stop("schiekade")
            print(f"✅ Stop 'schiekade' is valid: {is_valid}")
            
            # Test invalid stop
            try:
                await client.async_get_departures("invalidstopname123")
                print("❌ Should have failed for invalid stop")
            except Exception as e:
                print(f"✅ Correctly failed for invalid stop: {type(e).__name__}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_ret_client())
