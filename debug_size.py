import asyncio
import logging
from pyMercariAPI.mercari import Mercari

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def recursive_inspect(obj, depth=0, visited=None):
    if visited is None:
        visited = set()
    
    if depth > 3:
        return
    
    indent = "  " * depth
    
    if hasattr(obj, '__dict__'):
        for k, v in obj.__dict__.items():
            if k.startswith('_'): continue
            
            # Check for size-related keys
            if 'size' in k.lower():
                print(f"{indent}FOUND SIZE KEY: {k} = {v}")
            
            if hasattr(v, '__dict__'):
                print(f"{indent}{k}: (object)")
                if id(v) not in visited:
                    visited.add(id(v))
                    recursive_inspect(v, depth + 1, visited)
            else:
                # Print value if it looks interesting
                if isinstance(v, (str, int, float, bool, list)):
                    # print(f"{indent}{k}: {v}")
                    pass

async def inspect_item_recursive(item_id):
    m = Mercari()
    api = m._get_mercapi()
    item = await api.item(item_id)
    
    if not item:
        print("Item not found!")
        return

    print("\n=== RECURSIVE INSPECTION ===")
    recursive_inspect(item)

if __name__ == "__main__":
    asyncio.run(inspect_item_recursive('m31827373838'))
