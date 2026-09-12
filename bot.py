from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import requests
import json

# ============================================
#  НАСТРОЙКИ 
# ============================================
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Фиктивный веб-сервер для Render
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass  # отключаем логи

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# Запускаем в отдельном потоке
threading.Thread(target=run_health_server, daemon=True).start()
TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ============================================
#  ФУНКЦИЯ ПОИСКА В API
# ============================================
def search_movie(query):
    """Ищет фильм в PoiskKino API и возвращает информацию."""
    try:
        # Запрос к API (поиск по названию)
        url = f"https://api.poiskkino.dev/v1.4/movie/search?query={query.replace(' ', '+')}"
        headers = {"X-API-KEY": API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if data and data.get('docs') and len(data['docs']) > 0:
            # Берём первый результат
            movie = data['docs'][0]
            return {
                'id': movie.get('id'),
                'name': movie.get('name', 'Без названия'),
                'alternativeName': movie.get('alternativeName', ''),
                'year': movie.get('year', 'Год неизвестен'),
                'description': movie.get('description', 'Описание отсутствует'),
                'shortDescription': movie.get('shortDescription', ''),
                'rating': movie.get('rating', {}).get('kp', 0),
                'ratingImdb': movie.get('rating', {}).get('imdb', 0),
                'poster': movie.get('poster', {}).get('url', None),
                'genres': [genre['name'] for genre in movie.get('genres', [])[:3]],
                'countries': [country['name'] for country in movie.get('countries', [])[:2]],
                'trailer': movie.get('videos', {}).get('trailers', [{}])[0].get('url', None),
                'ageRating': movie.get('ageRating', ''),
                'movieLength': movie.get('movieLength', ''),
                'url': f"https://www.kinopoisk.ru/film/{movie.get('id')}/" if movie.get('id') else None,
            }
    except Exception as e:
        print(f"Ошибка API: {e}")
    return None

# ============================================
#  КОМАНДЫ БОТА
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск фильма", callback_data="search")],
        [InlineKeyboardButton("🎬 Топ-250", callback_data="top")]
    ]
    await update.message.reply_text(
        "🎬 *Кино-энциклопедия по PoiskKino API*\n\n"
        "📌 *Поиск:* напиши название фильма\n"
        "📌 *Топ-250:* список лучших фильмов\n"
        "📌 *Трейлеры:* с YouTube\n\n"
        "Нажми кнопку или просто напиши название!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "search":
        await query.edit_message_text("✍️ *Введите название фильма:*", parse_mode='Markdown')
        context.user_data['waiting_search'] = True
    
    elif query.data == "top":
        await query.edit_message_text("⏳ *Загружаю топ-250 фильмов...*", parse_mode='Markdown')
        # Здесь можно сделать запрос к API для топ-250
        await query.edit_message_text(
            "🎬 *Топ-250 фильмов:*\n\n"
            "1. Зеленая миля (1999) — 9.1\n"
            "2. Побег из Шоушенка (1994) — 9.3\n"
            "3. Крестный отец (1972) — 9.0\n\n"
            "🔍 *Ищи конкретный фильм через поиск!*",
            parse_mode='Markdown'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_search'):
        user_query = update.message.text
        await update.message.reply_text("🔎 *Ищу фильм...*", parse_mode='Markdown')
        
        movie = search_movie(user_query)
        
        if movie:
            # Формируем текст
            text = f"🎬 *{movie['name']}*"
            if movie['alternativeName']:
                text += f" ({movie['alternativeName']})"
            text += f"\n📅 *Год:* {movie['year']}"
            if movie['url']:
        text += f"\n\n🔗 [Открыть на Кинопоиске]({movie['url']})"
            
            if movie['movieLength']:
                text += f"\n⏱️ *Длительность:* {movie['movieLength']} мин"
            
            if movie['ageRating']:
                text += f"\n🔞 *Возраст:* {movie['ageRating']}+"
            
            if movie['genres']:
                text += f"\n🎭 *Жанры:* {', '.join(movie['genres'])}"
            
            if movie['countries']:
                text += f"\n🌍 *Страны:* {', '.join(movie['countries'])}"
            
            if movie['rating']:
                text += f"\n⭐ *Рейтинг КП:* {movie['rating']}"
            if movie['ratingImdb']:
                text += f"\n⭐ *Рейтинг IMDb:* {movie['ratingImdb']}"
            
            if movie['description']:
                text += f"\n\n📝 *Описание:* {movie['description'][:500]}..."
            
            # Отправляем постер
            if movie['poster']:
                await update.message.reply_photo(
                    photo=movie['poster'],
                    caption=text,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(text, parse_mode='Markdown')
            
            # Отправляем трейлер (если есть)
          # Отправляем кнопки (трейлер + ссылка на Кинопоиск)
buttons = []
if movie['trailer']:
    buttons.append([InlineKeyboardButton("▶️ Смотреть трейлер", url=movie['trailer'])])
if movie['url']:
    buttons.append([InlineKeyboardButton("🔗 Открыть на Кинопоиске", url=movie['url'])]) 

if buttons:
    await update.message.reply_text(
        "🎬 *Дополнительно:*",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )
        else:
            await update.message.reply_text(
                "😕 *Фильм не найден.*\n"
                "Проверьте название или попробуйте другой запрос.",
                parse_mode='Markdown'
            )
        
        context.user_data['waiting_search'] = False

# ============================================
#  ЗАПУСК БОТА
# ============================================
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот-энциклопедия запущен!")
    print("📚 Используется PoiskKino API")
    print(f"🔑 API-ключ: {API_KEY[:10]}...")
    app.run_polling()

if __name__ == "__main__":
    main()
