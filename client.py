import os
import base64
import requests
import numpy as np
from PIL import Image

BASE_URL = 'http://localhost:5000'

# --- 1. Проверка HTML-страницы ---------------------------------------------
r = requests.get(f'{BASE_URL}/')
print('GET /', r.status_code)
if r.status_code != 200:
    raise SystemExit(1)

# --- 2. Проверка JSON-API --------------------------------------------------
test_path = os.path.join('static', 'test_input.png')
if not os.path.exists(test_path):
    arr = (np.random.rand(120, 120, 3) * 255).astype('uint8')
    Image.fromarray(arr).save(test_path)

with open(test_path, 'rb') as fh:
    b64 = base64.b64encode(fh.read()).decode('utf-8')

payload = {'imagebin': b64, 'noise_level': 0.4}
res = requests.post(f'{BASE_URL}/apinet', json=payload)
print('POST /apinet', res.status_code)
if not res.ok:
    print(res.text)
    raise SystemExit(1)
print('Keys:', list(res.json().keys()))
print('OK')