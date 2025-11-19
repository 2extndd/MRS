"""
Image utilities for MercariSearcher
Download and encode images to base64 for storage in database
"""

import logging
import base64
import requests
from typing import Optional

logger = logging.getLogger(__name__)


def download_and_encode_image(image_url: str, timeout: int = 10, use_proxy: bool = True) -> Optional[str]:
    """
    Download image from URL and encode to base64
    Uses proxy rotation to bypass Railway IP blocking by Cloudflare

    Args:
        image_url: URL of the image to download
        timeout: Request timeout in seconds
        use_proxy: Whether to use proxy (True by default)

    Returns:
        Base64-encoded image string or None if failed
    """
    if not image_url:
        return None

    try:
        # Import proxy_rotator here to avoid circular imports
        from proxies import proxy_rotator
        
        # Headers to bypass Cloudflare (pretend to be browser from Mercari)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://jp.mercari.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }

        # Get proxy if available and enabled
        proxies = None
        current_proxy = None
        if use_proxy and proxy_rotator:
            proxy_dict = proxy_rotator.get_proxy()
            if proxy_dict:
                proxies = proxy_dict
                current_proxy = proxy_dict.get('http', 'unknown')
                logger.info(f"📡 Using proxy for image download: {current_proxy[:50]}...")
        
        # Download image with proxy
        logger.debug(f"Downloading image: {image_url[:80]}...")
        response = requests.get(image_url, headers=headers, proxies=proxies, timeout=timeout, stream=True)

        if response.status_code != 200:
            logger.warning(f"Failed to download image: HTTP {response.status_code} (proxy: {current_proxy[:50] if current_proxy else 'direct'})")
            
            # If 403 and using proxy, mark proxy as failed
            if response.status_code == 403 and proxies and proxy_rotator:
                logger.warning(f"⚠️  Proxy blocked (403), marking as failed: {current_proxy[:50]}...")
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

        # Check size (skip if too large - over 500KB)
        if image_size_kb > 500:
            logger.warning(f"Image too large: {image_size_kb:.1f}KB, skipping")
            return None

        # Encode to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Add data URI prefix for direct use in <img src="">
        image_format = content_type.split('/')[-1]  # e.g., 'jpeg', 'png', 'webp'
        data_uri = f"data:{content_type};base64,{base64_image}"

        logger.info(f"✅ Image encoded: {image_size_kb:.1f}KB → {len(data_uri)/1024:.1f}KB base64")
        return data_uri

    except requests.Timeout:
        logger.warning(f"Timeout downloading image from {image_url[:50]}... (proxy: {current_proxy[:50] if current_proxy else 'direct'})")
        
        # Mark proxy as failed on timeout
        if proxies and proxy_rotator:
            logger.warning(f"⚠️  Proxy timeout, marking as failed: {current_proxy[:50]}...")
            proxy_rotator.mark_current_failed()
        
        return None
    except requests.exceptions.ProxyError:
        logger.warning(f"Proxy connection error: {current_proxy[:50] if current_proxy else 'unknown'}")
        
        # Mark proxy as failed
        if proxies and proxy_rotator:
            proxy_rotator.mark_current_failed()
        
        return None
    except requests.RequestException as e:
        logger.warning(f"Request error downloading image: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error encoding image: {e}")
        return None


def resize_image_if_needed(image_bytes: bytes, max_width: int = 800) -> bytes:
    """
    Resize image if it's too large (optional optimization)

    Args:
        image_bytes: Image bytes
        max_width: Maximum width in pixels

    Returns:
        Resized image bytes or original if no resize needed
    """
    try:
        from PIL import Image
        from io import BytesIO

        # Open image
        img = Image.open(BytesIO(image_bytes))

        # Check if resize needed
        if img.width <= max_width:
            return image_bytes

        # Calculate new height maintaining aspect ratio
        ratio = max_width / img.width
        new_height = int(img.height * ratio)

        # Resize
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Save to bytes
        output = BytesIO()
        img.save(output, format=img.format or 'JPEG', quality=85, optimize=True)
        return output.getvalue()

    except ImportError:
        # PIL not installed, return original
        return image_bytes
    except Exception as e:
        logger.warning(f"Error resizing image: {e}")
        return image_bytes
