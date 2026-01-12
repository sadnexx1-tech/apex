import asyncio
import logging
import json
import os
import datetime
from decimal import Decimal
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))  # Для админ панели

# YooKassa конфигурация
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
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
        'price_usd': 125,  # $1.25
        'description': 'Видеолекции + 10 запросов/месяц'
    },
    'pro': {
        'title': 'Pro',
        'limit': 50,
        'price': 20000,  # 200 рублей
        'price_usd': 250,  # $2.50
        'description': 'Полный доступ + 50 запросов/месяц'
    },
    'unlimited': {
        'title': 'Unlimited',
        'limit': 9999,
        'price': 50000,  # 500 рублей
        'price_usd': 625,  # $6.25
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
PAYMENTS_FILE = 'payments.json'

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

def load_payments():
    """Загружает данные платежей"""
    if os.path.exists(PAYMENTS_FILE):
        with open(PAYMENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_payments(payments):
    """Сохраняет данные платежей"""
    with open(PAYMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(payments, f, ensure_ascii=False, indent=2)

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
    
    if user_id_str not in subs:
        return True
    
    user_data = subs[user_id_str]
    
    if not user_data.get('plan'):
        return True
    
    return False

# ═══════════════════════════════════════════════════════════════
# 📊 ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ЛИМИТАМИ
# ═══════════════════════════════════════════════════════════════

def increment_usage(user_id):
    """Проверяет лимит и увеличивает счетчик использования"""
    subs = load_subs()
    user_id_str = str(user_id)
    
    if user_id_str not in subs:
        return False
    
    user_data = subs[user_id_str]
    plan = user_data.get('plan')
    
    if plan == 'trial':
        if not user_data.get('trial_used', False):
            user_data['trial_used'] = True
            save_subs(subs)
            return True
        else:
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
    
    month_data['used'] += 1
    save_subs(subs)
    
    return True

# ═══════════════════════════════════════════════════════════════
# 💳 ФУНКЦИИ ДЛЯ ПЛАТЕЖЕЙ YOOKASSA
# ═══════════════════════════════════════════════════════════════

def create_payment(plan, user_id, user_email='customer@example.com'):
    """Создает платеж через YooKassa"""
    try:
        price = PLANS[plan]['price']
        
        payment = Payment.create({
            "amount": {
                "value": price / 100,
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f"https://t.me/{BOT_TOKEN.split(':')[0]}"
            },
            "capture": True,
            "description": f"Подписка {PLANS[plan]['title']} на CourseBot",
            "metadata": {
                "user_id": user_id,
                "plan": plan
            }
        }, user_email)
        
        return payment
    except Exception as e:
        logger.error(f"Ошибка создания платежа: {str(e)}")
        return None

def save_payment_record(payment_id, user_id, plan, status):
    """Сохраняет запись о платеже"""
    payments = load_payments()
    payments[payment_id] = {
        'user_id': user_id,
        'plan': plan,
        'status': status,
        'created_at': datetime.datetime.now().isoformat()
    }
    save_payments(payments)

def check_payment_status(payment_id):
    """Проверяет статус платежа"""
    try:
        payment = Payment.find_one(payment_id)
        return payment.status
    except Exception as e:
        logger.error(f"Ошибка проверки платежа: {str(e)}")
        return None

def activate_subscription(user_id, plan):
    """Активирует подписку пользователю"""
    subs = load_subs()
    user_id_str = str(user_id)
    
    if user_id_str not in subs:
        subs[user_id_str] = {
            'language': 'ru',
            'plan': plan,
            'months': get_default_months(),
            'premium_end': None,
            'join_date': datetime.datetime.now().isoformat()
        }
    else:
        subs[user_id_str]['plan'] = plan
        subs[user_id_str]['months'] = get_default_months()
    
    save_subs(subs)
    logger.info(f"Активирована подписка {plan} для пользователя {user_id}")

# ═══════════════════════════════════════════════════════════════
# 🎓 ФУНКЦИИ ДЛЯ КУРСОВ
# ═══════════════════════════════════════════════════════════════

def get_recommended_courses(lang='ru', limit=8):
    """Генерирует список рекомендованных курсов"""
    
    courses_ru = [
        {'id': 'python', 'name': '🎓 Python для начинающих'},
        {'id': 'django', 'name': '💻 Веб-разработка с Django'},
        {'id': 'datascience', 'name': '📊 Data Science и анализ данных'},
        {'id': 'figma', 'name': '🎨 Дизайн и Figma'},
        {'id': 'react', 'name': '📱 Мобильная разработка на React Native'},
        {'id': 'devops', 'name': '🚀 DevOps и Docker'},
        {'id': 'cybersecurity', 'name': '🔐 Cybersecurity основы'},
        {'id': 'marketing', 'name': '📈 Маркетинг и аналитика'},
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
# 🎯 STATES ДЛЯ FSM
# ═══════════════════════════════════════════════════════════════

class SearchStates(StatesGroup):
    waiting_for_search = State()

# ═══════════════════════════════════════════════════════════════
# 🤖 КОМАНДЫ И ОБРАБОТЧИКИ
# ═══════════════════════════════════════════════════════════════

@dp.message(Command('start'))
async def start_command(message: types.Message):
    """Команда /start"""
    user_id = message.from_user.id
    subs = load_subs()
    user_id_str = str(user_id)
    
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
        
        await message.answer(text, reply_markup=kb)

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
            
            is_first_time = give_trial_access(callback.from_user.id)
            
            subs = load_subs()
            user_id_str = str(callback.from_user.id)
            
            if is_first_time:
                if user_id_str not in subs:
                    subs[user_id_str] = {
                        'plan': 'trial',
                        'trial_used': False,
                        'months': get_default_months(),
                        'premium_end': None,
                        'join_date': datetime.datetime.now().isoformat()
                    }
                else:
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
            
            else:
                user_data = subs.get(user_id_str, {})
                user_plan = user_data.get('plan')
                
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
                    
                    recommended_courses = get_recommended_courses(lang, limit=8)
                    for i, course in enumerate(recommended_courses, 1):
                        success_text += f'{i}️⃣ {course["name"]}\n'
                    
                    success_text += '\n🎯 Начните обучение прямо сейчас!\n'
                    success_text += '💬 Поддержка доступна в любой момент\n'
                    
                    course_buttons = []
                    for course in recommended_courses:
                        course_buttons.append([InlineKeyboardButton(text=course["name"], callback_data=f'course_{course["id"]}')])
                    
                    main_buttons = [
                        [InlineKeyboardButton(text='📦 Подписки' if lang == 'ru' else '📦 Plans', callback_data='plans')],
                        [InlineKeyboardButton(text='📊 Мой лимит' if lang == 'ru' else '📊 My limit', callback_data='my_limit')],
                        [InlineKeyboardButton(text='🔍 Поиск курсов' if lang == 'ru' else '🔍 Search courses', callback_data='search_start')],
                        [InlineKeyboardButton(text='💬 Поддержка' if lang == 'ru' else '💬 Support', callback_data='support')],
                        [InlineKeyboardButton(text='👥 О нас' if lang == 'ru' else '👥 About', callback_data='about')],
                        [InlineKeyboardButton(text='🌍 Язык' if lang == 'ru' else '🌍 Language', callback_data='change_language')]
                    ]
                    
                    kb = InlineKeyboardMarkup(inline_keyboard=course_buttons + main_buttons)
            
            await callback.message.edit_text(success_text, reply_markup=kb)
        else:
            await callback.answer(get_text('subscribe_first', lang), show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {str(e)}")
        await callback.answer(get_text('error', lang, str(e)), show_alert=True)

@dp.callback_query(lambda c: c.data.startswith('course_'))
async def handle_course_click(callback: types.CallbackQuery):
    """Обработчик нажатия на рекомендованный курс"""
    lang = get_user_language(callback.from_user.id)
    user_id = callback.from_user.id
    
    course_id = callback.data.replace('course_', '')
    
    if not increment_usage(user_id):
        subs = load_subs()
        user_data = subs.get(str(user_id), {})
        plan = user_data.get('plan')
        
        if not plan:
            await callback.answer(get_text('subscribe_first', lang), show_alert=True)
        elif plan == 'trial':
            if lang == 'ru':
                msg = '🎁 Ваш тестовый запрос уже использован!\n\n💳 Пожалуйста, выберите подходящий тариф для продолжения.'
            else:
                msg = '🎁 Your trial request has been used!\n\n💳 Please choose a subscription plan to continue.'
            await callback.answer(msg, show_alert=True)
        else:
            await callback.answer(get_text('limit_exhausted', lang, PLANS[plan]['title'], PLANS[plan]['limit']), show_alert=True)
        return
    
    subs = load_subs()
    user_data = subs.get(str(user_id), {})
    user_plan = user_data.get('plan')
    
    results = search_course(course_id)
    
    if user_plan == 'lite':
        if lang == 'ru':
            text = f'🎬 ВИДЕОЛЕКЦИИ ПО ТЕМЕ: "{course_id.upper()}"\n\n'
        else:
            text = f'🎬 VIDEO LECTURES ON: "{course_id.upper()}"\n\n'
        
        if results:
            if lang == 'ru':
                text += '📚 СВЯЗАННЫЕ КУРСЫ (доступны на Pro/Unlimited):\n\n'
            else:
                text += '📚 RELATED COURSES (available on Pro/Unlimited):\n\n'
            for i, (key, name) in enumerate(results, 1):
                text += f'{i}️⃣ {name}\n'
            text += '\n'
        
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

@dp.callback_query(F.data.startswith('buy_'))
async def process_payment(callback: types.CallbackQuery):
    """Обработчик платежа"""
    lang = get_user_language(callback.from_user.id)
    user_id = callback.from_user.id
    plan = callback.data.replace('buy_', '')
    
    if plan not in PLANS:
        await callback.answer('Неверный тариф', show_alert=True)
        return
    
    try:
        payment = create_payment(plan, user_id)
        
        if payment and hasattr(payment, 'confirmation') and hasattr(payment.confirmation, 'confirmation_url'):
            save_payment_record(payment.id, user_id, plan, 'pending')
            
            if lang == 'ru':
                text = f'''💳 ОПЛАТА ПОДПИСКИ {PLANS[plan]['title'].upper()}

╔═════════════════════════════════════════╗
║  Сумма: {PLANS[plan]['price'] / 100}₽ ({PLANS[plan]['price_usd'] / 100}$)
║  Период: 1 месяц
╚═════════════════════════════════════════╝

Нажмите кнопку ниже для оплаты через YooKassa.

⏱️ Ссылка действительна 15 минут.
🔒 Платеж защищен и безопасен.

После успешной оплаты вам автоматически активируется подписка!
'''
            else:
                text = f'''💳 SUBSCRIPTION PAYMENT {PLANS[plan]['title'].upper()}

╔═════════════════════════════════════════╗
║  Amount: ${PLANS[plan]['price_usd'] / 100} (₽{PLANS[plan]['price'] / 100})
║  Period: 1 month
╚═════════════════════════════════════════╝

Click the button below to pay with YooKassa.

⏱️ Link valid for 15 minutes.
🔒 Payment is secure and protected.

After successful payment, your subscription will be activated automatically!
'''
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='💳 Оплатить' if lang == 'ru' else '💳 Pay', url=payment.confirmation.confirmation_url)],
                [InlineKeyboardButton(text='🔙 Назад' if lang == 'ru' else '🔙 Back', callback_data='plans')]
            ])
            
            await callback.message.edit_text(text, reply_markup=kb)
            logger.info(f"Платеж создан: {payment.id} для пользователя {user_id}, тариф {plan}")
        else:
            if lang == 'ru':
                error_text = '❌ Ошибка при создании платежа. Проверьте ключи YooKassa в файле .env'
            else:
                error_text = '❌ Error creating payment. Check your YooKassa keys in .env file'
            await callback.answer(error_text, show_alert=True)
            logger.error(f"Ошибка создания платежа для {user_id}")
    
    except Exception as e:
        logger.error(f"Ошибка обработки платежа: {str(e)}")
        await callback.answer(get_text('error', lang, str(e)), show_alert=True)

@dp.callback_query(F.data == 'search_start')
async def search_start(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс поиска курса"""
    lang = get_user_language(callback.from_user.id)
    
    if lang == 'ru':
        text = '🔍 Что вы хотите изучать?\n\nНапишите название курса или темы (python, django, react, etc):'
    else:
        text = '🔍 What would you like to learn?\n\nEnter a course or topic name (python, django, react, etc):'
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔙 Назад' if lang == 'ru' else '🔙 Back', callback_data='menu')]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(SearchStates.waiting_for_search)

@dp.message(StateFilter(SearchStates.waiting_for_search))
async def handle_search_input(message: types.Message, state: FSMContext):
    """Обрабатывает текстовый ввод поиска"""
    lang = get_user_language(message.from_user.id)
    user_id = message.from_user.id
    query = message.text.lower()
    
    results = search_course(query)
    
    if lang == 'ru':
        text = f'🔍 РЕЗУЛЬТАТЫ ПОИСКА: "{query.upper()}"\n\n'
    else:
        text = f'🔍 SEARCH RESULTS: "{query.upper()}"\n\n'
    
    if results:
        if lang == 'ru':
            text += '📚 НАЙДЕННЫЕ КУРСЫ:\n\n'
        else:
            text += '📚 FOUND COURSES:\n\n'
        for i, (key, name) in enumerate(results, 1):
            text += f'{i}️⃣ {name}\n'
    else:
        if lang == 'ru':
            text += '❌ Курсы по этому запросу не найдены.\n'
            text += '💡 Попробуйте: python, django, react, devops, figma, datascience\n'
        else:
            text += '❌ No courses found for this query.\n'
            text += '💡 Try: python, django, react, devops, figma, datascience\n'
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔙 Назад' if lang == 'ru' else '🔙 Back', callback_data='menu')]
    ])
    
    await message.answer(text, reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data == 'my_limit')
async def show_limit(callback: types.CallbackQuery):
    """Показывает лимит пользователя"""
    lang = get_user_language(callback.from_user.id)
    user_id = callback.from_user.id
    
    subs = load_subs()
    user_data = subs.get(str(user_id), {})
    plan = user_data.get('plan')
    
    if not plan:
        if lang == 'ru':
            text = '❌ У вас нет активной подписки'
        else:
            text = '❌ You don\'t have an active subscription'
    else:
        month = get_current_month()
        month_data = user_data.get('months', {}).get(month, {'used': 0})
        
        if plan == 'trial':
            if user_data.get('trial_used'):
                if lang == 'ru':
                    remaining = 0
                else:
                    remaining = 0
            else:
                if lang == 'ru':
                    remaining = 1
                else:
                    remaining = 1
            
            if lang == 'ru':
                text = f'''📊 ИНФОРМАЦИЯ О ЛИМИТАХ

╔═════════════════════════════════════════╗
║  ТЕСТОВЫЙ ПЕРИОД (TRIAL)                ║
╚═════════════════════════════════════════╝

✅ Тариф: ПРОБНЫЙ ПЕРИОД
📅 Месяц: {datetime.datetime.now().strftime('%B')}
🎯 Использовано: {month_data['used']} запрос(а)
📊 Осталось: {remaining} бесплатн(ый) запрос(ов)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 После использования пробного периода выберите платный тариф!
🚀 Всем платежам - гарантия качества и безопасности!
'''
            else:
                text = f'''📊 LIMIT INFORMATION

╔═════════════════════════════════════════╗
║  TRIAL PERIOD                           ║
╚═════════════════════════════════════════╝

✅ Plan: TRIAL PERIOD
📅 Month: {datetime.datetime.now().strftime('%B')}
🎯 Used: {month_data['used']} request(s)
📊 Remaining: {remaining} free request(s)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 After using the trial, choose a paid plan!
🚀 All payments guaranteed safe and secure!
'''
        else:
            limit = PLANS[plan]['limit']
            remaining = max(0, limit - month_data['used'])
            
            if lang == 'ru':
                text = f'''📊 ИНФОРМАЦИЯ О ЛИМИТАХ

╔═════════════════════════════════════════╗
║  ВАША ПОДПИСКА: {PLANS[plan]['title'].upper()}
╚═════════════════════════════════════════╝

✅ Тариф: {PLANS[plan]['title']}
📅 Месяц: {datetime.datetime.now().strftime('%B')}
💰 Цена: {PLANS[plan]['price'] / 100}₽/месяц
🎯 Использовано: {month_data['used']}/{limit} запросов
📊 Осталось: {remaining} запросов

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ Лимит обновляется первого числа каждого месяца!
🎁 Хотите больше запросов? Обновитесь на другой тариф!
'''
            else:
                text = f'''📊 LIMIT INFORMATION

╔═════════════════════════════════════════╗
║  YOUR SUBSCRIPTION: {PLANS[plan]['title'].upper()}
╚═════════════════════════════════════════╝

✅ Plan: {PLANS[plan]['title']}
📅 Month: {datetime.datetime.now().strftime('%B')}
💰 Price: ${PLANS[plan]['price_usd'] / 100}/month
🎯 Used: {month_data['used']}/{limit} requests
📊 Remaining: {remaining} requests

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ Limit resets on the first day of each month!
🎁 Want more requests? Upgrade to another plan!
'''
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📦 Другие тарифы' if lang == 'ru' else '📦 Other plans', callback_data='plans')],
        [InlineKeyboardButton(text='🔙 Назад' if lang == 'ru' else '🔙 Back', callback_data='menu')]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == 'support')
async def show_support(callback: types.CallbackQuery):
    """Показывает информацию о поддержке"""
    lang = get_user_language(callback.from_user.id)
    
    if lang == 'ru':
        text = '''💬 ПОДДЕРЖКА И ПОМОЩЬ

╔═════════════════════════════════════════╗
║  МЫ ВСЕГДА РЯДОМ!                       ║
╚═════════════════════════════════════════╝

📧 Email: support@coursebot.ru
💬 Telegram: @coursebot_support
📱 WhatsApp: +7 (999) 123-45-67

⏱️ Время ответа: обычно в течение 1 часа
🌍 Поддержка: РУ и ENG
🔧 Решение проблем: в течение 24 часов

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❓ ЧАСТЫЕ ВОПРОСЫ:

Q: Как вернуть деньги?
A: Полная гарантия 30 дней!

Q: Когда обновляется лимит?
A: Первого числа каждого месяца!

Q: Можно ли обновить тариф?
A: Да, в любой момент!

Q: Есть ли скидки?
A: Да! Спросите в поддержке о промокодах!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Спасибо, что выбрали CourseBot! 🙏
'''
    else:
        text = '''💬 SUPPORT AND HELP

╔═════════════════════════════════════════╗
║  WE'RE ALWAYS HERE!                     ║
╚═════════════════════════════════════════╝

📧 Email: support@coursebot.ru
💬 Telegram: @coursebot_support
📱 WhatsApp: +1 (999) 123-45-67

⏱️ Response time: usually within 1 hour
🌍 Support: RU and ENG
🔧 Problem solving: within 24 hours

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❓ FAQ:

Q: How to get a refund?
A: Full 30-day guarantee!

Q: When is the limit updated?
A: On the first day of each month!

Q: Can I upgrade my plan?
A: Yes, anytime!

Q: Are there any discounts?
A: Yes! Ask support about promo codes!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Thank you for choosing CourseBot! 🙏
'''
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔙 Назад' if lang == 'ru' else '🔙 Back', callback_data='menu')]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == 'about')
async def show_about(callback: types.CallbackQuery):
    """Показывает информацию о сервисе"""
    lang = get_user_language(callback.from_user.id)
    
    if lang == 'ru':
        text = '''👥 О НАС

╔═════════════════════════════════════════╗
║  CourseBot Premium - Образовательный   ║
║  сервис нового поколения!              ║
╚═════════════════════════════════════════╝

🎯 МИССИЯ:
Сделать качественное образование доступным для всех!

✨ ЧТО МЫ ПРЕДЛАГАЕМ:

🎓 Курсы от экспертов индустрии
💻 Полное сопровождение в обучении
🚀 Практические навыки с первого дня
📚 Видеолекции и интерактивные материалы
🏆 Сертификаты после прохождения

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 СТАТИСТИКА:

👥 50,000+ активных учеников
🌍 100+ стран в мире
⭐ 4.9/5.0 рейтинг
📖 1,000+ часов контента

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤝 НАША КОМАНДА:

👨‍💼 Основатели: опытные разработчики и педагоги
💪 Сообщество: учеников помогают друг другу
🎯 Цель: ваш успех в IT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌐 КОНТАКТЫ:

🔗 Сайт: www.coursebot.ru
📱 Telegram: @coursebot
🐙 GitHub: github.com/coursebot

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Присоединяйтесь к нашему сообществу! 🚀
'''
    else:
        text = '''👥 ABOUT US

╔═════════════════════════════════════════╗
║  CourseBot Premium - Next-Generation   ║
║  Educational Platform!                 ║
╚═════════════════════════════════════════╝

🎯 MISSION:
Make quality education accessible to everyone!

✨ WHAT WE OFFER:

🎓 Courses from industry experts
💻 Complete learning support
🚀 Practical skills from day one
📚 Video lectures and interactive materials
🏆 Certificates upon completion

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 STATISTICS:

👥 50,000+ active students
🌍 100+ countries worldwide
⭐ 4.9/5.0 rating
📖 1,000+ hours of content

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤝 OUR TEAM:

👨‍💼 Founders: experienced developers and educators
💪 Community: students help each other
🎯 Goal: your success in IT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌐 CONTACTS:

🔗 Website: www.coursebot.ru
📱 Telegram: @coursebot
🐙 GitHub: github.com/coursebot

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Join our community! 🚀
'''
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔙 Назад' if lang == 'ru' else '🔙 Back', callback_data='menu')]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

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
    logger.info('🤖 CourseBot Premium запущен успешно!')
    logger.info(f'Версия: 2.0 - PRO Edition with YooKassa Integration')
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
