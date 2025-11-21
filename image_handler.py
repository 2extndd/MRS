#!/usr/bin/env python3
"""
High-quality image handler for MercariSearcher
Downloads original/high-resolution images from Mercari CDN
"""

import logging
import base64
import requests
import re
import asyncio
from typing import Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


def get_original_image_url(image_url: str) -> str:
    """
    Convert any Mercari image URL to high-resolution version
    
    Strategy:
    - Mercari CDN uses w_XXX parameter for width
    - Use w_1200 for high quality (not /orig/ - Cloudflare blocks it!)
    - For Mercari Shops: use /large/ instead of /small/
    
    Args:
        image_url: Any Mercari image URL
        
    Returns:
        High-resolution URL
    """
    if not image_url:
        return None
    
    try:
        # Mercari Shops: replace /small/ with /large/
        if 'mercari-shops-static.com' in image_url or '/shops/' in image_url:
            # Handle different shops URL formats
            image_url = re.sub(r'/-/small/', '/-/large/', image_url)
            image_url = re.sub(r'/small/', '/large/', image_url)
            return image_url
        
        # Regular Mercari: upgrade to w_1200 (high quality, not blocked by Cloudflare)
        if 'mercdn.net' in image_url:
            if 'w_' in image_url:
                # Replace w_240 with w_1200
                return re.sub(r'w_\d+', 'w_1200', image_url)
            elif '/thumb/' in image_url:
                # Extract item ID and construct high-res URL
                match = re.search(r'm\d+_\d+', image_url)
                if match:
                    item_image_id = match.group(0)
                    query = ""
                    if '?' in image_url:
                        query = '?' + image_url.split('?')[1]
                    # Use /item/detail/orig/photos/ for original quality
                    return f"https://static.mercdn.net/item/detail/orig/photos/{item_image_id}.jpg{query}"
        
        return image_url
        
    except Exception as e:
        logger.warning(f"Error converting image URL: {e}")
        return image_url


async def get_all_item_images_async(item_id: str) -> List[str]:
    """
    Get ALL high-resolution images for a specific item using mercapi
    
    Args:
        item_id: Mercari item ID (e.g., 'm27150404280')
        
    Returns:
        List of high-resolution image URLs
    """
    try:
        from mercapi import Mercapi
        
        api = Mercapi()
        item = await api.item(item_id)
        
        if not item:
            logger.warning(f"Item not found: {item_id}")
            return []
        
        # Get photos - mercapi returns original URLs
        photos = getattr(item, 'photos', [])
        
        if photos:
            logger.info(f"Found {len(photos)} photos for item {item_id}")
            return photos
        else:
            # Fallback: convert thumbnails to high-res
            thumbnails = getattr(item, 'thumbnails', [])
            if thumbnails:
                logger.info(f"Using {len(thumbnails)} thumbnails for item {item_id}")
                return [get_original_image_url(t) for t in thumbnails]
            else:
                logger.warning(f"No images found for item {item_id}")
                return []
                
    except Exception as e:
        logger.error(f"Error getting item images: {e}")
        return []


def get_all_item_images(item_id: str) -> List[str]:
    """
    Synchronous wrapper for get_all_item_images_async
    
    Args:
        item_id: Mercari item ID
        
    Returns:
        List of high-resolution image URLs
    """
    try:
        return asyncio.run(get_all_item_images_async(item_id))
    except Exception as e:
        logger.error(f"Error in async image retrieval: {e}")
        return []


def download_and_encode_image(
    image_url: str, 
    timeout: int = 15, 
    use_proxy: bool = False,
    max_size_kb: int = 500
) -> Optional[str]:
    """
    Download high-resolution image and encode to base64 for database storage
    
    Args:
        image_url: URL of the image to download
        timeout: Request timeout in seconds
        use_proxy: Whether to use proxy (False by default - works without proxy!)
        max_size_kb: Maximum image size in KB
        
    Returns:
        Base64-encoded data URI or None if failed
    """
    if not image_url:
        return None
    
    try:
        # Convert to high-resolution URL first
        high_res_url = get_original_image_url(image_url)
        
        # Headers to mimic browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://jp.mercari.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        # Get proxy if enabled
        proxies = None
        current_proxy = None
        if use_proxy:
            from proxies import proxy_rotator
            if proxy_rotator:
                proxy_dict = proxy_rotator.get_proxy()
                if proxy_dict:
                    proxies = proxy_dict
                    current_proxy = proxy_dict.get('http', 'unknown')
                    logger.debug(f"Using proxy: {current_proxy[:50]}...")
        
        # Download image
        logger.debug(f"Downloading: {high_res_url[:80]}...")
        response = requests.get(high_res_url, headers=headers, proxies=proxies, timeout=timeout, stream=True)
        
        if response.status_code != 200:
            logger.warning(f"Failed: HTTP {response.status_code}")
            
            # Mark proxy as failed if 403
            if response.status_code == 403 and proxies:
                from proxies import proxy_rotator
                if proxy_rotator:
                    proxy_rotator.mark_current_failed()
            
            return None
        
        # Check content type
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            logger.warning(f"Invalid content type: {content_type}")
            return None
        
        # Read image bytes
        image_bytes = response.content
        image_size_kb = len(image_bytes) / 1024
        
        # Check size
        if image_size_kb > max_size_kb:
            logger.warning(f"Image too large: {image_size_kb:.1f}KB > {max_size_kb}KB, skipping")
            return None
        
        # Encode to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # Create data URI
        data_uri = f"data:{content_type};base64,{base64_image}"
        
        logger.info(f"✅ Image encoded: {image_size_kb:.1f}KB → {len(data_uri)/1024:.1f}KB base64")
        return data_uri
        
    except requests.Timeout:
        logger.warning(f"Timeout downloading image")
        if proxies:
            from proxies import proxy_rotator
            if proxy_rotator:
                proxy_rotator.mark_current_failed()
        return None
        
    except requests.exceptions.ProxyError:
        logger.warning(f"Proxy error")
        if proxies:
            from proxies import proxy_rotator
            if proxy_rotator:
                proxy_rotator.mark_current_failed()
        return None
        
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
        return None


def download_image_to_file(image_url: str, output_path: Path, timeout: int = 15) -> bool:
    """
    Download image to file (for testing/debugging)
    
    Args:
        image_url: Image URL
        output_path: Path to save image
        timeout: Request timeout
        
    Returns:
        True if successful
    """
    try:
        high_res_url = get_original_image_url(image_url)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://jp.mercari.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        }
        
        response = requests.get(high_res_url, headers=headers, timeout=timeout, stream=True)
        
        if response.status_code != 200:
            logger.error(f"Failed: HTTP {response.status_code}")
            return False
        
        # Save to file
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        size_kb = output_path.stat().st_size / 1024
        logger.info(f"✅ Saved: {output_path.name} ({size_kb:.1f}KB)")
        return True
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return False


if __name__ == "__main__":
    # Test image handler
    logging.basicConfig(level=logging.INFO)
    
    # Test URL conversion
    test_urls = [
        'https://static.mercdn.net/c!/w=240,f=webp/thumb/photos/m18043642062_1.jpg',
        'https://static.mercdn.net/thumb/item/webp/m27150404280_1.jpg?1763501290',
    ]
    
    print("\n=== Testing URL Conversion ===")
    for url in test_urls:
        high_res = get_original_image_url(url)
        print(f"\nOriginal: {url}")
        print(f"High-res: {high_res}")
    
    # Test download
    print("\n\n=== Testing Image Download ===")
    test_url = test_urls[0]
    high_res = get_original_image_url(test_url)
    
    print(f"\nDownloading: {high_res}")
    data_uri = download_and_encode_image(high_res)
    
    if data_uri:
        print(f"✅ Success! Size: {len(data_uri)/1024:.1f}KB base64")
    else:
        print("❌ Failed!")
