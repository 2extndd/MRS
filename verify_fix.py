
import logging
import asyncio
from pyMercariAPI.mercari import Mercari

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_close_method():
    logger.info("Testing Mercari.close() method...")
    
    try:
        # Create instance
        m = Mercari()
        logger.info("Mercari instance created")
        
        # Access internal loop to verify it exists
        loop = m._get_or_create_loop()
        logger.info(f"Event loop created: {loop}")
        
        if loop.is_closed():
            logger.error("Loop should be open!")
            return False
            
        # Call close
        logger.info("Calling close()...")
        m.close()
        
        # Verify loop is closed
        if not loop.is_closed():
            logger.error("Loop should be closed after close() call!")
            return False
            
        logger.info("✅ close() method works correctly (loop closed)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_close_method()
    if success:
        print("\n✅ VERIFICATION SUCCESSFUL")
        exit(0)
    else:
        print("\n❌ VERIFICATION FAILED")
        exit(1)
