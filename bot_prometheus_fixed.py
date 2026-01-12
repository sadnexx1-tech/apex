import asyncio
import logging
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import aiohttp

# ═══════════════════════════════════════════════════════════════
# 📊 PROMETHEUS МЕТРИКИ (ИСПРАВЛЕННАЯ ВЕРСИЯ)
# ═══════════════════════════════════════════════════════════════

# Создаем ОДИН реестр для всех метрик
registry = CollectorRegistry()

# Регистрируем метрики ОДИН РАЗ в реестре
bothost_bots_created_created = Gauge(
    'bothost_bots_created_created',
    'Timestamp of bot creation',
    registry=registry
)

bothost_bots_created_total = Counter(
    'bothost_bots_created_total',
    'Total number of bots created',
    registry=registry
)

bothost_bots_created = Gauge(
    'bothost_bots_created',
    'Current number of active bots',
    registry=registry
)

# Дополнительные метрики
message_processing_time = Histogram(
    'message_processing_time_seconds',
    'Time taken to process messages',
    registry=registry
)

users_online = Gauge(
    'users_online',
    'Number of users currently online',
    registry=registry
)

payment_transactions = Counter(
    'payment_transactions_total',
    'Total number of payment transactions',
    ['status'],  # status: success, failed
    registry=registry
)

subscription_activations = Counter(
    'subscription_activations_total',
    'Total subscription activations',
    ['plan'],  # plan: lite, pro, unlimited
    registry=registry
)

# ═══════════════════════════════════════════════════════════════
# 🤖 БОТ КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'
PROMETHEUS_PORT = 8000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ═══════════════════════════════════════════════════════════════
# 🎯 ОБРАБОТЧИКИ БОТА
# ═══════════════════════════════════════════════════════════════

@dp.message(Command('start'))
async def start_command(message: types.Message):
    """Команда /start"""
    users_online.inc()
    
    await message.answer(
        '👋 Добро пожаловать в CourseBot!\n\n'
        'Это бот для продажи курсов с интеграцией Prometheus метрик.'
    )

@dp.message(Command('metrics'))
async def metrics_command(message: types.Message):
    """Показывает текущие метрики"""
    metrics = generate_latest(registry).decode('utf-8')
    
    await message.answer(
        f'📊 ТЕКУЩИЕ МЕТРИКИ:\n\n'
        f'```\n{metrics[:4000]}\n```',
        parse_mode='Markdown'
    )

@dp.message(Command('stats'))
async def stats_command(message: types.Message):
    """Показывает статистику"""
    await message.answer(
        f'📈 СТАТИСТИКА:\n\n'
        f'👥 Пользователей онлайн: {int(users_online._value.get())}\n'
        f'💳 Транзакций: {int(payment_transactions._metrics.get(("success",), 0))}\n'
        f'📦 Подписок активировано: {int(subscription_activations._metrics.get((("lite",), 0)))}',
        parse_mode='Markdown'
    )

# ═══════════════════════════════════════════════════════════════
# 🌐 PROMETHEUS HTTP SERVER
# ═══════════════════════════════════════════════════════════════

async def prometheus_server():
    """Запускает HTTP сервер для Prometheus"""
    from aiohttp import web
    
    async def metrics_handler(request):
        """Endpoint /metrics для Prometheus"""
        return web.Response(
            text=generate_latest(registry).decode('utf-8'),
            content_type=CONTENT_TYPE_LATEST
        )
    
    async def health_handler(request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'bots_active': int(bothost_bots_created._value.get()),
            'users_online': int(users_online._value.get())
        })
    
    # Создаем приложение
    app = web.Application()
    app.router.add_get('/metrics', metrics_handler)
    app.router.add_get('/health', health_handler)
    
    # Запускаем сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PROMETHEUS_PORT)
    await site.start()
    
    logger.info(f'✅ Prometheus metrics server запущен на http://0.0.0.0:{PROMETHEUS_PORT}/metrics')
    
    return runner

# ═══════════════════════════════════════════════════════════════
# 📝 ЛОГИРОВАНИЕ СОБЫТИЙ
# ═══════════════════════════════════════════════════════════════

def log_payment_transaction(status: str):
    """Логирует транзакцию платежа"""
    payment_transactions.labels(status=status).inc()
    logger.info(f'💳 Payment transaction: {status}')

def log_subscription_activation(plan: str):
    """Логирует активацию подписки"""
    subscription_activations.labels(plan=plan).inc()
    logger.info(f'📦 Subscription activated: {plan}')

def log_message_processing(processing_time: float):
    """Логирует время обработки сообщения"""
    message_processing_time.observe(processing_time)
    logger.info(f'⏱️ Message processed in {processing_time}s')

# ═══════════════════════════════════════════════════════════════
# 🚀 ЗАПУСК
# ═══════════════════════════════════════════════════════════════

async def main():
    """Главная функция"""
    
    # Инициализируем метрики
    bothost_bots_created.set(1)
    bothost_bots_created_total.inc()
    users_online.set(0)
    
    logger.info('🤖 CourseBot с Prometheus запущен!')
    
    # Запускаем Prometheus сервер
    prometheus_runner = await prometheus_server()
    
    # Запускаем бота
    try:
        await dp.start_polling(bot)
    finally:
        await prometheus_runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
