import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import time
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# === НАСТРОЙКИ ===
VK_TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = os.getenv('GROUP_ID') 

# Настройки Google Sheets
CREDENTIALS_JSON = json.loads(os.getenv('CREDENTIALS_JSON'))

SPREADSHEET_NAME = 'Бот СИМСИК'
WORKSHEET_NAME = 'Лист1'  # Имя листа в таблице

# === ИНИЦИАЛИЗАЦИЯ VK API ===
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

print("✅ Бот успешно запущен и ожидает команд!")

# === ФУНКЦИИ ДЛЯ РАБОТЫ С GOOGLE SHEETS ===
def get_commands_from_sheets():
    """
    Загружает команды и варианты из Google Sheets в формате:
    Первая строка - команды (заголовки столбцов)
    Последующие строки - варианты ответов для каждой команды

    Возвращает словарь: {команда: [вариант1, вариант2, ...]}
    """
    try:
        # Аутентификация с Google Sheets API
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(CREDENTIALS_JSON, scope)
        client = gspread.authorize(creds)

        # Открытие таблицы
        spreadsheet = client.open(SPREADSHEET_NAME)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

        # Получение всех данных
        all_data = worksheet.get_all_values()

        if not all_data:
            print("❌ Таблица пустая!")
            return {}

        # Первая строка содержит команды (заголовки столбцов)
        headers = all_data[0]
        rows = all_data[1:]  # Остальные строки - данные

        # Создаем словарь для хранения команд и их вариантов
        commands_dict = {}

        # Проходим по каждому заголовку (команде)
        for col_idx, command in enumerate(headers):
            if not command or not command.startswith('!'):
                continue  # Пропускаем пустые или не команды

            variants = []
            # Собираем все непустые варианты из этого столбца
            for row in rows:
                if col_idx < len(row):  # Проверяем, что столбец существует в этой строке
                    cell_value = row[col_idx].strip()
                    if cell_value:  # Добавляем только непустые значения
                        variants.append(cell_value)

            if variants:  # Добавляем команду только если есть варианты
                commands_dict[command] = variants
                print(f"✅ Загружена команда '{command}' с {len(variants)} вариантами")

        print(f"🎉 Всего загружено команд: {len(commands_dict)}")
        return commands_dict

    except Exception as e:
        print(f"❌ Ошибка при загрузке данных из Google Sheets: {e}")
        return {}

# === ОСНОВНАЯ ЛОГИКА БОТА ===
def get_random_response(command, commands_data):
    """
    Возвращает случайный ответ для заданной команды
    """
    command = command.strip().lower()

    # Ищем команду с учетом регистра
    if command in commands_data:
        return random.choice(commands_data[command])

    # Если не нашли точное совпадение, пробуем найти без учета регистра
    for cmd, variants in commands_data.items():
        if cmd.lower() == command:
            return random.choice(variants)

    return f"🤔 Команда '{command}' не найдена в таблице. Доступные команды: {', '.join(commands_data.keys())}"

# === ГЛАВНЫЙ ЦИКЛ БОТА ===
def main():
    # Загружаем команды из таблицы
    commands_data = get_commands_from_sheets()

    print("🚀 Бот готов к работе!")
    print("Доступные команды:", ', '.join(commands_data.keys()))

    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                msg = event.object.message

                # Проверяем, что сообщение из беседы (peer_id > 2000000000 для бесед)
                if 'peer_id' in msg and msg['peer_id'] < 2000000000:
                    continue  # Это личное сообщение, пропускаем

                text = msg['text'].strip()
                peer_id = msg['peer_id']
                from_id = msg['from_id']

                # Проверяем, является ли сообщение командой
                if text.startswith('!'):
                    command = text

                    # Получаем случайный ответ
                    response = get_random_response(command, commands_data)

                    # Отправляем ответ в беседу
                    try:
                        vk.messages.send(
                            peer_id=peer_id,
                            message=response,
                            random_id=0
                        )
                        print(f"📩 Отправлен ответ на команду '{command}': {response}")
                    except Exception as e:
                        print(f"❌ Ошибка при отправке сообщения: {e}")

    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        print("🔄 Попытка перезапуска через 5 секунд...")
        time.sleep(5)
        main()

# === ЗАПУСК БОТА ===
if __name__ == "__main__":
    main()