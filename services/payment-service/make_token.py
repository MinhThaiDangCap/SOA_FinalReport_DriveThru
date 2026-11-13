import sys
import time

import jwt

from app import config

user_id = sys.argv[1] if len(sys.argv) > 1 else "1"
role = sys.argv[2] if len(sys.argv) > 2 else "CUSTOMER"
station_id = int(sys.argv[3]) if len(sys.argv) > 3 else None

payload = {"sub": user_id, "role": role, "exp": int(time.time()) + 86400}
if station_id is not None:
    payload["station_id"] = station_id

print(jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM))