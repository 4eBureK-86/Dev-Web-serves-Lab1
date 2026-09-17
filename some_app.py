import os
import random
import base64
from io import BytesIO

import numpy as np
import matplotlib
matplotlib.use('Agg')          # обязательно для работы без дисплея
import matplotlib.pyplot as plt
from PIL import Image

from flask import Flask, render_template, url_for, request, Response, jsonify
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from flask_wtf.recaptcha import RecaptchaField
from wtforms import FloatField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from werkzeug.utils import secure_filename

# ----------------------------------------------------------------------------
# Настройка приложения
# ----------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'change_me_to_random_secret'
app.config['UPLOAD_FOLDER'] = 'static'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 МБ

# --- Ключи reCAPTCHA (получить на https://www.google.com/recaptcha/admin) ---
# Если ключей нет — оставить пустые строки, тогда капча отключится.
RECAPTCHA_PUBLIC = os.environ.get('RECAPTCHA_PUBLIC', '')
RECAPTCHA_PRIVATE = os.environ.get('RECAPTCHA_PRIVATE', '')
USE_CAPTCHA = bool(RECAPTCHA_PUBLIC and RECAPTCHA_PRIVATE)

if USE_CAPTCHA:
    app.config['RECAPTCHA_PUBLIC_KEY'] = RECAPTCHA_PUBLIC
    app.config['RECAPTCHA_PRIVATE_KEY'] = RECAPTCHA_PRIVATE
    app.config['RECAPTCHA_USE_SSL'] = False

bootstrap = Bootstrap(app)


# ----------------------------------------------------------------------------
# Форма ввода
# ----------------------------------------------------------------------------
class NoiseForm(FlaskForm):
    upload = FileField('Изображение', validators=[
        FileRequired(message='Выберите файл'),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'bmp'], 'Только изображения!')
    ])
    noise_level = FloatField(
        'Уровень шума (0.0 – 1.0)',
        validators=[DataRequired(), NumberRange(min=0.0, max=1.0)],
        default=0.3
    )
    if USE_CAPTCHA:
        recaptcha = RecaptchaField()
    submit = SubmitField('Зашумить')


# ----------------------------------------------------------------------------
# Вспомогательные функции обработки изображений
# ----------------------------------------------------------------------------
def add_noise(image, level):
    """
    Добавляет к изображению равномерный шум.
    level — число от 0 до 1, задающее амплитуду шума.
    """
    arr = np.array(image).astype(np.float32) / 255.0
    # равномерный шум в диапазоне [-level, +level]
    noise = (np.random.rand(*arr.shape) - 0.5) * 2.0 * level
    noisy = arr + noise
    noisy = np.clip(noisy, 0.0, 1.0)
    return (noisy * 255).astype(np.uint8)


def build_histogram(image, save_path, title):
    """Строит и сохраняет гистограмму распределения каналов R, G, B."""
    arr = np.array(image)
    fig, ax = plt.subplots(figsize=(6, 4))
    for i, color in enumerate(('r', 'g', 'b')):
        if arr.ndim == 3:
            hist, bins = np.histogram(arr[:, :, i].ravel(),
                                      bins=256, range=(0, 256))
            ax.plot(bins[:-1], hist, color=color, alpha=0.7,
                    label=color.upper())
        else:  # градации серого
            hist, bins = np.histogram(arr.ravel(), bins=256, range=(0, 256))
            ax.plot(bins[:-1], hist, color='k', label='Gray')
    ax.set_xlabel('Интенсивность')
    ax.set_ylabel('Количество пикселей')
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=80)
    plt.close(fig)


# ----------------------------------------------------------------------------
# Маршруты
# ----------------------------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
@app.route('/net', methods=['GET', 'POST'])
def net():
    form = NoiseForm()
    data = {
        'original_image': None,
        'noisy_image': None,
        'hist_original': None,
        'hist_noisy': None,
        'error': None,
        'noise_level': None,
    }

    if form.validate_on_submit():
        try:
            f = form.upload.data
            filename = secure_filename(f.filename)
            # уникальное имя, чтобы не перезаписывать
            base_name = f"{random.randint(100000, 999999)}_{filename}"
            original_path = os.path.join(app.config['UPLOAD_FOLDER'], base_name)
            f.save(original_path)

            # открываем, уменьшаем до 512 px, чтобы не тормозить
            original = Image.open(original_path).convert('RGB')
            original.thumbnail((512, 512))
            original.save(original_path)

            # зашумление
            noisy_arr = add_noise(original, float(form.noise_level.data))
            noisy = Image.fromarray(noisy_arr)
            noisy_name = f"noisy_{base_name}"
            noisy_path = os.path.join(app.config['UPLOAD_FOLDER'], noisy_name)
            noisy.save(noisy_path)

            # гистограммы
            stem = base_name.rsplit('.', 1)[0]
            hist_orig_name = f"hist_orig_{stem}.png"
            hist_noisy_name = f"hist_noisy_{stem}.png"
            build_histogram(
                original,
                os.path.join(app.config['UPLOAD_FOLDER'], hist_orig_name),
                'Распределение цветов (исходное)'
            )
            build_histogram(
                noisy,
                os.path.join(app.config['UPLOAD_FOLDER'], hist_noisy_name),
                'Распределение цветов (зашумлённое)'
            )

            data.update({
                'original_image': url_for('static', filename=base_name),
                'noisy_image':    url_for('static', filename=noisy_name),
                'hist_original':  url_for('static', filename=hist_orig_name),
                'hist_noisy':     url_for('static', filename=hist_noisy_name),
                'noise_level':    form.noise_level.data,
            })
        except Exception as e:
            data['error'] = f'Ошибка обработки: {e}'

    return render_template('net.html', form=form, **data)


@app.route('/apinet', methods=['POST'])
def apinet():
    """JSON-API: принимает base64-изображение и уровень шума, возвращает
    зашумлённое изображение в base64."""
    if request.mimetype != 'application/json':
        return Response('{"error":"application/json expected"}',
                        status=400, mimetype='application/json')

    payload = request.get_json(silent=True) or {}
    if 'imagebin' not in payload or 'noise_level' not in payload:
        return Response('{"error":"imagebin and noise_level required"}',
                        status=400, mimetype='application/json')

    try:
        raw = base64.b64decode(payload['imagebin'])
        img = Image.open(BytesIO(raw)).convert('RGB')
        img.thumbnail((512, 512))
        level = float(payload['noise_level'])
        noisy = Image.fromarray(add_noise(img, level))

        buf = BytesIO()
        noisy.save(buf, format='PNG')
        result_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        return jsonify({'noisy_image': result_b64})
    except Exception as e:
        return Response(f'{{"error":"{e}"}}',
                        status=500, mimetype='application/json')


# ----------------------------------------------------------------------------
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='127.0.0.1', port=5000, debug=True)
