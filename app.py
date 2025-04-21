from flask import Flask, request, render_template, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import random
import time
import json
import logging
import sqlite3
import google.generativeai as genai
from ratelimit import limits, sleep_and_retry

app = Flask(__name__, static_url_path='/static')

# Налаштування логування (виведення в консоль для Render)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API ключі (замініть на справжній ключ із weatherapi.com, якщо цей не працює)
WEATHER_API_KEYS = [
    "f84e4d7d3b9f4e2e9e4d7d3b9f4e2e9",
    "f84e4d7d3b9f4e2e9e4d7d3b9f4e2e9",
    "f84e4d7d3b9f4e2e9e4d7d3b9f4e2e9"
]
current_weather_key_idx = 0

# Глобальні змінні
FISHING_DATA_CACHE = {"data": {}, "timestamp": {}}
WEATHER_CACHE = {}
WEATHER_CACHE_TIMESTAMP = {}
USER_CITIES = {}
USER_FISH = {}
USER_WATER_TYPE = {}
previous_pressure = {}

# Список риб із детальною інформацією
FISH_TYPES = {
    "Карась 🐠": {
        "temp_opt": {"весна": (15, 20), "літо": (18, 25), "осінь": (12, 18), "зима": (5, 10)},
        "pressure_opt": (1000, 1015),
        "recipes": [
            "Манка + мед: 200 г манки, 50 г меду, змішати з водою.",
            "Горохова каша: 300 г гороху, варити 2 години."
        ],
        "guide": {
            "description": "Карась — прісноводна риба, яка любить теплі водойми з мулистим дном.",
            "habitat": "Озера, ставки, повільні річки.",
            "best_time": "Ранок або вечір у теплу погоду (літо, рання осінь).",
            "tips": "Використовуй легкі снасті, уникай різких рухів, карась обережний."
        }
    },
    "Короп 🐟": {
        "temp_opt": {"весна": (15, 25), "літо": (20, 28), "осінь": (15, 22), "зима": (8, 12)},
        "pressure_opt": (1000, 1020),
        "recipes": [
            "Кукурудза + аніс: 300 г кукурудзи, 10 крапель анісової олії.",
            "Макуха: 250 г макухи, додати воду."
        ],
        "guide": {
            "description": "Короп — велика риба, яка потребує терпіння та міцних снастей.",
            "habitat": "Водосховища, ставки, глибокі річки.",
            "best_time": "Теплі дні, особливо після дощу.",
            "tips": "Використовуй солодкі прикормки, короп любить кукурудзу."
        }
    }
}

WATER_TYPES = ["Річка 🌊", "Озеро 🏞", "Ставок 🐟", "Водосховище ⚓"]

# Тимчасово відключена ініціалізація бази даних (через обмеження Render)
"""
def init_db():
    try:
        conn = sqlite3.connect('fishing_bot.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS user_history
                     (user_id TEXT, action TEXT, details TEXT, timestamp TEXT)''')
        conn.commit()
        conn.close()
        logger.info("База даних ініціалізована успішно")
    except Exception as e:
        logger.error(f"Помилка ініціалізації бази даних: {str(e)}")

init_db()
"""

# Перевірка кешу
def is_cache_valid(fish, ttl=86400):
    return (datetime.now() - FISHING_DATA_CACHE["timestamp"].get(fish, datetime.min)).total_seconds() < ttl

# Отримання погоди
def fetch_weather(city_query, endpoint="current.json"):
    global current_weather_key_idx
    url = f"http://api.weatherapi.com/v1/{endpoint}?key={WEATHER_API_KEYS[current_weather_key_idx]}&q={city_query}&lang=uk"
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429 or response.status_code >= 500:
                current_weather_key_idx = (current_weather_key_idx + 1) % len(WEATHER_API_KEYS)
                time.sleep(2)
                continue
        except Exception as e:
            logger.error(f"Помилка запиту погоди: {str(e)}")
            if attempt < retries - 1:
                current_weather_key_idx = (current_weather_key_idx + 1) % len(WEATHER_API_KEYS)
                time.sleep(2)
    return {"error": {"message": "Не вдалося отримати погоду"}}

# Обробник помилок 500
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Помилка 500: {str(error)}")
    return jsonify({"error": "Внутрішня помилка сервера", "details": str(error)}), 500

# Головна сторінка
@app.route('/')
def index():
    try:
        logger.info("Завантаження головної сторінки")
        return render_template('index.html', fish_types=FISH_TYPES.keys(), water_types=WATER_TYPES)
    except Exception as e:
        logger.error(f"Помилка при завантаженні головної сторінки: {str(e)}")
        return jsonify({"error": "Помилка завантаження головної сторінки", "details": str(e)}), 500

# Сторінка налаштувань
@app.route('/settings')
def settings():
    try:
        logger.info("Завантаження сторінки налаштувань")
        return render_template('settings.html')
    except Exception as e:
        logger.error(f"Помилка при завантаженні сторінки налаштувань: {str(e)}")
        return jsonify({"error": "Помилка завантаження сторінки налаштувань", "details": str(e)}), 500

# Сторінка посібника
@app.route('/fish_guide')
def fish_guide():
    try:
        logger.info("Завантаження сторінки посібника")
        return render_template('fish_guide.html', fish_types=FISH_TYPES)
    except Exception as e:
        logger.error(f"Помилка при завантаженні сторінки посібника: {str(e)}")
        return jsonify({"error": "Помилка завантаження сторінки посібника", "details": str(e)}), 500

# API для отримання погоди
@app.route('/get_weather', methods=['POST'])
def get_weather():
    try:
        data = request.json
        city = data.get('city')
        water_type = data.get('water_type', "Озеро 🏞")
        user_id = data.get('user_id', 'default_user')

        if not city:
            logger.warning("Місто не вказано у запиті на погоду")
            return jsonify({"error": "Місто не вказано!"})

        USER_CITIES[user_id] = city
        USER_WATER_TYPE[user_id] = water_type

        current_time = datetime.now()
        last_update = WEATHER_CACHE_TIMESTAMP.get(user_id)
        if last_update and (current_time - last_update).total_seconds() < 1800:
            logger.info(f"Погода для користувача {user_id} взята з кешу")
            cached_weather = WEATHER_CACHE[user_id]
            return jsonify(cached_weather)

        city_query = f"{city},Україна"
        response = fetch_weather(city_query)
        if "error" not in response:
            current = response["current"]
            temp = current["temp_c"]
            desc = current["condition"]["text"]
            pressure = current["pressure_mb"]
            water_temp = temp - 3  # Спрощена оцінка температури води

            pressure_change = pressure - previous_pressure.get(user_id, pressure)
            previous_pressure[user_id] = pressure

            weather_data = {
                "temp": temp,
                "water_temp": water_temp,
                "desc": desc,
                "pressure": pressure,
                "pressure_change": pressure_change
            }
            WEATHER_CACHE[user_id] = weather_data
            WEATHER_CACHE_TIMESTAMP[user_id] = current_time
            logger.info(f"Отримано погоду для {city}: {temp}°C")
            return jsonify(weather_data)
        else:
            error_msg = response.get('error', {}).get('message', 'Спробуй пізніше!')
            logger.error(f"Помилка погоди: {error_msg}")
            return jsonify({"error": error_msg})
    except Exception as e:
        logger.error(f"Помилка при отриманні погоди: {str(e)}")
        return jsonify({"error": "Помилка при отриманні погоди", "details": str(e)}), 500

# API для отримання рецептів
@app.route('/get_recipe', methods=['POST'])
def get_recipe():
    try:
        data = request.json
        fish = data.get('fish')
        user_id = data.get('user_id', 'default_user')

        if fish not in FISH_TYPES:
            logger.warning(f"Риба {fish} не знайдена")
            return jsonify({"error": "Риба не знайдена!"})

        USER_FISH[user_id] = [fish]
        recipe = random.choice(FISH_TYPES[fish]["recipes"])
        logger.info(f"Отримано рецепт для {fish}")
        return jsonify({"recipe": recipe})
    except Exception as e:
        logger.error(f"Помилка при отриманні рецепту: {str(e)}")
        return jsonify({"error": "Помилка при отриманні рецепту", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)