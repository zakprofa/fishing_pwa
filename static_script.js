// Реєстрація Service Worker
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/service-worker.js')
            .then(reg => console.log('Service Worker зареєстровано'))
            .catch(err => console.log('Помилка Service Worker:', err));
    });
}

// Застосування налаштувань при завантаженні сторінки
document.addEventListener('DOMContentLoaded', () => {
    const background = localStorage.getItem('background') || 'default';
    const region = localStorage.getItem('region') || 'Україна';
    applyBackground(background);
    if (document.getElementById('region')) {
        document.getElementById('region').value = region;
    }
    if (document.getElementById('background')) {
        document.getElementById('background').value = background;
    }
});

// Застосування фону
function applyBackground(background) {
    document.body.className = '';
    if (background !== 'default') {
        document.body.classList.add(`bg-${background}`);
    }
}

// Збереження налаштувань
function saveSettings() {
    const background = document.getElementById('background').value;
    const region = document.getElementById('region').value;
    localStorage.setItem('background', background);
    localStorage.setItem('region', region);
    applyBackground(background);
    alert('Налаштування збережено!');
}

// Отримання геолокації
function getLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(async (position) => {
            const { latitude, longitude } = position.coords;
            const response = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json&addressdetails=1`);
            const data = await response.json();
            let city = data.address.city || data.address.town || data.address.village || '';
            if (city) {
                document.getElementById('city').value = city;
            } else {
                alert('Не вдалося визначити місто. Введіть вручну.');
            }
        }, (error) => {
            alert('Помилка геолокації: ' + error.message);
        });
    } else {
        alert('Геолокація не підтримується вашим браузером.');
    }
}

// Отримання погоди
async function getWeather() {
    const city = document.getElementById('city').value;
    const water_type = document.getElementById('water_type').value;
    const region = localStorage.getItem('region') || 'Україна';
    if (!city) {
        alert('Введи місто!');
        return;
    }
    if (!navigator.onLine) {
        const lastWeather = JSON.parse(localStorage.getItem('lastWeather'));
        if (lastWeather) {
            document.getElementById('result').innerHTML = `
                🌡️ Офлайн-дані: ${lastWeather.temp}°C<br>
                💧 Температура води: ${lastWeather.water_temp}°C
            `;
        } else {
            document.getElementById('result').innerHTML = '❌ Немає офлайн-даних';
        }
        return;
    }
    const response = await fetch('/get_weather', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ city: `${city},${region}`, water_type, user_id: 'web_user' })
    });
    const data = await response.json();
    const resultDiv = document.getElementById('result');
    if (data.error) {
        resultDiv.innerHTML = `❌ Помилка: ${data.error}`;
    } else {
        resultDiv.innerHTML = `
            🌡️ Температура: ${data.temp}°C<br>
            💧 Температура води: ${data.water_temp}°C<br>
            ☁️ Погода: ${data.desc}<br>
            📊 Тиск: ${data.pressure} hPa (зміна: ${data.pressure_change} hPa)
        `;
        localStorage.setItem('lastWeather', JSON.stringify(data));
    }
}

// Отримання рецепту
async function getRecipe() {
    const fish = document.getElementById('fish').value;
    const response = await fetch('/get_recipe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fish, user_id: 'web_user' })
    });
    const data = await response.json();
    const resultDiv = document.getElementById('result');
    if (data.error) {
        resultDiv.innerHTML = `❌ Помилка: ${data.error}`;
    } else {
        resultDiv.innerHTML = `🍲 Рецепт для ${fish}:<br>${data.recipe}`;
    }
}