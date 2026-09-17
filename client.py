import os
import base64
import requests
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

BASE_URL = 'http://localhost:5000'

# --- 1. Проверка HTML-страницы ---------------------------------------------
r = requests.get(f'{BASE_URL}/')
print('GET /', r.status_code)
if r.status_code != 200:
    raise SystemExit(1)

# --- 2. Подготовка тестовой картинки ---------------------------------------
# Ищем бабочку с любым из возможных расширений
candidates = [
    os.path.join('static', 'test_input_2.png'),
    os.path.join('static', 'test_input_2.jpg'),
    os.path.join('static', 'test_input_2.jpeg'),
    os.path.join('static', 'test_input.png'),
    os.path.join('static', 'test_input.jpg'),
]

test_path = None
for c in candidates:
    if os.path.exists(c):
        test_path = c
        print('Using image:', test_path)
        break

# Если ничего не нашли — генерируем шумовой fallback
if test_path is None:
    test_path = os.path.join('static', 'test_input.png')
    arr = (np.random.rand(120, 120, 3) * 255).astype('uint8')
    Image.fromarray(arr).save(test_path)
    print('Generated random test image:', test_path)

with open(test_path, 'rb') as fh:
    b64 = base64.b64encode(fh.read()).decode('utf-8')

# --- 3. Запрос к JSON-API --------------------------------------------------
payload = {'imagebin': b64, 'noise_level': 0.4}
res = requests.post(f'{BASE_URL}/apinet', json=payload)
print('POST /apinet', res.status_code)
if not res.ok:
    print(res.text)
    raise SystemExit(1)

data = res.json()
print('Keys:', list(data.keys()))

# --- 4. Сохраняем зашумлённое изображение на диск --------------------------
os.makedirs('static', exist_ok=True)

# декодируем base64 обратно в файл PNG
noisy_bytes = base64.b64decode(data['noisy_image'])
noisy_path = os.path.join('static', 'noisy_result.png')
with open(noisy_path, 'wb') as fh:
    fh.write(noisy_bytes)
print('Saved:', noisy_path)

# сохраняем исходное изображение как reference
original_path = os.path.join('static', 'original_result.png')
img = Image.open(test_path).convert('RGB')
img.save(original_path)
print('Saved:', original_path)

# --- 5. Строим гистограммы обоих изображений для артефактов ----------------
def save_hist(img_path, out_path, title):
    arr = np.array(Image.open(img_path).convert('RGB'))
    fig, ax = plt.subplots(figsize=(6, 4))
    for i, color in enumerate(('r', 'g', 'b')):
        hist, bins = np.histogram(arr[:, :, i].ravel(), bins=256, range=(0, 256))
        ax.plot(bins[:-1], hist, color=color, alpha=0.7, label=color.upper())
    ax.set_xlabel('Интенсивность')
    ax.set_ylabel('Количество пикселей')
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=80)
    plt.close(fig)

save_hist(original_path,
          os.path.join('static', 'hist_original.png'),
          'Распределение цветов (исходное)')
save_hist(noisy_path,
          os.path.join('static', 'hist_noisy.png'),
          'Распределение цветов (зашумлённое)')
print('Histograms saved')

print('OK')