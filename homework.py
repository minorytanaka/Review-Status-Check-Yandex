import logging
import os
import time
import sys
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

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
    filename='homework_logging.log',
    format='%(asctime)s, [%(levelname)s], %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Отправлено сообщение: "{message}".')
    except telegram.error.TelegramError as error:
        exception_message = f'Не удалось отправить сообщение: "{error}".'
        logger.error(exception_message)
        raise exceptions.SendMessageException(exception_message)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        response = requests.get(url=ENDPOINT,
                                headers=HEADERS,
                                params={'from_date': timestamp}
                                )
        result = response.json()
        if response.status_code != HTTPStatus.OK:
            message = f'Код ответа API: {response.status_code}'
            logger.error(message)
            raise exceptions.GetAPIAnswerException(message)
        return result
    except Exception as error:
        exception_message = (
            f'Не удалось отправить запрос эндпоинту API-сервиса: "{error}".'
        )
        logger.error(exception_message)
        raise exceptions.GetAPIAnswerException(exception_message)


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    expected_keys = ['current_date', 'homeworks']
    if not all(key in response for key in expected_keys):
        exception_message = (
            f'Ключи ответа не совпадают с ожидаемыми ключами: {expected_keys}.'
        )
        logger.error(exception_message)
        raise TypeError(exception_message)
    if not isinstance(response, dict):
        exception_message = (
            f'Данные ответа не совпадают с ожидаемыми: {type(response)}.'
        )
        logger.error(exception_message)
        raise TypeError(exception_message)
    if not isinstance(response['homeworks'], list):
        exception_message = (
            'Данные ответа под ключом "homeworks" приходят не в виде списка.'
        )
        logger.error(exception_message)
        raise TypeError(exception_message)
    homework = response['homeworks']
    return homework


def parse_status(homework):
    """Извлекает из домашней работы ёё статус."""
    homework_name = homework.get('homework_name')
    homework_verdict = homework.get('status')
    if homework_verdict not in HOMEWORK_VERDICTS:
        exception_message = (
            f'Неожиданный статус домашней работы: {homework_verdict}'
        )
        logger.error(exception_message)
        raise exceptions.ParseStatusException(exception_message)
    if not homework_name:
        exception_message = (
            'В ответе API нет ключа "homework_name".'
        )
        logger.error(exception_message)
        raise exceptions.ParseStatusException(exception_message)
    verdict = HOMEWORK_VERDICTS[homework_verdict]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exception_message = 'Проверьте переменные окружения.'
        logger.critical(exception_message)
        raise exceptions.CheckTokensException(exception_message)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    current_status = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)

            if not homework:
                logger.info('Статус не обновлён.')
            else:
                homework_status = parse_status(homework[0])
                if current_status == homework_status:
                    logger.debug(f'Статус работы {current_status}')
                else:
                    current_status = homework_status
                    send_message(bot, current_status)

        except Exception as error:
            exception_message = f'Сбой в работе программы: {error}'
            logger.error(exception_message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
