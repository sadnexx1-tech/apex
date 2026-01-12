import asyncio
import logging
import json
import os
import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
import aiohttp
from yookassa import Payment, Configuration

# ═══════════════════════════════════════════════════════════════
# ⚙️ КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
CHANNEL_ID = '@your_channel_name'  # ← ЗАМЕНИ НА СВОЙ КАНАЛ

# YooKassa конфигурация
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ═══════════════════════════════════════════════════════════════
# 💾 КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════

PLANS = {
    'lite': {
        'title': 'Lite',
        'limit': 10,
        'price': 10000,  # 100 рублей
        'description': 'Видеолекции + 10 запросов/месяц'
    },
    'pro': {
        'title': 'Pro',
        'limit': 50,
        'price': 20000,  # 200 рублей
        'description': 'Полный доступ + 50 запросов/месяц'
    },
    'unlimited': {
        'title': 'Unlimited',
        'limit': 9999,
        'price': 50000,  # 500 рублей
        'description': 'Полный доступ + неограниченные запросы'
    }
}

# Фото для сообщений (премиум оформление)
PHOTOS = {
    'menu': 'https://user-gen-media-assets.s3.amazonaws.com/seedream_images/5a22a59b-4f8d-420a-98fb-0a79e204fee3.png'
}

# Тексты на разных языках
TEXTS = {
    'ru': {
        'subscribe_first': 'Сначала подпишитесь на канал!',
        'limit_exhausted': 'Лимит запросов исчерпан! На тарифе {0} доступно {1} запросов в месяц.',
        'error': 'Произошла ошибка: {0}',
        'payment_success': '✅ Платеж успешно обработан! Вы получили доступ.',
        'payment_failed': '❌ Платеж не прошел. Попробуйте еще раз.',
    },
    'en': {
        'subscribe_first': 'Please subscribe to the channel first!',
        'limit_exhausted': 'Request limit exceeded! Your plan {0} includes {1} requests per month.',
        'error': 'An error occurred: {0}',
        'payment_success': '✅ Payment processed successfully! You have access.',
        'payment_failed': '❌ Payment failed. Please try again.',
    }
}

# ═══════════════════════════════════════════════════════════════
# 📂 УПРАВЛЕНИЕ ДАННЫМИ ПОЛЬЗОВАТЕЛЕЙ
# ═══════════════════════════════════════════════════════════════

SUBS_FILE = 'subscriptions.json'

def load_subs():
    """Загружает данные подписок"""
    if os.path.exists(SUBS_FILE):
        with open(SUBS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_subs(subs):
    """Сохраняет данные подписок"""
    with open(SUBS_FILE, 'w', encoding='utf-8') as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)

def get_default_months():
    """Создает объект месяцев для нового пользователя"""
    months = {}
    for i in range(1, 13):
        months[str(i)] = {'used': 0}
    return months

def get_current_month():
    """Получает номер текущего месяца"""
    return str(datetime.datetime.now().month)

def get_user_language(user_id):
    """Получает язык пользователя"""
    subs = load_subs()
    user_data = subs.get(str(user_id), {})
    return user_data.get('language', 'ru')

def set_user_language(user_id, lang):
    """Устанавливает язык пользователя"""
    subs = load_subs()
    user_id_str = str(user_id)
    if user_id_str not in subs:
        subs[user_id_str] = {
            'language': lang,
            'plan': None,
            'months': get_default_months(),
            'join_date': datetime.datetime.now().isoformat()
        }
    else:
        subs[user_id_str]['language'] = lang
    save_subs(subs)

def get_text(key, lang, *args):
    """Получает текст на нужном языке"""
    text = TEXTS.get(lang, TEXTS['ru']).get(key, '')
    if args:
        return text.format(*args)
    return text

# ═══════════════════════════════════════════════════════════════
# 🎁 ФУНКЦИИ ДЛЯ TRIAL ПЕРИОДА
# ═══════════════════════════════════════════════════════════════

def give_trial_access(user_id):
    """Выдает тестовый доступ при первой подписке на канал"""
    subs = load_subs()
    user_id_str = str(user_id)
    
    # Если пользователя нет в базе - это первый раз
    if user_id_str not in subs:
        return True  # Выдаем тестовый доступ
    
    user_data = subs[user_id_str]
    
    # Если нет плана - это первый раз
    if not user_data.get('plan'):
        return True  # Выдаем тестовый доступ
    
    return False  # Уже был тестовый доступ

# ═══════════════════════════════════════════════════════════════
# 📊 ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ЛИМИТАМИ
# ═══════════════════════════════════════════════════════════════

def increment_usage(user_id):
    """Проверяет лимит и увеличивает счетчик использования (включая trial)"""
    subs = load_subs()
    user_id_str = str(user_id)
    
    if user_id_str not in subs:
        return False
    
    user_data = subs[user_id_str]
    plan = user_data.get('plan')
    
    # ОБРАБОТКА TRIAL ПЕРИОДА
    if plan == 'trial':
        # Если trial запрос еще не использован
        if not user_data.get('trial_used', False):
            user_data['trial_used'] = True
            save_subs(subs)
            return True
        else:
            # Trial запрос уже использован
            return False
    
    if plan not in PLANS:
        return False
    
    month = get_current_month()
    if month not in user_data.get('months', {}):
        return False
    
    month_data = user_data['months'][month]
    limit = PLANS[plan]['limit']
    
    if month_data['used'] >= limit:
        return False
    
    # Увеличиваем счетчик
    month_data['used'] += 1
    save_subs(subs)
    
    return True

# ═══════════════════════════════════════════════════════════════
# 🎓 ФУНКЦИИ ДЛЯ КУРСОВ
# ═══════════════════════════════════════════════════════════════

def get_recommended_courses(lang='ru', limit=8):
    """Генерирует список рекомендованных курсов с ID для кликабельности"""
    
    courses_ru = [
        {'id': 'python', 'name': '🎓 Python для начинающих'},
        {'id': 'django', 'name': '💻 Веб-разработка с Django'},
        {'id': 'datascience', 'name': '📊 Data Science и анализ данных'},
        {'id': 'figma', 'name': '🎨 Дизайн и Figma'},
        {'id': 'react', 'name': '📱 Мобильная разработка на React Native'},
        {'id': 'devops', 'name': '🚀 DevOps и Docker'},
        {'id': 'cybersecurity', 'name': '🔐 Cybersecurity основы'},
        {'id': 'marketing', 'name': '📈 Маркетинг и аналитика'},
        {'id': 'ml', 'name': '🤖 Машинное обучение с TensorFlow'},
        {'id': 'cloud', 'name': '☁️ Cloud AWS и облачные технологии'}
    ]
    
    courses_en = [
        {'id': 'python', 'name': '🎓 Python for Beginners'},
        {'id': 'django', 'name': '💻 Web Development with Django'},
        {'id': 'datascience', 'name': '📊 Data Science and Analytics'},
        {'id': 'figma', 'name': '🎨 Design and Figma'},
        {'id': 'react', 'name': '📱 Mobile Development React Native'},
        {'id': 'devops', 'name': '🚀 DevOps and Docker'},
        {'id': 'cybersecurity', 'name': '🔐 Cybersecurity Basics'},
        {'id': 'marketing', 'name': '📈 Marketing and Analytics'},
        {'id': 'ml', 'name': '🤖 Machine Learning with TensorFlow'},
        {'id': 'cloud', 'name': '☁️ Cloud AWS and Cloud Technologies'}
    ]
    
    courses = courses_ru if lang == 'ru' else courses_en
    return courses[:limit]

def search_course(query):
    """Ищет курсы в базе по запросу"""
    courses_data = {
        'python': [('py_basic', 'Основы Python'), ('py_data', 'Python для анализа данных'), ('py_web', 'Web разработка на Python')],
        'django': [('dj_intro', 'Django для начинающих'), ('dj_advanced', 'Advanced Django'), ('dj_rest', 'Django REST Framework')],
        'datascience': [('ds_intro', 'Data Science основы'), ('ds_ml', 'Machine Learning'), ('ds_viz', 'Data Visualization')],
        'figma': [('fig_basic', 'Figma основы'), ('fig_design', 'UI/UX Design'), ('fig_proto', 'Prototyping')],
        'react': [('react_basic', 'React основы'), ('react_native', 'React Native'), ('react_advanced', 'Advanced React')],
        'devops': [('devops_docker', 'Docker и контейнеризация'), ('devops_k8s', 'Kubernetes'), ('devops_ci', 'CI/CD')],
        'cybersecurity': [('sec_basic', 'Cybersecurity основы'), ('sec_network', 'Network Security'), ('sec_web', 'Web Security')],
        'marketing': [('mark_seo', 'SEO оптимизация'), ('mark_smm', 'SMM маркетинг'), ('mark_analytics', 'Analytics')],
        'ml': [('ml_basic', 'ML основы'), ('ml_tensor', 'TensorFlow'), ('ml_nlp', 'Natural Language Processing')],
        'cloud': [('aws_intro', 'AWS введение'), ('aws_ec2', 'EC2 и вычисления'), ('aws_db', 'Базы данных в AWS')]
    }
    
    return courses_data.get(query, [])

def get_premium_lectures(course_id, plan='pro'):
    """Возвращает список премиум видеолекций"""
    lectures = [
        {
            'title': f'🏆 Профессиональный курс: {course_id}',
            'description': 'Полный видеокурс от ведущих экспертов',
            'url': f'https://youtube.com/results?search_query={course_id}+tutorial'
        },
        {
            'title': f'📚 Интенсив: Мастерство в {course_id}',
            'description': 'Ускоренная программа обучения',
            'url': f'https://youtube.com/results?search_query={course_id}+advanced'
        },
        {
            'title': f'🎯 Практический тренинг: {course_id}',
            'description': 'Реальные кейсы и примеры',
            'url': f'https://youtube.com/results?search_query={course_id}+projects'
        },
        {
            'title': f'⭐ Мастер-класс по {course_id}',
            'description': 'Эксклюзивные техники от профессионалов',
            'url': f'https://youtube.com/results?search_query={course_id}+masterclass'
        },
        {
            'title': f'🚀 Быстрый старт в {course_id}',
            'description': 'От новичка к профессионалу за 30 дней',
            'url': f'https://youtube.com/results?search_query={course_id}+beginner'
        }
    ]
    return lectures

# ═══════════════════════════════════════════════════════════════
# 🤖 КОМАНДЫ И ОБРАБОТЧИКИ
# ═══════════════════════════════════════════════════════════════

@dp.message(Command('start'))
async def start_command(message: types.Message):
    """Команда /start"""
    user_id = message.from_user.id
    subs = load_subs()
    user_id_str = str(user_id)
    
    # Проверяем язык или предлагаем выбрать
    if user_id_str not in subs:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🇷🇺 Русский', callback_data='lang_ru')],
            [InlineKeyboardButton(text='🇬🇧 English', callback_data='lang_en')]
        ])
        await message.answer('Выберите язык / Choose language:', reply_markup=kb)
    else:
        lang = subs[user_id_str].get('language', 'ru')
        if lang == 'ru':
            text = '👋 Добро пожаловать в CourseBot!\n\nПожалуйста, проверьте подписку на канал.'
        else:
            text = '👋 Welcome to CourseBot!\n\nPlease verify your channel subscription.'
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Проверить подписку' if lang == 'ru' else '✅ Check subscription', callback_data='check_sub')],
            [InlineKeyboardButton(text='🌍 Язык' if lang == 'ru' else '🌍 Language', callback_data='change_language')]
        ])
        
        await message.answer_photo(
            photo=PHOTOS['menu'],
            caption=text,
            reply_markup=kb
        )

@dp.callback_query(F.data.startswith('lang_'))
async def handle_language(callback: types.CallbackQuery):
    """Обработчик выбора языка"""
    lang = callback.data.replace('lang_', '')
    user_id = callback.from_user.id
    set_user_language(user_id, lang)
    
    if lang == 'ru':
        text = '✅ Язык установлен: Русский\n\nТеперь проверьте подписку на канал и нажмите кнопку ниже.'
        button_text = '✅ Проверить подписку'
    else:
        text = '✅ Language set: English\n\nNow verify your channel subscription and click the button below.'
        button_text = '✅ Check subscription'
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, callback_data='check_sub')]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == 'check_sub')
async def check_sub(callback: types.CallbackQuery):
    """Проверка подписки на канал"""
    lang = get_user_language(callback.from_user.id)
    user_id = callback.from_user.id
    
    try:
        member = await bot.get_chat_member(CHANNEL_ID, callback.from_user.id)
        if member.status in ['member', 'administrator', 'creator']:
            
            # Проверяем первый раз ли это - выдаем тестовый доступ
            is_first_time = give_trial_access(callback.from_user.id)
            
            subs = load_subs()
            user_id_str = str(callback.from_user.id)
            
            # ЕСЛИ ПЕРВЫЙ РАЗ - ВЫДАЕМ TRIAL НА ВСЕХ ТАРИФАХ
            if is_first_time:
                # Добавляем пользователя с пробным доступом
                if user_id_str not in subs:
                    subs[user_id_str] = {
                        'plan': 'trial',
                        'trial_used': False,  # Флаг что пробный запрос еще не использован
                        'months': get_default_months(),
                        'premium_end': None,
                        'join_date': datetime.datetime.now().isoformat()
                    }
                else:
                    # Обновляем существующего пользователя
                    subs[user_id_str]['plan'] = 'trial'
                    subs[user_id_str]['trial_used'] = False
                
                save_subs(subs)
                
                if lang == 'ru':
                    success_text = '''🎁 ПОЗДРАВЛЯЕМ! ВЫ АКТИВИРОВАЛИ ТЕСТОВЫЙ ПЕРИОД! 🎁

╔═════════════════════════════════════════╗
║  ✅ ПОДПИСКА НА КАНАЛ АКТИВИРОВАНА      ║
║  🎁 ТЕСТОВЫЙ ПЕРИОД: 1 БЕСПЛАТНЫЙ ЗАПРОС║
╚═════════════════════════════════════════╝

Спасибо за подписку на наш канал! 🙌

Вы получили:

🎯 1 БЕСПЛАТНЫЙ ЗАПРОС для тестирования
💎 Доступ ко всем премиум курсам на этот запрос
📚 Видеолекции и материалы
⭐ Полный функционал нашего сервиса

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Используйте свой бесплатный запрос прямо сейчас!

После этого вы сможете:

💳 Выбрать удобный тариф подписки
🚀 Получить неограниченный доступ
🔥 Пользоваться всеми возможностями

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'''
                else:
                    success_text = '''🎁 CONGRATULATIONS! YOU ACTIVATED TRIAL PERIOD! 🎁

╔═════════════════════════════════════════╗
║  ✅ CHANNEL SUBSCRIPTION ACTIVATED       ║
║  🎁 TRIAL PERIOD: 1 FREE REQUEST        ║
╚═════════════════════════════════════════╝

Thank you for subscribing to our channel! 🙌

You received:

🎯 1 FREE REQUEST for testing
💎 Access to all premium courses for this request
📚 Video lectures and materials
⭐ Full functionality of our service

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use your free request right now!

After that you can:

💳 Choose a convenient subscription plan
🚀 Get unlimited access
🔥 Use all features

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'''
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='🔍 Попробовать' if lang == 'ru' else '🔍 Try Now', callback_data='search_start')],
                    [InlineKeyboardButton(text='📦 Подписки' if lang == 'ru' else '📦 Plans', callback_data='plans')],
                    [InlineKeyboardButton(text='🌍 Язык' if lang == 'ru' else '🌍 Language', callback_data='change_language')]
                ])
            
            # ЕСЛИ НЕ ПЕРВЫЙ РАЗ - ОБЫЧНОЕ МЕНЮ
            else:
                user_data = subs.get(user_id_str, {})
                user_plan = user_data.get('plan')
                
                # ДЛЯ LITE: ТОЛЬКО ВИДЕОЛЕКЦИИ
                if user_plan == 'lite':
                    if lang == 'ru':
                        success_text = '''✨ ДОБРО ПОЖАЛОВАТЬ В LITE! ✨

╔═════════════════════════════════════════╗
║  ✅ ПОДПИСКА АКТИВИРОВАНА               ║
║  🎬 ВИДЕОЛЕКЦИИ ДОСТУПНЫ                ║
╚═════════════════════════════════════════╝

Вы получили доступ к:

🎬 Видеолекциям от YouTube
📚 Курируемым материалам
⭐ Быстрому старту

💡 На плане Lite доступны только видеолекции.
🎯 Обновитесь на Pro для полного контента!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Выберите раздел:'''
                    else:
                        success_text = '''✨ WELCOME TO LITE! ✨

╔═════════════════════════════════════════╗
║  ✅ SUBSCRIPTION ACTIVATED               ║
║  🎬 VIDEO LECTURES AVAILABLE             ║
╚═════════════════════════════════════════╝

You have access to:

🎬 Video lectures from YouTube
📚 Curated materials
⭐ Quick start

💡 Lite plan includes video lectures only.
🎯 Upgrade to Pro for full content!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Select a section:'''
                    
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text='🆙 Обновить на Pro' if lang == 'ru' else '🆙 Upgrade to Pro', callback_data='buy_pro')],
                        [InlineKeyboardButton(text='🔍 Поиск' if lang == 'ru' else '🔍 Search', callback_data='search_start')],
                        [InlineKeyboardButton(text='🏠 Меню' if lang == 'ru' else '🏠 Menu', callback_data='menu')]
                    ])
                
                # ДЛЯ PRO И UNLIMITED: ПОЛНЫЙ ФУНКЦИОНАЛ + КУРСЫ
                else:
                    if lang == 'ru':
                        success_text = '''✨ ДОБРО ПОЖАЛОВАТЬ В ПРЕМИУМ СООБЩЕСТВО! ✨

╔═════════════════════════════════════════╗
║  ✅ ПОДПИСКА АКТИВИРОВАНА               ║
║  💎 ПРЕМИУМ ДОСТУП ОТКРЫТ               ║
╚═════════════════════════════════════════╝

Вы получили доступ к:

🎬 Премиум видеокурсам
📚 Курируемым лекциям от экспертов
🏆 Практическим тренингам
⭐ Мастер-классам
🔥 Эксклюзивному контенту

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📚 РЕКОМЕНДУЕМЫЕ КУРСЫ ДЛЯ ВАС:

'''
                    else:
                        success_text = '''✨ WELCOME TO PREMIUM COMMUNITY! ✨

╔═════════════════════════════════════════╗
║  ✅ SUBSCRIPTION ACTIVATED               ║
║  💎 PREMIUM ACCESS GRANTED               ║
╚═════════════════════════════════════════╝

You have access to:

🎬 Premium video courses
📚 Curated lectures from experts
🏆 Practical trainings
⭐ Master classes
🔥 Exclusive content

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📚 RECOMMENDED COURSES FOR YOU:

'''
                    
                    # Добавляем список рекомендованных курсов
                    recommended_courses = get_recommended_courses(lang, limit=8)
                    for i, course in enumerate(recommended_courses, 1):
                        success_text += f'{i}️⃣ {course["name"]}\n'
                    
                    success_text += '\n🎯 Начните обучение прямо сейчас!\n'
                    success_text += '💬 Поддержка доступна в любой момент\n'
                    
                    # КНОПКИ ДЛЯ КУРСОВ
                    course_buttons = []
                    for course in recommended_courses:
                        course_buttons.append([InlineKeyboardButton(text=course["name"], callback_data=f'course_{course["id"]}')])
                    
                    # ОСНОВНЫЕ КНОПКИ
                    main_buttons = [
                        [InlineKeyboardButton(text='📦 Подписки' if lang == 'ru' else '📦 Plans', callback_data='plans')],
                        [InlineKeyboardButton(text='📊 Мой лимит' if lang == 'ru' else '📊 My limit', callback_data='my_limit')],
                        [InlineKeyboardButton(text='🔍 Поиск курсов' if lang == 'ru' else '🔍 Search courses', callback_data='search_start')],
                        [InlineKeyboardButton(text='💬 Поддержка' if lang == 'ru' else '💬 Support', callback_data='support')],
                        [InlineKeyboardButton(text='👥 О нас' if lang == 'ru' else '👥 About', callback_data='about')],
                        [InlineKeyboardButton(text='🌍 Язык' if lang == 'ru' else '🌍 Language', callback_data='change_language')]
                    ]
                    
                    kb = InlineKeyboardMarkup(inline_keyboard=course_buttons + main_buttons)
            
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=PHOTOS['menu'],
                    caption=success_text
                ),
                reply_markup=kb
            )
        else:
            await callback.answer(get_text('subscribe_first', lang), show_alert=True)
    except Exception as e:
        await callback.answer(get_text('error', lang, str(e)), show_alert=True)

@dp.callback_query(lambda c: c.data.startswith('course_'))
async def handle_course_click(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик нажатия на рекомендованный курс с выдачей связанных курсов"""
    lang = get_user_language(callback.from_user.id)
    user_id = callback.from_user.id
    
    # Извлекаем ID курса
    course_id = callback.data.replace('course_', '')
    
    # Проверяем лимит
    if not increment_usage(user_id):
        subs = load_subs()
        user_data = subs.get(str(user_id), {})
        plan = user_data.get('plan')
        
        if not plan:
            await callback.answer(get_text('subscribe_first', lang), show_alert=True)
        elif plan == 'trial':
            # Trial запрос уже использован
            if lang == 'ru':
                msg = '🎁 Ваш тестовый запрос уже использован!\n\n💳 Пожалуйста, выберите подходящий тариф для продолжения.'
            else:
                msg = '🎁 Your trial request has been used!\n\n💳 Please choose a subscription plan to continue.'
            await callback.answer(msg, show_alert=True)
        else:
            await callback.answer(get_text('limit_exhausted', lang, PLANS[plan]['title'], PLANS[plan]['limit']), show_alert=True)
        return
    
    # Получаем информацию о тарифе
    subs = load_subs()
    user_data = subs.get(str(user_id), {})
    user_plan = user_data.get('plan')
    
    # ИЩЕМ РЕАЛЬНЫЕ КУРСЫ ИЗ БАЗЫ, СВЯЗАННЫЕ С ЗАПРОСОМ
    results = search_course(course_id)
    
    # ДЛЯ LITE: ВИДЕОЛЕКЦИИ + ИНФОРМАЦИЯ О КУРСАХ
    if user_plan == 'lite':
        if lang == 'ru':
            text = f'🎬 ВИДЕОЛЕКЦИИ ПО ТЕМЕ: "{course_id.upper()}"\n\n'
        else:
            text = f'🎬 VIDEO LECTURES ON: "{course_id.upper()}"\n\n'
        
        # Показываем курсы из базы (информационно)
        if results:
            if lang == 'ru':
                text += '📚 СВЯЗАННЫЕ КУРСЫ (доступны на Pro/Unlimited):\n\n'
            else:
                text += '📚 RELATED COURSES (available on Pro/Unlimited):\n\n'
            for i, (key, name) in enumerate(results, 1):
                text += f'{i}️⃣ {name}\n'
            text += '\n'
        
        # Добавляем видеолекции
        if lang == 'ru':
            text += '═'*50 + '\n'
            text += '🎬 ВИДЕОЛЕКЦИИ С YOUTUBE:\n'
            text += '═'*50 + '\n\n'
        else:
            text += '═'*50 + '\n'
            text += '🎬 YOUTUBE VIDEO LECTURES:\n'
            text += '═'*50 + '\n\n'
        
        premium_lectures = get_premium_lectures(course_id, user_plan)
        for i, lecture in enumerate(premium_lectures, 1):
            text += f'{i}️⃣ {lecture["title"]}\n'
            text += f'   📝 {lecture["description"]}\n'
            text += f'   🔗 {lecture["url"]}\n\n'
        
        text += '─'*50 + '\n'
        text += f'💡 На вашем плане доступны только видеолекции\n'
        text += f'🎯 Обновитесь на Pro для полного доступа к курсам\n\n'
        
        month = get_current_month()
        month_data = user_data['months'][month]
        remaining = PLANS[user_data['plan']]['limit'] - month_data['used']
        text += f'📊 Осталось запросов: {remaining}\n'
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🆙 Обновить на Pro' if lang == 'ru' else '🆙 Upgrade to Pro', callback_data='buy_pro')],
            [InlineKeyboardButton(text='🔙 Назад' if lang == 'ru' else '🔙 Back', callback_data='menu')]
        ])
    
    # ДЛЯ PRO И UNLIMITED: ПОЛНЫЙ КОНТЕНТ + ВСЕ КУРСЫ
    else:
        if lang == 'ru':
            text = f'🎓 ПОЛНЫЙ КУРС: {course_id.upper()}\n\n'
            text += '═'*50 + '\n'
            text += '📚 СВЯЗАННЫЕ КУРСЫ ИЗ НАШЕЙ БАЗЫ:\n'
            text += '═'*50 + '\n\n'
        else:
            text = f'🎓 FULL COURSE: {course_id.upper()}\n\n'
            text += '═'*50 + '\n'
            text += '📚 RELATED COURSES FROM OUR DATABASE:\n'
            text += '═'*50 + '\n\n'
        
        if results:
            for i, (key, name) in enumerate(results, 1):
                text += f'{i}️⃣ ✅ {name}\n'
            text += '\n'
        else:
            if lang == 'ru':
                text += 'Курсы по этой теме пока не добавлены, но видеолекции доступны!\n\n'
            else:
                text += 'No courses on this topic yet, but video lectures are available!\n\n'
        
        # Добавляем видеолекции
        if lang == 'ru':
            text += '═'*50 + '\n'
            text += '💎 ПРЕМИУМ ВИДЕОЛЕКЦИИ:\n'
            text += '═'*50 + '\n\n'
        else:
            text += '═'*50 + '\n'
            text += '💎 PREMIUM VIDEO LECTURES:\n'
            text += '═'*50 + '\n\n'
        
        premium_lectures = get_premium_lectures(course_id, user_plan)
        for i, lecture in enumerate(premium_lectures, 1):
            text += f'{i}️⃣ {lecture["title"]}\n'
            text += f'   📝 {lecture["description"]}\n'
            text += f'   🔗 {lecture["url"]}\n\n'
        
        # ПОКАЗЫВАЕМ ИНФОРМАЦИЮ О ЛИМИТЕ (включая trial)
        if user_plan == 'trial':
            if lang == 'ru':
                text += '─'*50 + '\n'
                text += '🎁 ТЕСТОВЫЙ ПЕРИОД\n'
                text += '📊 Осталось бесплатных запросов: 0\n'
                text += '\n💳 Выберите тариф для продолжения работы!\n'
            else:
                text += '─'*50 + '\n'
                text += '🎁 TRIAL PERIOD\n'
                text += '📊 Free requests remaining: 0\n'
                text += '\n💳 Choose a plan to continue!\n'
        else:
            month = get_current_month()
            month_data = user_data['months'][month]
            remaining = PLANS[user_data['plan']]['limit'] - month_data['used']
            
            text += '─'*50 + '\n'
            text += f'📊 ' + ('Осталось запросов' if lang == 'ru' else 'Requests remaining') + f': {remaining}\n'
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔍 Новый поиск' if lang == 'ru' else '🔍 New search', callback_data='search_start')],
            [InlineKeyboardButton(text='🔙 Назад' if lang == 'ru' else '🔙 Back', callback_data='menu')]
        ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == 'plans')
async def show_plans(callback: types.CallbackQuery):
    """Показывает доступные тарифы"""
    lang = get_user_language(callback.from_user.id)
    
    if lang == 'ru':
        text = '''💎 ВЫБЕРИТЕ ПОДХОДЯЩИЙ ТАРИФ

╔═══════════════════════════════════════════════════╗
║  🎬 LITE - 100₽/месяц                           ║
╚═══════════════════════════════════════════════════╝

✅ Видеолекции от YouTube
✅ 10 запросов в месяц
❌ Нет доступа к полным курсам

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

╔═══════════════════════════════════════════════════╗
║  💎 PRO - 200₽/месяц (ПОПУЛЯРНЫЙ)               ║
╚═══════════════════════════════════════════════════╝

✅ Все видеолекции
✅ Полные курсы из базы
✅ 50 запросов в месяц
✅ Приоритетная поддержка

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

╔═══════════════════════════════════════════════════╗
║  🔥 UNLIMITED - 500₽/месяц (ЛУЧШЕЕ ПРЕДЛОЖЕНИЕ) ║
╚═══════════════════════════════════════════════════╝

✅ Полный доступ ко всему
✅ Неограниченные запросы
✅ Премиум поддержка 24/7
✅ Эксклюзивные материалы

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Выберите тариф и начните обучение! 🚀'''
    else:
        text = '''💎 CHOOSE YOUR PLAN

╔═══════════════════════════════════════════════════╗
║  🎬 LITE - $1.25/month                           ║
╚═══════════════════════════════════════════════════╝

✅ YouTube video lectures
✅ 10 requests per month
❌ No access to full courses

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

╔═══════════════════════════════════════════════════╗
║  💎 PRO - $2.50/month (POPULAR)                  ║
╚═══════════════════════════════════════════════════╝

✅ All video lectures
✅ Full courses from database
✅ 50 requests per month
✅ Priority support

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

╔═══════════════════════════════════════════════════╗
║  🔥 UNLIMITED - $6.25/month (BEST OFFER)        ║
╚═══════════════════════════════════════════════════╝

✅ Full access to everything
✅ Unlimited requests
✅ Premium 24/7 support
✅ Exclusive materials

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Choose a plan and start learning! 🚀'''
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🎬 Lite (100₽)' if lang == 'ru' else '🎬 Lite ($1.25)', callback_data='buy_lite')],
        [InlineKeyboardButton(text='💎 Pro (200₽)' if lang == 'ru' else '💎 Pro ($2.50)', callback_data='buy_pro')],
        [InlineKeyboardButton(text='🔥 Unlimited (500₽)' if lang == 'ru' else '🔥 Unlimited ($6.25)', callback_data='buy_unlimited')],
        [InlineKeyboardButton(text='🔙 Назад' if lang == 'ru' else '🔙 Back', callback_data='menu')]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == 'search_start')
async def search_start(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс поиска курса"""
    lang = get_user_language(callback.from_user.id)
    
    if lang == 'ru':
        text = '🔍 Что вы хотите изучать?\n\nНапишите название курса или темы:'
    else:
        text = '🔍 What would you like to learn?\n\nEnter a course or topic name:'
    
    await callback.message.edit_text(text)
    await state.set_state("waiting_for_search")

@dp.callback_query(F.data == 'menu')
async def back_to_menu(callback: types.CallbackQuery):
    """Возвращает в главное меню"""
    lang = get_user_language(callback.from_user.id)
    user_id = callback.from_user.id
    
    subs = load_subs()
    user_id_str = str(user_id)
    
    if user_id_str not in subs:
        await callback.answer('Ошибка: пользователь не найден', show_alert=True)
        return
    
    user_data = subs[user_id_str]
    user_plan = user_data.get('plan')
    
    if user_plan == 'lite':
        if lang == 'ru':
            text = '🎬 Lite план активен\n\nВидеолекции и ограниченные запросы'
        else:
            text = '🎬 Lite plan active\n\nVideo lectures and limited requests'
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🆙 Обновить' if lang == 'ru' else '🆙 Upgrade', callback_data='plans')],
            [InlineKeyboardButton(text='🔍 Поиск' if lang == 'ru' else '🔍 Search', callback_data='search_start')],
        ])
    else:
        if lang == 'ru':
            text = '✨ Премиум сообщество\n\nПолный доступ к курсам'
        else:
            text = '✨ Premium community\n\nFull access to courses'
        
        recommended_courses = get_recommended_courses(lang, limit=8)
        
        course_buttons = []
        for course in recommended_courses:
            course_buttons.append([InlineKeyboardButton(text=course["name"], callback_data=f'course_{course["id"]}')])
        
        main_buttons = [
            [InlineKeyboardButton(text='🔍 Поиск' if lang == 'ru' else '🔍 Search', callback_data='search_start')],
        ]
        
        kb = InlineKeyboardMarkup(inline_keyboard=course_buttons + main_buttons)
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == 'change_language')
async def change_language(callback: types.CallbackQuery):
    """Изменить язык"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🇷🇺 Русский', callback_data='lang_ru')],
        [InlineKeyboardButton(text='🇬🇧 English', callback_data='lang_en')],
        [InlineKeyboardButton(text='🔙 Назад' if get_user_language(callback.from_user.id) == 'ru' else '🔙 Back', callback_data='menu')]
    ])
    
    text = 'Выберите язык / Choose language:'
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# ═══════════════════════════════════════════════════════════════
# 🚀 ЗАПУСК БОТА
# ═══════════════════════════════════════════════════════════════

async def main():
    """Запуск бота"""
    logger.info('🤖 Bot started successfully!')
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
