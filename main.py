import asyncio
import logging
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.storage.memory import MemoryStorage
from yookassa import Configuration
from dotenv import load_dotenv

load_dotenv()
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher(storage=MemoryStorage())
Configuration.account_id = os.getenv('YOOKASSA_SHOP_ID')
Configuration.secret_key = os.getenv('YOOKASSA_SECRET_KEY')

CHANNEL_ID = '@sadnexx_true'
SUBS_FILE = 'subscriptions.json'

courses = {
    'seo': {'title': 'SEO продвижение сайтов', 'desc': 'Полный курс по SEO оптимизации', 'price': 25000, 'duration': 180, 'photo': 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=400', 'access': 'https://t.me/+seo_link'},
    'smm': {'title': 'SMM продвижение', 'desc': 'SMM от А до Я для соцсетей', 'price': 20000, 'duration': 150, 'photo': 'https://images.unsplash.com/photo-1611532736597-de2d4265fba3?w=400', 'access': 'https://t.me/+smm_link'},
    'context': {'title': 'Контекстная реклама', 'desc': 'Яндекс.Директ + Google Ads', 'price': 22000, 'duration': 120, 'photo': 'https://images.unsplash.com/photo-1460925895917-adf4e565e6b1?w=400', 'access': 'https://t.me/+context_link'},
    'target': {'title': 'Таргетированная реклама', 'desc': 'VK, Facebook, Telegram Ads', 'price': 18000, 'duration': 90, 'photo': 'https://images.unsplash.com/photo-1533478611592-007d2c9ac1d9?w=400', 'access': 'https://t.me/+target_link'},
    'copy': {'title': 'Копирайтинг', 'desc': 'Тексты которые продают', 'price': 15000, 'duration': 60, 'photo': 'https://images.unsplash.com/photo-1455391458394-eab60318c891?w=400', 'access': 'https://t.me/+copy_link'},
    'design': {'title': 'Дизайн', 'desc': 'Figma + Photoshop для профессионалов', 'price': 28000, 'duration': 180, 'photo': 'https://images.unsplash.com/photo-1561070791-2526d30994b5?w=400', 'access': 'https://t.me/+design_link'},
    'test': {'title': 'Тестирование ПО', 'desc': 'QA от новичка до middle разработчика', 'price': 19000, 'duration': 120, 'photo': 'https://images.unsplash.com/photo-1516534775068-bb57e39c1a4d?w=400', 'access': 'https://t.me/+test_link'},
    'anal': {'title': 'Аналитика', 'desc': 'Яндекс.Метрика + GA4 полный курс', 'price': 21000, 'duration': 150, 'photo': 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400', 'access': 'https://t.me/+anal_link'},
    'pm': {'title': 'Менеджмент проектов', 'desc': 'Agile Scrum и PM инструменты', 'price': 24000, 'duration': 180, 'photo': 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=400', 'access': 'https://t.me/+pm_link'},
    'py': {'title': 'Курс Python', 'desc': 'С нуля до фриланса за 3 месяца', 'price': 30000, 'duration': 365, 'photo': 'https://images.unsplash.com/photo-1526374965328-7f5ae4e8a27d?w=400', 'access': 'https://t.me/+py_link'},
    'js': {'title': 'Курс JavaScript', 'desc': 'Frontend разработка и React', 'price': 32000, 'duration': 365, 'photo': 'https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=400', 'access': 'https://t.me/+js_link'},
    'freelance': {'title': 'Фриланс', 'desc': 'Как зарабатывать на Upwork Kwork', 'price': 12000, 'duration': 90, 'photo': 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=400', 'access': 'https://t.me/+freelance_link'},
    'tester': {'title': 'Тестировщик ПО', 'desc': 'Автотесты и ручное тестирование', 'price': 17000, 'duration': 120, 'photo': 'https://images.unsplash.com/photo-1516534775068-bb57e39c1a4d?w=400', 'access': 'https://t.me/+tester_link'},
}

def load_subs():
    try:
        with open(SUBS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except:
        return {}

def save_subs(subs):
    with open(SUBS_FILE, 'w') as f:
        json.dump(subs, f)

@dp.message(Command('start'))
async def start(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📢 Подписаться', url=f'https://t.me/{CHANNEL_ID[1:]}')],
        [InlineKeyboardButton(text='✅ Проверить подписку', callback_data='check_sub')]
    ])
    await msg.answer_photo(
        photo='https://images.unsplash.com/photo-1552664730-d307ca884978?w=400',
        caption='🔔 Добро пожаловать в школу курсов!\n\nПодпишитесь на канал для доступа ко всем курсам.\nПосле подписки нажмите "Проверить подписку".',
        reply_markup=kb
    )

@dp.callback_query(F.data == 'check_sub')
async def check_sub(callback: types.CallbackQuery):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, callback.from_user.id)
        if member.status in ['member', 'administrator', 'creator']:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='👥 О нас', callback_data='about')],
                [InlineKeyboardButton(text='📚 Каталог', callback_data='catalog')],
                [InlineKeyboardButton(text='🔥 Акции', callback_data='promo')],
                [InlineKeyboardButton(text='💰 Тарифы', callback_data='prices')],
                [InlineKeyboardButton(text='📋 Мои подписки', callback_data='my_subs')]
            ])
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media='https://images.unsplash.com/photo-1552664730-d307ca884978?w=400',
                    caption='✅ Подписка подтверждена!\n\nВыберите раздел:'
                ),
                reply_markup=kb
            )
        else:
            await callback.answer('❌ Подпишитесь на канал сначала!', show_alert=True)
    except Exception as e:
        await callback.answer(f'❌ Ошибка: {str(e)}', show_alert=True)

@dp.callback_query(F.data == 'about')
async def about(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🏠 Главное меню', callback_data='menu')]
    ])
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media='https://images.unsplash.com/photo-1552664730-d307ca884978?w=400',
            caption='📚 О нас\n\nМы предлагаем практические курсы по IT, маркетингу и фрилансу.\nБолее 1000+ учеников прошли наши программы!\n\n✅ Актуальные навыки\n✅ Живое общение с преподавателями\n✅ Помощь в трудоустройстве'
        ),
        reply_markup=kb
    )

@dp.callback_query(F.data == 'promo')
async def promo(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🏠 Главное меню', callback_data='menu')]
    ])
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media='https://images.unsplash.com/photo-1552664730-d307ca884978?w=400',
            caption='🔥 АКЦИИ И ПРЕДЛОЖЕНИЯ\n\n🎁 Скидка 20% на все курсы до 20.01.2026\n🎁 Купи 2 курса — 3-й в подарок!\n🎁 Первая покупка — дополнительная скидка 10%\n\nВремя ограничено! Спешите!'
        ),
        reply_markup=kb
    )

@dp.callback_query(F.data == 'prices')
async def prices(callback: types.CallbackQuery):
    text = '💰 ВСЕ КУРСЫ И ЦЕНЫ\n\n'
    for k, v in courses.items():
        text += f"• {v['title']}: {v['price']/100}₽\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📚 В каталог', callback_data='catalog')],
        [InlineKeyboardButton(text='🏠 Главное меню', callback_data='menu')]
    ])
    await callback.message.edit_media(
        media=InputMediaPhoto(media='https://images.unsplash.com/photo-1552664730-d307ca884978?w=400', caption=text),
        reply_markup=kb
    )

@dp.callback_query(F.data == 'catalog')
async def catalog(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📖 {list(courses.values())[i]['title'][:25]}...", callback_data=f"course_{list(courses.keys())[i]}")]
        for i in range(len(courses))
    ] + [[InlineKeyboardButton(text='🏠 Меню', callback_data='menu')]])
    first_course = list(courses.values())[0]
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=first_course['photo'],
            caption=f"📚 КАТАЛОГ КУРСОВ\n\n{first_course['title']}\n{first_course['desc']}\n\n💰 {first_course['price']/100}₽\n\nВыберите нужный курс из списка:"
        ),
        reply_markup=kb
    )

@dp.callback_query(lambda c: c.data.startswith('course_'))
async def course_detail(callback: types.CallbackQuery):
    course_key = callback.data.split('_')[1]
    course = courses[course_key]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'🛒 Купить за {course["price"]/100}₽', callback_data=f'buy_{course_key}')],
        [InlineKeyboardButton(text='📚 Каталог', callback_data='catalog')],
        [InlineKeyboardButton(text='🏠 Меню', callback_data='menu')]
    ])
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=course['photo'],
            caption=f"📖 {course['title']}\n\n{course['desc']}\n\n💰 Цена: {course['price']/100}₽\n⏳ Доступ: {course['duration']} дней\n👥 100+ учеников уже купили"
        ),
        reply_markup=kb
    )

@dp.callback_query(F.data == 'my_subs')
async def my_subs(callback: types.CallbackQuery):
    subs = load_subs()
    user_subs = subs.get(str(callback.from_user.id), {})
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🏠 Меню', callback_data='menu')]
    ])
    if not user_subs:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media='https://images.unsplash.com/photo-1552664730-d307ca884978?w=400',
                caption='📋 У вас нет активных подписок.\n\nПейдите в каталог и купите курс!'
            ),
            reply_markup=kb
        )
        return
    text = '📋 ВАШ АКТИВНЫЕ ПОДПИСКИ:\n\n'
    for k, v in user_subs.items():
        text += f"✅ {courses[k]['title']}\n⏳ Дней осталось: {v['duration']}\n🔗 {v['access']}\n\n"
    await callback.message.edit_media(
        media=InputMediaPhoto(media='https://images.unsplash.com/photo-1552664730-d307ca884978?w=400', caption=text),
        reply_markup=kb
    )

@dp.callback_query(lambda c: c.data.startswith('buy_'))
async def buy_course(callback: types.CallbackQuery):
    course_key = callback.data.split('_')[1]
    course = courses[course_key]
    await bot.send_invoice(
        callback.from_user.id,
        title=course['title'],
        description=course['desc'],
        payload=course_key,
        provider_token='',
        currency='RUB',
        prices=[LabeledPrice(label=course['title'], amount=course['price'])]
    )
    await callback.answer('🧾 Счёт отправлен в чат!', show_alert=False)

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@dp.message(F.successful_payment)
async def deliver_course(msg: types.Message):
    course_key = msg.successful_payment.invoice_payload
    course = courses[course_key]
    user_id = str(msg.from_user.id)
    subs = load_subs()
    if user_id not in subs:
        subs[user_id] = {}
    subs[user_id][course_key] = {
        'start': datetime.now().isoformat(),
        'duration': course['duration'],
        'access': course['access']
    }
    save_subs(subs)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📋 Мои подписки', callback_data='my_subs')],
        [InlineKeyboardButton(text='🛒 Купить ещё', callback_data='catalog')],
        [InlineKeyboardButton(text='🏠 Меню', callback_data='menu')]
    ])
    await msg.answer_photo(
        photo=course['photo'],
        caption=f'✅ УСПЕХ! Курс активирован!\n\n📖 {course["title"]}\n🔗 Ссылка доступа: {course["access"]}\n⏳ Срок доступа: {course["duration"]} дней\n\nСохраните ссылку и начинайте учиться!',
        reply_markup=kb
    )

@dp.callback_query(F.data == 'menu')
async def menu(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='👥 О нас', callback_data='about')],
        [InlineKeyboardButton(text='📚 Каталог', callback_data='catalog')],
        [InlineKeyboardButton(text='🔥 Акции', callback_data='promo')],
        [InlineKeyboardButton(text='💰 Тарифы', callback_data='prices')],
        [InlineKeyboardButton(text='📋 Мои подписки', callback_data='my_subs')]
    ])
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media='https://images.unsplash.com/photo-1552664730-d307ca884978?w=400',
            caption='🏠 ГЛАВНОЕ МЕНЮ\n\nВыберите раздел:'
        ),
        reply_markup=kb
    )

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info('Бот запущен')
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
