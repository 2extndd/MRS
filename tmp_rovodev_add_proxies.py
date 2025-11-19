#!/usr/bin/env python3
"""
Add proxies to database in correct format
"""
import sys
sys.path.insert(0, '.')

from db import DatabaseManager

# Your 115 proxies in correct format
PROXIES = """82.21.62.51:7815:wtllhdak:9vxcxlvhxv1h
82.23.88.20:7776:wtllhdak:9vxcxlvhxv1h
96.62.187.26:7239:wtllhdak:9vxcxlvhxv1h
104.253.199.230:5509:wtllhdak:9vxcxlvhxv1h
159.148.236.107:6313:wtllhdak:9vxcxlvhxv1h
82.21.49.142:7405:wtllhdak:9vxcxlvhxv1h
150.241.111.109:6613:wtllhdak:9vxcxlvhxv1h
82.23.57.198:7452:wtllhdak:9vxcxlvhxv1h
82.21.35.207:7967:wtllhdak:9vxcxlvhxv1h
147.79.22.84:7800:wtllhdak:9vxcxlvhxv1h
82.21.130.78:7292:wtllhdak:9vxcxlvhxv1h
136.0.167.123:7126:wtllhdak:9vxcxlvhxv1h
82.21.62.134:7898:wtllhdak:9vxcxlvhxv1h
82.22.96.216:7924:wtllhdak:9vxcxlvhxv1h
82.21.38.105:7366:wtllhdak:9vxcxlvhxv1h
46.203.144.233:8000:wtllhdak:9vxcxlvhxv1h
82.29.143.253:7967:wtllhdak:9vxcxlvhxv1h
82.21.44.215:7977:wtllhdak:9vxcxlvhxv1h
179.61.172.198:6749:wtllhdak:9vxcxlvhxv1h
104.253.199.225:5504:wtllhdak:9vxcxlvhxv1h
31.98.7.191:6369:wtllhdak:9vxcxlvhxv1h
104.253.199.64:5343:wtllhdak:9vxcxlvhxv1h
45.39.157.162:9194:wtllhdak:9vxcxlvhxv1h
136.0.167.195:7198:wtllhdak:9vxcxlvhxv1h
136.0.167.46:7049:wtllhdak:9vxcxlvhxv1h
150.241.111.42:6546:wtllhdak:9vxcxlvhxv1h
46.202.3.38:7304:wtllhdak:9vxcxlvhxv1h
150.241.111.17:6521:wtllhdak:9vxcxlvhxv1h
46.202.34.65:7831:wtllhdak:9vxcxlvhxv1h
104.253.199.53:5332:wtllhdak:9vxcxlvhxv1h
46.203.184.72:7339:wtllhdak:9vxcxlvhxv1h
46.202.34.112:7878:wtllhdak:9vxcxlvhxv1h
82.23.88.27:7783:wtllhdak:9vxcxlvhxv1h
104.253.199.156:5435:wtllhdak:9vxcxlvhxv1h
104.253.248.237:6016:wtllhdak:9vxcxlvhxv1h
150.241.117.26:5530:wtllhdak:9vxcxlvhxv1h
45.39.157.183:9215:wtllhdak:9vxcxlvhxv1h
136.0.167.235:7238:wtllhdak:9vxcxlvhxv1h
136.0.167.175:7178:wtllhdak:9vxcxlvhxv1h
136.0.167.172:7175:wtllhdak:9vxcxlvhxv1h
104.253.248.212:5991:wtllhdak:9vxcxlvhxv1h
82.23.88.176:7932:wtllhdak:9vxcxlvhxv1h
45.39.157.84:9116:wtllhdak:9vxcxlvhxv1h
104.253.199.91:5370:wtllhdak:9vxcxlvhxv1h
136.0.167.124:7127:wtllhdak:9vxcxlvhxv1h
166.0.42.126:6134:wtllhdak:9vxcxlvhxv1h
166.0.42.168:6176:wtllhdak:9vxcxlvhxv1h
82.23.88.6:7762:wtllhdak:9vxcxlvhxv1h
104.253.248.33:5812:wtllhdak:9vxcxlvhxv1h
150.241.117.250:5754:wtllhdak:9vxcxlvhxv1h
82.23.88.36:7792:wtllhdak:9vxcxlvhxv1h
104.253.199.252:5531:wtllhdak:9vxcxlvhxv1h
45.39.157.172:9204:wtllhdak:9vxcxlvhxv1h
82.23.88.57:7813:wtllhdak:9vxcxlvhxv1h
45.39.157.109:9141:wtllhdak:9vxcxlvhxv1h
104.253.199.126:5405:wtllhdak:9vxcxlvhxv1h
104.253.199.177:5456:wtllhdak:9vxcxlvhxv1h
136.0.167.95:7098:wtllhdak:9vxcxlvhxv1h
45.39.157.58:9090:wtllhdak:9vxcxlvhxv1h
150.241.117.7:5511:wtllhdak:9vxcxlvhxv1h
166.0.42.123:6131:wtllhdak:9vxcxlvhxv1h
45.39.157.219:9251:wtllhdak:9vxcxlvhxv1h
82.23.88.203:7959:wtllhdak:9vxcxlvhxv1h
104.253.248.108:5887:wtllhdak:9vxcxlvhxv1h
150.241.111.25:6529:wtllhdak:9vxcxlvhxv1h
150.241.117.231:5735:wtllhdak:9vxcxlvhxv1h
136.0.167.185:7188:wtllhdak:9vxcxlvhxv1h
104.253.248.53:5832:wtllhdak:9vxcxlvhxv1h
104.253.199.160:5439:wtllhdak:9vxcxlvhxv1h
45.39.157.13:9045:wtllhdak:9vxcxlvhxv1h
136.0.167.138:7141:wtllhdak:9vxcxlvhxv1h
104.253.199.158:5437:wtllhdak:9vxcxlvhxv1h
166.0.42.245:6253:wtllhdak:9vxcxlvhxv1h
150.241.111.200:6704:wtllhdak:9vxcxlvhxv1h
104.253.248.240:6019:wtllhdak:9vxcxlvhxv1h
166.0.42.155:6163:wtllhdak:9vxcxlvhxv1h
166.0.42.230:6238:wtllhdak:9vxcxlvhxv1h
150.241.117.33:5537:wtllhdak:9vxcxlvhxv1h
104.253.199.42:5321:wtllhdak:9vxcxlvhxv1h
45.39.157.180:9212:wtllhdak:9vxcxlvhxv1h
104.253.199.92:5371:wtllhdak:9vxcxlvhxv1h
166.0.42.215:6223:wtllhdak:9vxcxlvhxv1h
150.241.117.235:5739:wtllhdak:9vxcxlvhxv1h
82.23.88.179:7935:wtllhdak:9vxcxlvhxv1h
104.253.248.55:5834:wtllhdak:9vxcxlvhxv1h
45.39.157.62:9094:wtllhdak:9vxcxlvhxv1h
104.253.248.2:5781:wtllhdak:9vxcxlvhxv1h
150.241.117.96:5600:wtllhdak:9vxcxlvhxv1h
150.241.111.162:6666:wtllhdak:9vxcxlvhxv1h
150.241.117.55:5559:wtllhdak:9vxcxlvhxv1h
82.23.88.108:7864:wtllhdak:9vxcxlvhxv1h
150.241.117.84:5588:wtllhdak:9vxcxlvhxv1h
136.0.167.174:7177:wtllhdak:9vxcxlvhxv1h
104.253.248.44:5823:wtllhdak:9vxcxlvhxv1h
150.241.117.97:5601:wtllhdak:9vxcxlvhxv1h
150.241.117.148:5652:wtllhdak:9vxcxlvhxv1h
150.241.111.37:6541:wtllhdak:9vxcxlvhxv1h
104.253.248.177:5956:wtllhdak:9vxcxlvhxv1h
104.253.248.217:5996:wtllhdak:9vxcxlvhxv1h
82.23.88.142:7898:wtllhdak:9vxcxlvhxv1h
104.253.248.137:5916:wtllhdak:9vxcxlvhxv1h
136.0.167.158:7161:wtllhdak:9vxcxlvhxv1h
150.241.117.72:5576:wtllhdak:9vxcxlvhxv1h
104.253.199.95:5374:wtllhdak:9vxcxlvhxv1h
82.23.88.90:7846:wtllhdak:9vxcxlvhxv1h
166.0.42.181:6189:wtllhdak:9vxcxlvhxv1h
104.253.199.242:5521:wtllhdak:9vxcxlvhxv1h
104.253.248.148:5927:wtllhdak:9vxcxlvhxv1h
104.253.248.59:5838:wtllhdak:9vxcxlvhxv1h
104.253.248.157:5936:wtllhdak:9vxcxlvhxv1h
82.23.88.232:7988:wtllhdak:9vxcxlvhxv1h
82.23.88.87:7843:wtllhdak:9vxcxlvhxv1h
104.253.248.29:5808:wtllhdak:9vxcxlvhxv1h
45.39.157.241:9273:wtllhdak:9vxcxlvhxv1h
104.253.248.23:5802:wtllhdak:9vxcxlvhxv1h""".strip()

def main():
    print("=" * 80)
    print("Adding proxies to database")
    print("=" * 80)
    
    db = DatabaseManager()
    
    # Count proxies
    proxy_lines = [l.strip() for l in PROXIES.split('\n') if l.strip()]
    print(f"\n📊 Total proxies to add: {len(proxy_lines)}")
    print(f"First proxy: {proxy_lines[0]}")
    print(f"Last proxy: {proxy_lines[-1]}")
    
    # Save to database
    print("\n💾 Saving to database...")
    db.save_config('PROXY_ENABLED', 'true')
    db.save_config('PROXY_LIST', PROXIES)
    
    # Verify
    print("\n✅ Verifying...")
    enabled = db.load_config('PROXY_ENABLED')
    proxy_list = db.load_config('PROXY_LIST')
    
    saved_proxies = [l.strip() for l in proxy_list.split('\n') if l.strip()]
    
    print(f"PROXY_ENABLED: {enabled}")
    print(f"Proxies saved: {len(saved_proxies)}")
    
    if len(saved_proxies) == len(proxy_lines):
        print("\n✅ SUCCESS! All proxies saved correctly!")
    else:
        print(f"\n⚠️  WARNING: Expected {len(proxy_lines)} but saved {len(saved_proxies)}")
    
    print("\n" + "=" * 80)
    print("✅ DONE! Proxies are now in the database.")
    print("Worker will use them on next restart or config reload.")
    print("=" * 80)

if __name__ == "__main__":
    main()
