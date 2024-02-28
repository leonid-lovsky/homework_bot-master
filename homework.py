import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from requests import RequestException
from telegram import TelegramError

load_dotenv()

ENV_VARS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    logger.debug('Отправка сообщения в Telegram.')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramError as error:
        raise IOError('Невозможно отправить сообщение в Telegram.') from error
    else:
        logger.info(f'Сообщение отправлено в Telegram: "{message}"')


def get_api_answer(current_timestamp):
    """Выполняет запрос к API."""
    logger.debug('Выполнение запроса к API.')
    try:
        timestamp = current_timestamp or int(time.time())
        params = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise RequestException(response=response)
    except RequestException as error:
        raise IOError(
            'Ошибка при выполнении запроса к API. Код ответа: '
            f'{error.response.status_code}'
        ) from error
    else:
        return response.json()


def check_response(response):
    """Проверяет ответ от API."""
    logger.debug('Проверка ответа от API.')
    if not isinstance(response, dict):
        raise TypeError(
            'В ответ на запрос от API пришел не словарь.'
            f' response = {response}.'
        )
    homeworks = response.get('homeworks')
    if 'homeworks' not in response:
        raise KeyError(
            'В ответе от API отсутствует ключ "homeworks".'
            f' response = {response}.'
        )
    if not isinstance(homeworks, list):
        raise TypeError(
            'В ответе от API под ключом "homeworks" пришел не список.'
            f' response = {response}.'
        )
    current_date = response.get('current_date')
    if 'current_date' not in response:
        raise KeyError(
            'В ответе от API отсутствует ключ "current_date".'
            f' response = {response}.'
        )
    if not isinstance(current_date, int):
        raise TypeError(
            'В ответе от API под ключом "current_date" пришло не число'
            ' (целое).'
            f' response = {response}.'
        )
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    logger.debug('Извлечение статуса домашней работы.')
    if not isinstance(homework, dict):
        raise TypeError(
            'В ответ на запрос от API пришел не словарь.'
            f' homework = {homework}.'
        )
    homework_name = homework.get('homework_name')
    if 'homework_name' not in homework:
        raise KeyError(
            'В ответе от API отсутствует ключ "homework_name".'
            f' homework = {homework}.'
        )
    if not isinstance(homework_name, str):
        raise TypeError(
            'В ответе от API под ключом "homework_name" пришла не строка.'
            f' homework = {homework}.'
        )
    status = homework.get('status')
    if 'status' not in homework:
        raise KeyError(
            'В ответе от API отсутствует ключ "status".'
            f' homework = {homework}.'
        )
    if not isinstance(status, str):
        raise TypeError(
            'В ответе от API под ключом "status" пришла не строка.'
            f' homework = {homework}.'
        )
    if status not in HOMEWORK_STATUSES:
        raise KeyError(
            'Недокументированный статус домашней работы.'
            f' homework = {homework}.'
        )
    verdict = HOMEWORK_STATUSES[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет обязательные переменные окружения."""
    logger.debug('Проверка обязательных переменных окружения.')
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы."""
    if not check_tokens():
        message = 'Отсутствует обязательная переменная окружения: '
        for v in ENV_VARS:
            if v not in os.environ:
                message += '\'' + v + '\''
        message += '\nПрограмма принудительно остановлена.'
        logger.critical(message)
        sys.exit(message)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    latest_error = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)

            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)

            if not len(homeworks):
                logger.debug('Статус проверки работ не изменился.')

            current_timestamp = response['current_date']

        except Exception as error:
            logger.exception(error)

            if latest_error != error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                latest_error = error

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
