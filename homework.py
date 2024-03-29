import logging
import os
import requests
import time
import telegram

from http import HTTPStatus
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='global.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('local.log', maxBytes=50000000, backupCount=5)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверяем наличие учетных данных."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Бот отправляет сообщение в telegram."""
    logger.info(f'Бот отправил в telegram сообщение: {message}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError:
        logger.error('Бот не смог отправить сообщение в telegram!')
    else:
        logger.debug(f'В telegram отправлено сообщение: {message}')


def get_api_answer(timestamp):
    """Опрашиваем API сервиса Практикум.Домашка."""
    payload = {'from_date': timestamp}
    logger.info('Опрашиваем API сервиса практикум.домашка.')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as error:
        raise Exception(f'Ошибка при запросе к API: {error}')
    if response.status_code != HTTPStatus.OK:
        status_code = response.status_code
        logger.info(
            f'На запрос: {response.content};'
            f'Код ответа сервера: {status_code}'
        )
        raise Exception(f'Код ответа сервера: {status_code}')
    try:
        return response.json()
    except Exception:
        raise Exception('Статуc не оптеделен')


def check_response(response):
    """Проверяем ответ API на соответствие документации."""
    logger.info('Проверяем ответ API на соответствие документации')
    if not isinstance(response, dict):
        raise TypeError('Ответ содержит не верный тип данных')
    missed_keys = {'homeworks', 'current_date'} - response.keys()
    if missed_keys:
        logger.error(f'В ответе API нет ожидаемых ключей: {missed_keys}')
    else:
        homeworks = response['homeworks']
    if isinstance(homeworks, list):
        return homeworks
    else:
        raise TypeError('Список "homeworks" пустой')


def parse_status(homeworks):
    """Извлекаем из данных статус по домашней работе."""
    missed_keys = {'status', 'homework_name'} - homeworks.keys()
    if missed_keys:
        logger.error(
            f'В списке "homeworks" нет ожидаемых ключей: {missed_keys}'
        )
    else:
        homework_status = homeworks['status']
        homework_name = homeworks['homework_name']
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        # В задании: Обязательно должны логироваться такие события:
        # отсутствие обязательных переменных окружения
        # во время запуска бота (уровень CRITICAL).
        logger.critical('Учетные данные переданы с ошибкой или отсутствуют')
        raise ValueError('Учетные данные переданы с ошибкой или отсутствуют')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    # timestamp = 0
    first_message = ''
    second_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)[0]
            message = parse_status(homeworks)
            if message != first_message:
                send_message(bot, message)
                first_message = message
            else:
                logger.debug('Статус домашней работы не изменился')
        except Exception as error:
            logging.error(error)
            error_message = (f'Ошибка программы: {error}')
            if error_message != second_message:
                send_message(bot, error_message)
                second_message = error_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
