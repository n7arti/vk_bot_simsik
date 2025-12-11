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
import time
from datetime import datetime, timedelta, timezone

# Загружаем переменные окружения
load_dotenv()

# === НАСТРОЙКИ ===
VK_TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = os.getenv('GROUP_ID') 
USER_TOKEN = os.getenv('USER_TOKEN') 

# Настройки Google Sheets
with open('/home/n777arti/vk_bot_simsik/google_credentials.json', 'r') as f:
    CREDENTIALS_JSON = json.load(f)

SPREADSHEET_NAME = 'Бот СИМСИК'
WORKSHEET_NAME = 'Лист1'  # Имя листа в таблице

# === ИНИЦИАЛИЗАЦИЯ VK API ===
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

user_vk_session = vk_api.VkApi(token=USER_TOKEN)
user_vk = user_vk_session.get_api()

print("✅ Бот успешно запущен и ожидает команд!")

# === ФУНКЦИИ ДЛЯ РАБОТЫ С GOOGLE SHEETS ===
def get_commands_from_sheets():
    """
    Загружает команды и варианты из Google Sheets
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

        # Создаем словарь для хранения команд и их данных
        commands_dict = {}

        # Проходим по каждому заголовку (команде)
        for col_idx, command in enumerate(headers):
            if not command:
                continue
                
            command = command.strip()
            
            # Для команды !постысегодня обрабатываем особо
            if command.lower() == '!постысегодня':
                group_data = []
                for row in rows:
                    if col_idx < len(row):
                        cell_value = row[col_idx].strip()
                        if cell_value and ';' in cell_value:
                            group_data.append(cell_value)
                
                if group_data:
                    commands_dict[command] = {
                        'type': 'posts',
                        'data': group_data
                    }
                    print(f"✅ Загружена команда '{command}' с {len(group_data)} группами")
            
            # Для обычных команд (начинающихся с !)
            elif command.startswith('!'):
                variants = []
                for row in rows:
                    if col_idx < len(row):
                        cell_value = row[col_idx].strip()
                        if cell_value:
                            variants.append(cell_value)
                
                if variants:
                    commands_dict[command] = {
                        'type': 'random',
                        'data': variants
                    }
                    print(f"✅ Загружена команда '{command}' с {len(variants)} вариантами")

        print(f"🎉 Всего загружено команд: {len(commands_dict)}")
        return commands_dict

    except Exception as e:
        print(f"❌ Ошибка при загрузке данных из Google Sheets: {e}")
        return {}

# === ОСНОВНАЯ ЛОГИКА БОТА ===
def get_response_for_command(command, commands_data):
    """
    Возвращает ответ для заданной команды в зависимости от её типа
    """
    command = command.strip().lower()
    
    # Ищем команду с учетом регистра
    if command in commands_data:
        cmd_data = commands_data[command]
        
        if cmd_data['type'] == 'random':
            return random.choice(cmd_data['data'])
        elif cmd_data['type'] == 'posts':
            return get_posts_from_groups(cmd_data['data'])
    
    # Если не нашли точное совпадение, пробуем найти без учета регистра
    for cmd, cmd_data in commands_data.items():
        if cmd.lower() == command:
            if cmd_data['type'] == 'random':
                return random.choice(cmd_data['data'])
            elif cmd_data['type'] == 'posts':
                return get_posts_from_groups(cmd_data['data'])
    
    return f"🤔 Команда '{command}' не найдена в таблице. Доступные команды: {', '.join(commands_data.keys())}"

def get_posts_from_groups(group_data):
    """
    Получает последние посты из указанных групп и форматирует результат
    
    group_data: список строк в формате "[Название];[ID]"
    Возвращает: отформатированную строку с постами
    """
    try:
        results = []
        today = datetime.now(timezone(timedelta(hours=3)))  # Время VK - UTC+3
        today_date = today.date()
        
        for group_entry in group_data:
            if ';' not in group_entry:
                continue
                
            name, screen_name = group_entry.split(';', 1)
            name = name.strip()
            screen_name = screen_name.strip()
            
            try:
                group_info = vk.groups.getById(
                    group_id=screen_name,
                    fields='id'
                )
                
                if not group_info:
                    continue
                
                group_id = group_info[0]['id'] 
                
                posts = user_vk.wall.get(
                    owner_id=f"-{group_id}",  # Для групп owner_id отрицательный
                    count=10,
                    filter='owner'  # Только посты от имени группы
                )
                
                today_posts = []
                
                # Фильтруем ТОЛЬКО посты за сегодня
                for post in posts['items']:
                    post_date = datetime.fromtimestamp(post['date'], timezone(timedelta(hours=3))).date()
                    
                    if post_date == today_date:
                        today_posts.append(post)
                        
                if not today_posts:
                    continue
                
                post_links = []
                for i, post in enumerate(today_posts):  # Все посты без ограничения
                    post_id = post['id']
                    post_url = f"https://vk.com/wall-{group_id}_{post_id}"
                    post_links.append(f"[{post_url}|пост {i + 1}]")
                
                # Добавляем задержку между запросами к API
                time.sleep(0.4)
                
                if post_links:
                    results.append(f"{name}({', '.join(post_links)})")
                    
            except Exception as e:
                continue
        
        if results:
            return f"📊 **Посты {today_date.strftime('%d.%m.%Y')}:**\n" + "\n".join(results)
        else:
            return f"🤔 Не найдено постов за сегодня ({today_date.strftime('%d.%m.%Y')})"
            
    except Exception as e:
        print(f"❌ Критическая ошибка при получении постов: {e}")
        return "❌ Ошибка при получении данных о постах"

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
                    response = get_response_for_command(command, commands_data)

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