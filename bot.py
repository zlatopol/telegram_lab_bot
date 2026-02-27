"""
Простейший Telegram бот для проверки лабораторных работ через OpenRouter
"""

import asyncio
import os
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from dotenv import load_dotenv
from openai import OpenAI

from file_utils import extract_docx, extract_pdf, extract_txt


# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

if not BOT_TOKEN or not OPENROUTER_KEY:
    print("❌ Добавьте токены в .env файл!")
    print("📝 Пример .env файла:")
    print("TELEGRAM_BOT_TOKEN=ваш_токен")
    print("OPENROUTER_API_KEY=ваш_ключ")
    exit(1)

# Инициализация
bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# OpenRouter клиент
openrouter = OpenAI(
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# Поддерживаемые форматы
SUPPORTED_FORMATS = ['.pdf', '.docx', '.txt']
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 МБ

def get_main_keyboard():
    """Главная клавиатура"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")],
        [InlineKeyboardButton(text="📊 Модели", callback_data="models")]
    ])

@dp.message(CommandStart())
async def start_command(message: Message):
    """Команда /start"""
    await message.answer(
        f"🎓 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        "Я проверяю лабораторные работы с помощью ИИ.\n\n"
        "📄 <b>Как пользоваться:</b>\n"
        "1. Отправь мне файл с работой\n"
        "2. Подожди проверку (1-2 минуты)\n"
        "3. Получи оценку и рекомендации\n\n"
        "📁 <b>Поддерживаю:</b> PDF, DOCX, TXT (до 20 МБ)\n"
        "🤖 <b>Использую:</b> Лучшую доступную бесплатную модель\n\n"
        "<i>Просто отправь файл и я проверю!</i>",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("help"))
async def help_command(message: Message):
    """Команда /help"""
    await message.answer(
        "📖 <b>Как пользоваться ботом:</b>\n\n"
        "1️⃣ Отправь мне файл с лабораторной работой\n"
        "2️⃣ Жди проверку от ИИ (1-2 минуты)\n"
        "3️⃣ Получи детальную оценку\n\n"
        "<b>📁 Поддерживаемые форматы:</b>\n"
        "• PDF (до 20 МБ)\n"
        "• DOCX (Microsoft Word)\n"
        "• TXT (текстовые файлы)\n\n"
        "<b>📊 Что проверяется:</b>\n"
        "• Качество кода и решения (0-30)\n"
        "• Полнота реализации (0-30)\n" 
        "• Документация (0-20)\n"
        "• Оформление работы (0-20)\n\n"
        "<b>🤖 Используемые ИИ модели:</b>\n"
        "• openrouter/free - авто выбор лучшей\n"
        "• Список моделей: /models\n\n"
        "<b>💡 Итог:</b> Оценка из 100 баллов + рекомендации",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("models"))
async def models_command(message: Message):
    """Список доступных моделей"""
    await message.answer(
        "🤖 <b>Доступные бесплатные модели:</b>\n\n"
        "• <b>openrouter/free</b> - авто выбор лучшей\n"
        "• <b>deepseek/deepseek-r1:free</b> - для сложных задач\n"
        "• <b>arcee-ai/trinity-large-preview:free</b> - креатив\n"
        "• <b>google/gemini-2.0-flash-exp:free</b> - быстрая\n"
        "• <b>qwen/qwen-2.5-72b-instruct:free</b> - мощная\n"
        "• <b>meta-llama/llama-3.3-70b-instruct:free</b> - Llama\n\n"
        "<i>По умолчанию используется openrouter/free</i>",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "help")
async def help_callback(callback):
    """Помощь через callback"""
    await help_command(callback.message)

@dp.callback_query(F.data == "models")
async def models_callback(callback):
    """Модели через callback"""
    await models_command(callback.message)

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_text(message: Message):
    """Обработка текстовых сообщений"""
    await message.answer(
        "📄 <b>Отправь файл для проверки!</b>\n\n"
        "Я не анализирую текстовые сообщения.\n"
        "Просто прикрепи файл с лабораторной работой.\n\n"
        "Поддерживаю: PDF, DOCX, TXT",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.document)
async def handle_document(message: Message):
    """Обработка файла"""
    document = message.document
    file_name = document.file_name
    file_size = document.file_size
    
    # Проверка размера
    if file_size > MAX_FILE_SIZE:
        await message.answer(
            f"❌ <b>Файл слишком большой!</b>\n\n"
            f"📏 Размер файла: {file_size / 1024 / 1024:.1f} МБ\n"
            f"📏 Максимум: {MAX_FILE_SIZE / 1024 / 1024} МБ\n\n"
            f"Попробуй сжать файл или выбрать другой.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Проверка формата
    file_ext = Path(file_name).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        await message.answer(
            f"❌ <b>Неподдерживаемый формат!</b>\n\n"
            f"📄 Твой файл: <code>{file_ext}</code>\n"
            f"📁 Поддерживаю: <code>{', '.join(SUPPORTED_FORMATS)}</code>\n\n"
            f"Преобразуй файл в подходящий формат.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Показываем статус обработки
    status_msg = await message.answer(
        "⏳ <b>Проверяю работу...</b>\n\n"
        "🔄 Загружаю файл...\n"
        "⏳ Извлекаю содержимое...\n"
        "⏳ Анализирую с помощью ИИ...\n\n"
        "<i>Обычно занимает 1-2 минуты</i>"
    )
    
    temp_path = None
    
    try:
        # Загружаем файл
        file = await bot.get_file(document.file_id)
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp_file:
            await bot.download_file(file.file_path, tmp_file.name)
            temp_path = tmp_file.name
        
        await status_msg.edit_text(
            "⏳ <b>Проверяю работу...</b>\n\n"
            "✅ Файл загружен\n"
            "🔄 Извлекаю содержимое...\n"
            "⏳ Анализирую с помощью ИИ..."
        )
        
        # Извлекаем содержимое в зависимости от типа файла
        if file_ext == '.txt':
            content = await extract_txt(temp_path)
        elif file_ext == '.docx':
            content = await extract_docx(temp_path)
        elif file_ext == '.pdf':
            content = await extract_pdf(temp_path)
        else:
            raise Exception("Неподдерживаемый формат")
        
        # Проверяем, что содержимое не пустое
        if not content or not content.strip():
            raise Exception("Файл пуст или не содержит читаемого текста")
        
        # Обрезаем слишком длинный контент (безопасный лимит для модели)
        if len(content) > 15000:
            content = content[:15000] + "...\n\n[Текст обрезан из-за длины]"
            await status_msg.edit_text(
                "⏳ <b>Проверяю работу...</b>\n\n"
                "✅ Файл загружен\n"
                "✅ Содержимое извлечено (обрезано до 15000 символов)\n"
                "🔄 Анализирую с помощью ИИ...\n\n"
                "<i>ИИ анализирует работу...</i>"
            )
        else:
            await status_msg.edit_text(
                "⏳ <b>Проверяю работу...</b>\n\n"
                "✅ Файл загружен\n"
                "✅ Содержимое извлечено\n"
                "🔄 Анализирую с помощью ИИ...\n\n"
                "<i>ИИ анализирует работу...</i>"
            )
        
        # Отправляем на проверку
        result = await check_with_ai(content)
        
        # Удаляем временный файл
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        
        # Отправляем информацию о файле
        await status_msg.edit_text(
            "✅ <b>Проверка завершена!</b>\n\n"
            f"📄 <b>Файл:</b> <code>{file_name}</code>\n"
            f"📊 <b>Размер:</b> {file_size / 1024:.1f} КБ\n"
            f"📝 <b>Символов:</b> {len(content):,}\n"
            f"🤖 <b>Модель:</b> openrouter/free (автовыбор)"
        )
        
        # Разбиваем длинный результат на части (Telegram ограничение 4096 символов)
        if len(result) > 4000:
            parts = [result[i:i+4000] for i in range(0, len(result), 4000)]
            for i, part in enumerate(parts):
                clean_part = clean_text(part)
                if i == 0:
                    await message.answer(f"📋 <b>Результат проверки:</b>\n\n{clean_part}")
                else:
                    await message.answer(f"📋 <b>Продолжение ({i+1}/{len(parts)}):</b>\n\n{clean_part}")
        else:
            clean_result = clean_text(result)
            await message.answer(f"📋 <b>Результат проверки:</b>\n\n{clean_result}")
        
        # Предлагаем проверить еще файл
        await message.answer(
            "🎉 <b>Готово!</b>\n\n"
            "Можешь отправить еще один файл для проверки 📄",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        # Удаляем временный файл в случае ошибки
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
        
        error_text = str(e)
        await status_msg.edit_text(
            f"❌ <b>Ошибка при обработке файла</b>\n\n"
            f"<code>{error_text[:200]}</code>\n\n"
            f"Попробуй еще раз или выбери другой файл.",
            reply_markup=get_main_keyboard()
        )

async def check_with_ai(content: str) -> str:
    """Проверка работы через OpenRouter"""
    
    prompt = f"""Ты - эксперт по проверке лабораторных работ. Проанализируй работу студента.

КРИТЕРИИ ОЦЕНКИ (100 баллов максимум):
1. Качество кода и решения (0-30 баллов)
2. Полнота и правильность реализации (0-30 баллов)  
3. Документация и комментарии (0-20 баллов)
4. Оформление и структура работы (0-20 баллов)

ФОРМАТ ОТВЕТА:
📊 КРАТКИЙ АНАЛИЗ:
[2-3 предложения о работе]

📈 ОЦЕНКА ПО КРИТЕРИЯМ:
• Качество кода: X/30 - [обоснование]
• Полнота реализации: X/30 - [обоснование]
• Документация: X/20 - [обоснование]
• Оформление: X/20 - [обоснование]

✅ СИЛЬНЫЕ СТОРОНЫ:
• [список]

💡 ЧТО УЛУЧШИТЬ:
• [конкретные рекомендации]

🎯 ИТОГОВАЯ ОЦЕНКА: X/100

СОДЕРЖИМОЕ РАБОТЫ:
{content}

Будь справедлив, но требователен. Пиши понятно для студента."""
    
    try:
        # Используем openrouter/free для автовыбора лучшей бесплатной модели
        response = openrouter.chat.completions.create(
            model="openrouter/free",  # ИСПРАВЛЕНО: было "qopenrouter/free"
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.4
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"❌ <b>Ошибка при обращении к ИИ</b>\n\n{str(e)}\n\nПопробуйте еще раз через несколько минут."

# Функция для очистки текста
def clean_text(text: str) -> str:
    """Удаляет markdown-разметку и оставляет чистый текст"""
    # Заменяем ** на пустоту (убираем жирный)
    text = text.replace('**', '')
    # Заменяем * на пустоту (убираем курсив)
    text = text.replace('*', '')
    # Заменяем _ на пустоту
    text = text.replace('_', '')
    # Заменяем ` на пустоту (код)
    text = text.replace('`', '')
    return text

# Запуск бота
async def main():
    print("=" * 50)
    print("🤖 Telegram бот для проверки лабораторных работ")
    print("=" * 50)
    print(f"📁 Поддерживаемые форматы: {', '.join(SUPPORTED_FORMATS)}")
    print(f"📊 Макс. размер файла: {MAX_FILE_SIZE / 1024 / 1024} МБ")
    print("🤖 Модель: openrouter/free (автовыбор лучшей)")
    print("⚡ Бот запущен! Отправьте файл для проверки")
    print("=" * 50)
    print("🛑 Для остановки нажмите Ctrl+C")
    print("=" * 50)
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())