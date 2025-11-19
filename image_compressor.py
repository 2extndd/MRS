"""
Image compression utility for Web UI
Generates smaller thumbnails from base64 images to speed up page loading
"""

import base64
import io
from PIL import Image
import logging

logger = logging.getLogger(__name__)


def compress_image_data(image_data_uri: str, max_width: int = 400, quality: int = 75) -> str:
    """
    Compress base64 image for faster web UI loading
    
    Args:
        image_data_uri: Data URI (data:image/jpeg;base64,...)
        max_width: Maximum width for thumbnail
        quality: JPEG quality (1-95)
    
    Returns:
        Compressed data URI
    """
    try:
        if not image_data_uri or not image_data_uri.startswith('data:'):
            return image_data_uri
        
        # Parse data URI
        parts = image_data_uri.split(',', 1)
        if len(parts) != 2:
            return image_data_uri
        
        header = parts[0]  # data:image/jpeg;base64
        base64_data = parts[1]
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_data)
        
        # Open image with PIL
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed (for PNG with transparency)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Calculate new size maintaining aspect ratio
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Compress to JPEG
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        compressed_bytes = output.getvalue()
        
        # Encode back to base64
        compressed_base64 = base64.b64encode(compressed_bytes).decode('utf-8')
        
        # Create new data URI
        compressed_uri = f"data:image/jpeg;base64,{compressed_base64}"
        
        original_size = len(base64_data)
        compressed_size = len(compressed_base64)
        reduction = (1 - compressed_size / original_size) * 100
        
        logger.debug(f"Compressed image: {original_size/1024:.1f}KB → {compressed_size/1024:.1f}KB ({reduction:.1f}% reduction)")
        
        return compressed_uri
        
    except Exception as e:
        logger.error(f"Error compressing image: {e}")
        return image_data_uri  # Return original on error


def get_thumbnail_from_item(item: dict, max_width: int = 400) -> str:
    """
    Get compressed thumbnail from item dict
    
    Args:
        item: Item dictionary from database
        max_width: Maximum width for thumbnail
    
    Returns:
        Compressed image data URI or None
    """
    image_data = item.get('image_data')
    
    if not image_data:
        return None
    
    # Check if already compressed (cached)
    if '_thumbnail' in item and item['_thumbnail']:
        return item['_thumbnail']
    
    # Compress and return
    return compress_image_data(image_data, max_width=max_width, quality=75)


if __name__ == "__main__":
    # Test compression
    logging.basicConfig(level=logging.DEBUG)
    
    print("Image compressor utility")
    print("Use: from image_compressor import compress_image_data")
