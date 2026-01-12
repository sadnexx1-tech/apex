import asyncio
import logging
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from yookassa import Configuration
from dotenv import load_dotenv

load_dotenv()
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher(storage=MemoryStorage())
Configuration.account_id = os.getenv('YOOKASSA_SHOP_ID')
Configuration.secret_key = os.getenv('YOOKASSA_SECRET_KEY')

CHANNEL_ID = '@sadnexx_true'
SUBS_FILE = 'subscriptions.json'

# Фотографии для каждого раздела
PHOTOS = {
    'start': 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=400',
    'menu': 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=400',
    'plans': 'https://images.unsplash.com/photo-1611532736597-de2d4265fba3?w=400',
    'lite': 'https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=400',
    'pro': 'https://images.unsplash.com/photo-1611532736597-de2d4265fba3?w=400',
    'unlim': 'https://images.unsplash.com/photo-1526374965328-7f5ae4e8a27d?w=400',
    'limit': 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400',
    'support': 'https://images.unsplash.com/photo-1516534775068-bb57e39c1a4d?w=400',
    'about': 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=400',
    'search': 'https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=400',
    'success': 'https://images.unsplash.com/photo-1611532736597-de2d4265fba3?w=400',
}

PLANS = {
    'lite': {'title': 'Lite', 'limit': 10, 'price': 5000, 'duration': 30, 'photo': PHOTOS['lite']},
    'pro': {'title': 'Pro', 'limit': 50, 'price': 15000, 'duration': 30, 'photo': PHOTOS['pro']},
    'unlim': {'title': 'Unlimited', 'limit': 999999, 'price': 30000, 'duration': 30, 'photo': PHOTOS['unlim']},
}

COURSES = {
    'smm': 'SMM маркетинг в соцсетях',
    'seo': 'SEO поисковая оптимизация',
    'программирование': 'Программирование',
    'администрирование': 'Администрирование',
    'веб_дизайн': 'Веб дизайн',
    'бизнес': 'Бизнес, маркетинг и менеджмент',
    'форекс': 'Форекс, трейдинг и инвестиции',
    'блокчейн': 'Блокчейн и криптовалюты',
    'психология': 'Психология',
    'фото': 'Фото и видео обработка',
    'дизайн': 'Дизайн и живопись',
    'языки': 'Изучение иностранных языков',
    'кулинария': 'Кулинария',
    'здоровье': 'Здоровье и спорт',
    'музыка': 'Музыка',
    'копирайтинг': 'Копирайтинг',
    'разное': 'Разное',
}

class UserState(StatesGroup):
    waiting_for_request = State()
    waiting_for_language = State()

# Переводы на разные языки
LANG_TEXTS = {
    'ru': {
        'welcome': '🔔 Добро пожаловать в сервис курсов!\n\nПодпишитесь на канал для доступа ко всем планам.\nПосле подписки нажмите "Проверить подписку".',
        'select_lang': '🌍 Выберите язык / Select language:',
        'russian': '🇷🇺 Русский',
        'english': '🇬🇧 English',
        'subscribe': '📢 Подписаться',
        'check_sub': '✅ Проверить подписку',
        'subscription_confirmed': '✅ Подписка подтверждена!\n\nВыберите раздел:',
        'plans': '📦 Подписки',
        'my_limit': '📊 Мой лимит',
        'support': '💬 Поддержка',
        'about': '👥 О нас',
        'language': '🌍 Язык',
        'menu': '🏠 Меню',
        'subscribe_first': '❌ Подпишитесь на канал сначала!',
        'error': '❌ Ошибка: {}',
        'available_plans': '📦 ДОСТУПНЫЕ ПОДПИСКИ:\n\n⭐ Lite: 10 запросов в месяц - 50₽\n\n⭐⭐ Pro: 50 запросов в месяц - 150₽\n\n⭐⭐⭐ Unlimited: Безлимит запросов - 300₽\n\nВыберите подписку для начала работы!',
        'no_subscription': '📊 У вас нет активной подписки.\n\nВыберите подписку в разделе "Подписки"!',
        'your_limit': '📊 ВАШ ЛИМИТ:\n\n📦 План: {}\n📈 Лимит в месяц: {} запросов\n✅ Использовано: {}/{}\n⏳ Осталось: {}\n📅 Период: {}',
        'support_text': '💬 ПОДДЕРЖКА\n\nЕсть вопросы? Свяжитесь с нашей командой:\n\n✉️ Напишите @sadnexx\n⏰ Время ответа: до 24 часов\n\nМы здесь, чтобы помочь!',
        'write_support': '💬 Написать в поддержку',
        'about_text': '👥 О НАС\n\nМы предоставляем доступ к качественным курсам и учебным материалам.\n\n✅ Качественный контент\n✅ Поддержка 24/7\n✅ Гибкие тарифы\n✅ Быстрый поиск курсов\n\nПодпишитесь на @sadnexx_true для обновлений!',
        'buy': '🛒',
        'invoice_sent': '🧾 Счёт отправлен в чат!',
        'success': '✅ УСПЕХ! Подписка активирована!\n\n📦 План: {}\n📈 Лимит: {} запросов в месяц\n⏳ Действует 30 дней\n\nТеперь вы можете искать курсы! Просто напишите название курса или ключевое слово.',
        'search_courses': '🔍 Поиск курсов',
        'enter_query': '🔍 Введите название курса или ключевое слово (например: "программирование", "дизайн", "маркетинг"):\n\nНаберите /cancel чтобы выйти.',
        'cancelled': '❌ Отменено.',
        'limit_exhausted': '⚠️ Лимит исчерпан!\n\nПлан "{}": {} запросов в месяц.',
        'no_found': '❌ Курсов не найдено по запросу: "{}"\n\nПопробуйте другое ключевое слово.',
        'found': '🎓 Найдено {} курс(ов):\n\n',
        'remaining': '\n📊 Осталось запросов: {}',
        'search_again': '🔍 Найти снова',
        'need_subscription': '📦 Вам нужна активная подписка для поиска курсов.\n\nВыберите план:',
        'main_menu': '🏠 ГЛАВНОЕ МЕНЮ\n\nВыберите раздел:',
        'lang_changed': '✅ Язык изменён на Русский!',
    },
    'en': {
        'welcome': '🔔 Welcome to Courses Service!\n\nSubscribe to the channel to access all plans.\nAfter subscribing, click "Check subscription".',
        'select_lang': '🌍 Select language / Выберите язык:',
        'russian': '🇷🇺 Русский',
        'english': '🇬🇧 English',
        'subscribe': '📢 Subscribe',
        'check_sub': '✅ Check subscription',
        'subscription_confirmed': '✅ Subscription confirmed!\n\nSelect a section:',
        'plans': '📦 Plans',
        'my_limit': '📊 My limit',
        'support': '💬 Support',
        'about': '👥 About us',
        'language': '🌍 Language',
        'menu': '🏠 Menu',
        'subscribe_first': '❌ Subscribe to the channel first!',
        'error': '❌ Error: {}',
        'available_plans': '📦 AVAILABLE PLANS:\n\n⭐ Lite: 10 requests/month - $0.50\n\n⭐⭐ Pro: 50 requests/month - $1.50\n\n⭐⭐⭐ Unlimited: Unlimited requests - $3.00\n\nChoose a plan to get started!',
        'no_subscription': '📊 You have no active subscription.\n\nChoose a plan in "Plans" section!',
        'your_limit': '📊 YOUR LIMIT:\n\n📦 Plan: {}\n📈 Monthly limit: {} requests\n✅ Used: {}/{}\n⏳ Remaining: {}\n📅 Period: {}',
        'support_text': '💬 SUPPORT\n\nHave questions? Contact our team:\n\n✉️ Write to @sadnexx\n⏰ Response time: up to 24 hours\n\nWe\'re here to help!',
        'write_support': '💬 Write to support',
        'about_text': '👥 ABOUT US\n\nWe provide access to high-quality courses and learning materials.\n\n✅ Quality content\n✅ 24/7 Support\n✅ Flexible plans\n✅ Fast course search\n\nSubscribe to @sadnexx_true for updates!',
        'buy': '🛒',
        'invoice_sent': '🧾 Invoice sent to chat!',
        'success': '✅ SUCCESS! Subscription activated!\n\n📦 Plan: {}\n📈 Limit: {} requests/month\n⏳ Valid for 30 days\n\nNow you can search for courses! Just type the course name or keyword.',
        'search_courses': '🔍 Search courses',
        'enter_query': '🔍 Enter course name or keyword (e.g., "programming", "design", "marketing"):\n\nType /cancel to exit.',
        'cancelled': '❌ Cancelled.',
        'limit_exhausted': '⚠️ Limit exhausted!\n\nPlan "{}": {} requests per month.',
        'no_found': '❌ No courses found for: "{}"\n\nTry another keyword.',
        'found': '🎓 Found {} course(s):\n\n',
        'remaining': '\n📊 Requests remaining: {}',
        'search_again': '🔍 Search again',
        'need_subscription': '📦 You need an active subscription to search courses.\n\nChoose a plan:',
        'main_menu': '🏠 MAIN MENU\n\nSelect a section:',
        'lang_changed': '✅ Language changed to English!',
    }
}

def load_subs():
    try:
        with open(SUBS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except:
        return {}

def save_subs(subs):
    with open(SUBS_FILE, 'w', encoding='utf-8') as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)

def get_current_month():
    return datetime.now().strftime('%Y-%m')

def get_user_language(user_id):
    subs = load_subs()
    user_id_str = str(user_id)
    return subs.get(user_id_str, {}).get('language', 'ru')

def set_user_language(user_id, language):
    subs = load_subs()
    user_id_str = str(user_id)
    if user_id_str not in subs:
        subs[user_id_str] = {}
    subs[user_id_str]['language'] = language
    save_subs(subs)

def get_text(key, lang='ru', *args):
    text = LANG_TEXTS.get(lang, LANG_TEXTS['ru']).get(key, '')
    if args:
        return text.format(*args)
    return text

def search_course(query):
    """Поиск курса по ключевым словам"""
    query_lower = query.lower()
    found = []
    
    for key, name in COURSES.items():
        if query_lower in key or query_lower in name.lower():
            found.append((key, name))
    
    return found

def increment_usage(user_id):
    """Увеличить счётчик запросов"""
    subs = load_subs()
    user_id_str = str(user_id)
    
    if user_id_str not in subs:
        return False
    
    if not subs[user_id_str].get('plan'):
        return False
    
    month = get_current_month()
    if 'months' not in subs[user_id_str]:
        subs[user_id_str]['months'] = {}
    if month not in subs[user_id_str]['months']:
        subs[user_id_str]['months'][month] = {'used': 0}
    
    plan = subs[user_id_str]['plan']
    limit = PLANS[plan]['limit']
    used = subs[user_id_str]['months'][month]['used']
    
    if used >= limit:
        return False
    
    subs[user_id_str]['months'][month]['used'] += 1
    save_subs(subs)
    return True

@dp.message(Command('start'))
async def start(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    await state.set_state(UserState.waiting_for_language)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🇷🇺 Русский', callback_data='lang_ru')],
        [InlineKeyboardButton(text='🇬🇧 English', callback_data='lang_en')]
    ])
    await msg.answer_photo(
        photo=PHOTOS['start'],
        caption='🌍 Choose language / Выберите язык:',
        reply_markup=kb
    )

@dp.callback_query(lambda c: c.data.startswith('lang_'))
async def set_language(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = callback.data.split('_')[1]
    set_user_language(user_id, lang)
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('subscribe', lang), url=f'https://t.me/{CHANNEL_ID[1:]}')],
        [InlineKeyboardButton(text=get_text('check_sub', lang), callback_data='check_sub')]
    ])
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=PHOTOS['start'],
            caption=get_text('welcome', lang)
        ),
        reply_markup=kb
    )

@dp.callback_query(F.data == 'check_sub')
async def check_sub(callback: types.CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    try:
        member = await bot.get_chat_member(CHANNEL_ID, callback.from_user.id)
        if member.status in ['member', 'administrator', 'creator']:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_text('plans', lang), callback_data='plans')],
                [InlineKeyboardButton(text=get_text('my_limit', lang), callback_data='my_limit')],
                [InlineKeyboardButton(text=get_text('support', lang), callback_data='support')],
                [InlineKeyboardButton(text=get_text('about', lang), callback_data='about')],
                [InlineKeyboardButton(text=get_text('language', lang), callback_data='change_language')]
            ])
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=PHOTOS['menu'],
                    caption=get_text('subscription_confirmed', lang)
                ),
                reply_markup=kb
            )
        else:
            await callback.answer(get_text('subscribe_first', lang), show_alert=True)
    except Exception as e:
        await callback.answer(get_text('error', lang, str(e)), show_alert=True)

@dp.callback_query(F.data == 'change_language')
async def change_language(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🇷🇺 Русский', callback_data='set_lang_ru')],
        [InlineKeyboardButton(text='🇬🇧 English', callback_data='set_lang_en')]
    ])
    await callback.message.answer('🌍 Choose language / Выберите язык:', reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith('set_lang_'))
async def set_new_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = callback.data.split('_')[2]
    set_user_language(user_id, lang)
    await callback.answer(get_text('lang_changed', lang), show_alert=True)

@dp.callback_query(F.data == 'plans')
async def plans(callback: types.CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{get_text('buy', lang)} {PLANS['lite']['title']} - {PLANS['lite']['price']/100}₽", callback_data='buy_lite')],
        [InlineKeyboardButton(text=f"{get_text('buy', lang)} {PLANS['pro']['title']} - {PLANS['pro']['price']/100}₽", callback_data='buy_pro')],
        [InlineKeyboardButton(text=f"{get_text('buy', lang)} {PLANS['unlim']['title']} - {PLANS['unlim']['price']/100}₽", callback_data='buy_unlim')],
        [InlineKeyboardButton(text=get_text('menu', lang), callback_data='menu')]
    ])
    await callback.message.edit_media(
        media=InputMediaPhoto(media=PHOTOS['plans'], caption=get_text('available_plans', lang)),
        reply_markup=kb
    )

@dp.callback_query(F.data == 'my_limit')
async def my_limit(callback: types.CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    user_id = str(callback.from_user.id)
    subs = load_subs()
    user_data = subs.get(user_id, {})
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('menu', lang), callback_data='menu')]
    ])
    
    if not user_data.get('plan'):
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=PHOTOS['limit'],
                caption=get_text('no_subscription', lang)
            ),
            reply_markup=kb
        )
        return
    
    plan = user_data['plan']
    month = get_current_month()
    month_data = user_data.get('months', {}).get(month, {'used': 0})
    used = month_data['used']
    limit = PLANS[plan]['limit']
    remaining = limit - used
    
    text = get_text('your_limit', lang, PLANS[plan]['title'], limit, used, limit, remaining, month)
    
    await callback.message.edit_media(
        media=InputMediaPhoto(media=PHOTOS['limit'], caption=text),
        reply_markup=kb
    )

@dp.callback_query(F.data == 'support')
async def support(callback: types.CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('write_support', lang), url='https://t.me/sadnexx')],
        [InlineKeyboardButton(text=get_text('menu', lang), callback_data='menu')]
    ])
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=PHOTOS['support'],
            caption=get_text('support_text', lang)
        ),
        reply_markup=kb
    )

@dp.callback_query(F.data == 'about')
async def about(callback: types.CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('menu', lang), callback_data='menu')]
    ])
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=PHOTOS['about'],
            caption=get_text('about_text', lang)
        ),
        reply_markup=kb
    )

@dp.callback_query(lambda c: c.data.startswith('buy_'))
async def buy_plan(callback: types.CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    plan_key = callback.data.split('_')[1]
    plan = PLANS[plan_key]
    await bot.send_invoice(
        callback.from_user.id,
        title=f"Subscription {plan['title']}",
        description=f"{plan['limit']} requests per month",
        payload=plan_key,
        provider_token='',
        currency='RUB',
        prices=[LabeledPrice(label=plan['title'], amount=plan['price'])]
    )
    await callback.answer(get_text('invoice_sent', lang), show_alert=False)

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@dp.message(F.successful_payment)
async def deliver_plan(msg: types.Message):
    lang = get_user_language(msg.from_user.id)
    plan_key = msg.successful_payment.invoice_payload
    plan = PLANS[plan_key]
    user_id = str(msg.from_user.id)
    subs = load_subs()
    
    if user_id not in subs:
        subs[user_id] = {}
    
    month = get_current_month()
    subs[user_id]['plan'] = plan_key
    subs[user_id]['purchase_date'] = datetime.now().isoformat()
    if 'months' not in subs[user_id]:
        subs[user_id]['months'] = {}
    if month not in subs[user_id]['months']:
        subs[user_id]['months'][month] = {'used': 0}
    
    save_subs(subs)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('my_limit', lang), callback_data='my_limit')],
        [InlineKeyboardButton(text=get_text('search_courses', lang), callback_data='search_start')],
        [InlineKeyboardButton(text=get_text('menu', lang), callback_data='menu')]
    ])
    await msg.answer_photo(
        photo=PHOTOS['success'],
        caption=get_text('success', lang, plan['title'], plan['limit']),
        reply_markup=kb
    )

@dp.callback_query(F.data == 'search_start')
async def search_start(callback: types.CallbackQuery, state: FSMContext):
    lang = get_user_language(callback.from_user.id)
    await state.set_state(UserState.waiting_for_request)
    await callback.message.answer_photo(
        photo=PHOTOS['search'],
        caption=get_text('enter_query', lang)
    )

@dp.message(F.text, UserState.waiting_for_request)
async def handle_search(msg: types.Message, state: FSMContext):
    lang = get_user_language(msg.from_user.id)
    user_id = msg.from_user.id
    
    if msg.text == '/cancel':
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('menu', lang), callback_data='menu')]
        ])
        await msg.answer(get_text('cancelled', lang), reply_markup=kb)
        return
    
    if not increment_usage(user_id):
        subs = load_subs()
        user_data = subs.get(str(user_id), {})
        if not user_data.get('plan'):
            await msg.answer(get_text('subscribe_first', lang))
        else:
            plan = user_data['plan']
            await msg.answer(get_text('limit_exhausted', lang, PLANS[plan]['title'], PLANS[plan]['limit']))
        await state.clear()
        return
    
    query = msg.text
    results = search_course(query)
    
    if not results:
        await msg.answer(get_text('no_found', lang, query))
        return
    
    text = get_text('found', lang, len(results))
    for key, name in results:
        text += f'✅ {name}\n'
    
    subs = load_subs()
    user_data = subs.get(str(user_id), {})
    month = get_current_month()
    month_data = user_data['months'][month]
    remaining = PLANS[user_data['plan']]['limit'] - month_data['used']
    
    text += get_text('remaining', lang, remaining)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('search_again', lang), callback_data='search_start')],
        [InlineKeyboardButton(text=get_text('my_limit', lang), callback_data='my_limit')],
        [InlineKeyboardButton(text=get_text('menu', lang), callback_data='menu')]
    ])
    
    await msg.answer(text, reply_markup=kb)
    await state.clear()

@dp.message(F.text)
async def handle_text(msg: types.Message):
    lang = get_user_language(msg.from_user.id)
    user_id = str(msg.from_user.id)
    subs = load_subs()
    user_data = subs.get(user_id, {})
    
    if not user_data.get('plan'):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('subscribe', lang), url=f'https://t.me/{CHANNEL_ID[1:]}')],
            [InlineKeyboardButton(text=get_text('check_sub', lang), callback_data='check_sub')]
        ])
        await msg.answer_photo(
            photo=PHOTOS['start'],
            caption=get_text('need_subscription', lang),
            reply_markup=kb
        )
        return
    
    if increment_usage(msg.from_user.id):
        results = search_course(msg.text)
        if results:
            text = get_text('found', lang, len(results))
            for key, name in results:
                text += f'✅ {name}\n'
            
            subs = load_subs()
            user_data = subs.get(user_id, {})
            month = get_current_month()
            month_data = user_data['months'][month]
            remaining = PLANS[user_data['plan']]['limit'] - month_data['used']
            
            text += get_text('remaining', lang, remaining)
            await msg.answer(text)
        else:
            await msg.answer(get_text('no_found', lang, msg.text))
    else:
        plan = user_data['plan']
        await msg.answer(get_text('limit_exhausted', lang, PLANS[plan]['title'], PLANS[plan]['limit']))

@dp.callback_query(F.data == 'menu')
async def menu(callback: types.CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('plans', lang), callback_data='plans')],
        [InlineKeyboardButton(text=get_text('my_limit', lang), callback_data='my_limit')],
        [InlineKeyboardButton(text=get_text('support', lang), callback_data='support')],
        [InlineKeyboardButton(text=get_text('about', lang), callback_data='about')],
        [InlineKeyboardButton(text=get_text('language', lang), callback_data='change_language')]
    ])
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=PHOTOS['menu'],
            caption=get_text('main_menu', lang)
        ),
        reply_markup=kb
    )

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info('🤖 Bot started successfully!')
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
