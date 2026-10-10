import asyncio
import base64
import html
import io
import json
import logging
import math
import os
import re
from datetime import datetime, timedelta
import pytz
import aiohttp

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = ""
ADMIN_IDS = []
GEMINI_API_KEY = ""

DEFAULT_GROUP = "УЭБО-07"

USERS_FILE = "users_data.json"
STAROSTAS_FILE = "starostas.json"
SCHEDULE_FILE = "schedule.json"
TICKETS_FILE = "tickets.json"
TZ = pytz.timezone("Europe/Moscow")

CAMPUSES = {
    "vern78": {
        "name": "Пр-т Вернадского, 78 (В-78)",
        "short_name": "В-78",
        "lat": 55.669986,
        "lon": 37.479815,
    },
    "pirogovka": {
        "name": "Малая Пироговская, 1с5 (МП-1)",
        "short_name": "МП-1",
        "lat": 55.731454,
        "lon": 37.575038,
    },
    "vern86": {
        "name": "Пр-т Вернадского, 86 (В-86)",
        "short_name": "В-86",
        "lat": 55.661642,
        "lon": 37.476483,
    },
    "stromynka": {
        "name": "Стромынка, 20",
        "short_name": "Стромынка",
        "lat": 55.794297,
        "lon": 37.701548,
    },
    "sokolinaya": {
        "name": "5-я ул. Соколиной Горы, 22",
        "short_name": "Соколиная Гора",
        "lat": 55.765103,
        "lon": 37.742354,
    },
}

MOSCOW_FALLBACK = {"lat": 55.7558, "lon": 37.6173}

DAYS_OF_WEEK = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

DAY_INDEX_MAP = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
}
REV_DAY_MAP = {v: k for k, v in DAY_INDEX_MAP.items()}

MIREA_TIMES = {
    1: "09:00–10:30",
    2: "10:40–12:10",
    3: "12:40–14:10",
    4: "14:20–15:50",
    5: "16:20–17:50",
    6: "18:00–19:30",
    7: "19:40–21:10",
}

# Расписание УЭБО-07 со скриншотов
UEBO_07_SCHEDULE = {
    "Нечётная": {
        "Понедельник": [
            {"num": 1, "time": "09:00–10:30", "type": "ЛК", "subject": "История России", "room": "А-63 (МП-1)", "teacher": "Анисимов Вячеслав Дмитриевич"},
            {"num": 2, "time": "10:40–12:10", "type": "ЛК", "subject": "Информатика", "room": "А-63 (МП-1)", "teacher": "Грушина Светлана Рафаиловна"},
            {"num": 3, "time": "12:40–14:10", "type": "ПР", "subject": "Математический анализ", "room": "А-400 (МП-1)", "teacher": "Богатырева Эмма Михайловна"},
        ],
        "Вторник": [
            {"num": 1, "time": "09:00–10:30", "type": "ПР", "subject": "Экономическая география и регионалистика", "room": "А-231 (МП-1)", "teacher": "Тарчоков Салим Казбекович"},
            {"num": 2, "time": "10:40–12:10", "type": "ЛК", "subject": "Экономическая теория", "room": "А-61 (МП-1)", "teacher": "Черноризова Нина Васильевна"},
            {"num": 3, "time": "12:40–14:10", "type": "ПР", "subject": "Информатика", "room": "Б-215 (МП-1)", "teacher": "Баландина Галина Ивановна"},
        ],
        "Среда": [
            {"num": 2, "time": "10:40–12:10", "type": "ПР", "subject": "История России", "room": "А-346 (МП-1)", "teacher": "Даноян Валерий Левович"},
            {"num": 3, "time": "12:40–14:10", "type": "ПР", "subject": "Экономическая теория", "room": "А-355 (МП-1)", "teacher": "Морозов Василий Алексеевич"},
        ],
        "Четверг": [
            {"num": 2, "time": "10:40–12:10", "type": "ПР", "subject": "Иностранный язык", "room": "И-312 (В-78)", "teacher": "Давтян Анаит Гагиковна"},
            {"num": 3, "time": "12:40–14:10", "type": "ПР", "subject": "Линейная алгебра", "room": "А-318 (В-78)", "teacher": "Капалин Иван Владимирович"},
        ],
        "Пятница": [
            {"num": 1, "time": "09:00–10:30", "type": "ЛК", "subject": "Производственно-хозяйственная деятельность", "room": "А-11 (В-78)", "teacher": "Вихрова Анна Сергеевна"},
            {"num": 2, "time": "10:40–12:10", "type": "ЛК", "subject": "Линейная алгебра", "room": "А-11 (В-78)", "teacher": "Гончарова Зоя Григорьевна"},
            {"num": 3, "time": "12:40–14:10", "type": "ПР", "subject": "Экономическая теория", "room": "А-328 (В-78)", "teacher": "Морозов Василий Алексеевич"},
            {"num": 4, "time": "14:20–15:50", "type": "ПР", "subject": "Физическая культура и спорт", "room": "ФОК-6 (В-78)", "teacher": "Колесников Анатолий Михайлович"},
            {"num": 5, "time": "16:20–17:50", "type": "ПР", "subject": "Производственно-хозяйственная деятельность", "room": "А-325 (В-78)", "teacher": "Вихрова Анна Сергеевна"},
        ],
        "Суббота": [],
    },
    "Чётная": {
        "Понедельник": [
            {"num": 1, "time": "09:00–10:30", "type": "ЛК", "subject": "История России", "room": "А-63 (МП-1)", "teacher": "Анисимов Вячеслав Дмитриевич"},
            {"num": 2, "time": "10:40–12:10", "type": "ЛК", "subject": "Введение в профессиональную деятельность", "room": "А-63 (МП-1)", "teacher": "Белоусова Ирина Викторовна"},
            {"num": 3, "time": "12:40–14:10", "type": "ПР", "subject": "Математический анализ", "room": "А-400 (МП-1)", "teacher": "Богатырева Эмма Михайловна"},
        ],
        "Вторник": [
            {"num": 1, "time": "09:00–10:30", "type": "ПР", "subject": "Экономическая география и регионалистика", "room": "А-231 (МП-1)", "teacher": "Тарчоков Салим Казбекович"},
            {"num": 2, "time": "10:40–12:10", "type": "ЛК", "subject": "Экономическая теория", "room": "А-61 (МП-1)", "teacher": "Черноризова Нина Васильевна"},
            {"num": 3, "time": "12:40–14:10", "type": "ПР", "subject": "Информатика", "room": "Б-215 (МП-1)", "teacher": "Баландина Галина Ивановна"},
        ],
        "Среда": [
            {"num": 2, "time": "10:40–12:10", "type": "ПР", "subject": "История России", "room": "А-346 (МП-1)", "teacher": "Даноян Валерий Левович"},
        ],
        "Четверг": [
            {"num": 1, "time": "09:00–10:30", "type": "ЛК", "subject": "Экономическая география и регионалистика", "room": "А-11 (В-78)", "teacher": "Фролов Александр Львович"},
            {"num": 2, "time": "10:40–12:10", "type": "ПР", "subject": "Иностранный язык", "room": "И-312 (В-78)", "teacher": "Давтян Анаит Гагиковна"},
            {"num": 3, "time": "12:40–14:10", "type": "ПР", "subject": "Линейная алгебра", "room": "А-318 (В-78)", "teacher": "Капалин Иван Владимирович"},
        ],
        "Пятница": [
            {"num": 2, "time": "10:40–12:10", "type": "ЛК", "subject": "Математический анализ", "room": "А-11 (В-78)", "teacher": "Гончарова Зоя Григорьевна"},
            {"num": 3, "time": "12:40–14:10", "type": "ПР", "subject": "Экономическая теория", "room": "А-328 (В-78)", "teacher": "Морозов Василий Алексеевич"},
            {"num": 4, "time": "14:20–15:50", "type": "ПР", "subject": "Физическая культура и спорт", "room": "ФОК-6 (В-78)", "teacher": "Колесников Анатолий Михайлович"},
            {"num": 5, "time": "16:20–17:50", "type": "ПР", "subject": "Производственно-хозяйственная деятельность", "room": "А-325 (В-78)", "teacher": "Вихрова Анна Сергеевна"},
        ],
        "Суббота": [],
    },
}

def create_empty_schedule_template() -> dict:
    return {
        "Нечётная": {d: [] for d in DAYS_OF_WEEK[:-1]},
        "Чётная": {d: [] for d in DAYS_OF_WEEK[:-1]},
    }

INITIAL_BASE_SCHEDULE = {"groups": {}}
for i in range(1, 14):
    g_name = f"УЭБО-{i:02d}"
    if g_name == "УЭБО-07":
        INITIAL_BASE_SCHEDULE["groups"][g_name] = UEBO_07_SCHEDULE
    else:
        INITIAL_BASE_SCHEDULE["groups"][g_name] = create_empty_schedule_template()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ==================== СОСТОЯНИЯ FSM ====================
class BotStates(StatesGroup):
    waiting_for_reg_group = State()
    waiting_for_reg_location = State()
    waiting_for_change_group = State()
    waiting_for_photo = State()
    admin_assign_starosta = State()
    admin_add_new_group = State()
    starosta_broadcast = State()
    admin_broadcast = State()
    editing_pair = State()
    user_submitting_ticket = State()
    admin_replying_ticket = State()


# ==================== ХРАНИЛИЩЕ ====================
def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_users(data: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user(user_id: int) -> dict:
    users = load_users()
    u = users.get(str(user_id), {})
    if "settings" not in u:
        u["settings"] = {
            "morning_notify": True,
            "evening_notify": True,
            "pair_notify": True,
            "show_route": True,
        }
    return u


def update_user(user_id: int, **kwargs):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "settings": {
                "morning_notify": True,
                "evening_notify": True,
                "pair_notify": True,
                "show_route": True,
            }
        }
    for k, v in kwargs.items():
        if k == "settings" and "settings" in users[uid]:
            users[uid]["settings"].update(v)
        else:
            users[uid][k] = v
    save_users(users)


def load_starostas() -> dict:
    if os.path.exists(STAROSTAS_FILE):
        try:
            with open(STAROSTAS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_starostas(data: dict):
    with open(STAROSTAS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_starosta(user_id: int) -> str | None:
    starostas = load_starostas()
    return starostas.get(str(user_id))


def load_schedule() -> dict:
    if not os.path.exists(SCHEDULE_FILE):
        save_schedule(INITIAL_BASE_SCHEDULE)
        return INITIAL_BASE_SCHEDULE
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "groups" not in data:
                data = INITIAL_BASE_SCHEDULE
                save_schedule(data)
                return data

            changed = False
            for i in range(1, 14):
                g_name = f"УЭБО-{i:02d}"
                if g_name not in data["groups"]:
                    if g_name == "УЭБО-07":
                        data["groups"][g_name] = UEBO_07_SCHEDULE
                    else:
                        data["groups"][g_name] = create_empty_schedule_template()
                    changed = True

            if "Чернига А." in data["groups"]:
                del data["groups"]["Чернига А."]
                changed = True

            if changed:
                save_schedule(data)
            return data
    except Exception:
        return INITIAL_BASE_SCHEDULE


def save_schedule(data: dict):
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_existing_groups() -> list[str]:
    sched = load_schedule()
    groups = list(sched.get("groups", {}).keys())
    groups.sort()
    return groups


def get_group_schedule(group_name: str) -> dict:
    sched = load_schedule()
    groups = sched.setdefault("groups", {})
    if group_name not in groups:
        groups[group_name] = create_empty_schedule_template()
        save_schedule(sched)
    return groups[group_name]


# ==================== ХРАНИЛИЩЕ ТИКЕТОВ ====================
def load_tickets() -> dict:
    if os.path.exists(TICKETS_FILE):
        try:
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_tickets(data: dict):
    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==================== ОПРЕДЕЛЕНИЕ ЧЁТНОСТИ ====================
def get_academic_week_parity(dt: datetime) -> str:
    year = dt.year
    if dt.month >= 9:
        sem_start = datetime(year, 9, 1, tzinfo=dt.tzinfo)
    elif dt.month == 1:
        sem_start = datetime(year - 1, 9, 1, tzinfo=dt.tzinfo)
    else:
        feb1 = datetime(year, 2, 1, tzinfo=dt.tzinfo)
        days_to_mon = (7 - feb1.weekday()) % 7
        first_mon = feb1 if feb1.weekday() == 0 else feb1 + timedelta(days=days_to_mon)
        sem_start = first_mon + timedelta(days=7)

    start_monday = sem_start - timedelta(days=sem_start.weekday())
    target_monday = dt - timedelta(days=dt.weekday())

    diff_weeks = (target_monday.date() - start_monday.date()).days // 7
    week_num = max(1, diff_weeks + 1)
    return "чётная" if (week_num % 2 == 0) else "нечётная"


def find_next_study_day(group: str, from_date: datetime) -> tuple[datetime, str, str, list] | None:
    sched = load_schedule()
    group_data = sched.get("groups", {}).get(group, {})
    for offset in range(1, 15):
        check_dt = from_date + timedelta(days=offset)
        w_idx = check_dt.weekday()
        if w_idx == 6:
            continue
        day_name = DAYS_OF_WEEK[w_idx]
        parity = get_academic_week_parity(check_dt)
        parity_title = "Чётная" if parity == "чётная" else "Нечётная"
        lessons = group_data.get(parity_title, {}).get(day_name, [])
        if lessons:
            return check_dt, day_name, parity, lessons
    return None


# ==================== МАРШРУТЫ И ГЕО ====================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_campus_data(room_str: str) -> dict:
    low = room_str.lower()
    if "мп-1" in low or "мп" in low or "пирогов" in low:
        return CAMPUSES["pirogovka"]
    elif "в-86" in low or "вернадского 86" in low:
        return CAMPUSES["vern86"]
    elif "стром" in low:
        return CAMPUSES["stromynka"]
    elif "сокол" in low:
        return CAMPUSES["sokolinaya"]
    return CAMPUSES["vern78"]


def calculate_commute(first_lesson: dict, user_loc: dict | None) -> dict:
    campus = get_campus_data(first_lesson.get("room", ""))
    c_lat, c_lon = campus["lat"], campus["lon"]

    if not user_loc:
        return {
            "has_location": False,
            "campus": campus["name"],
            "short_campus": campus["short_name"],
            "yandex_url": f"https://yandex.ru/maps/?text={c_lat},{c_lon}",
        }

    u_lat, u_lon = user_loc["lat"], user_loc["lon"]
    dist_km = haversine_km(u_lat, u_lon, c_lat, c_lon)
    yandex_url = f"https://yandex.ru/maps/?rtext={u_lat},{u_lon}~{c_lat},{c_lon}&rtt=mt"

    if dist_km > 80:
        return {
            "has_location": True,
            "too_far": True,
            "dist_km": round(dist_km),
            "campus": campus["name"],
            "short_campus": campus["short_name"],
            "yandex_url": yandex_url,
        }

    travel_min = max(20, round((15 + dist_km * 2.3) / 5) * 5)
    time_str = first_lesson.get("time", MIREA_TIMES.get(first_lesson.get("num", 1), "09:00"))
    m = re.search(r"(\d{1,2}):(\d{2})", time_str)
    if m:
        start_h, start_m = int(m.group(1)), int(m.group(2))
        today_start = datetime.now(TZ).replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        leave_dt = today_start - timedelta(minutes=travel_min + 15)
        leave_time_str = leave_dt.strftime("%H:%M")
    else:
        leave_time_str = "за 1 час до начала"

    return {
        "has_location": True,
        "too_far": False,
        "campus": campus["name"],
        "short_campus": campus["short_name"],
        "travel_time": f"~{travel_min} минут",
        "leave_time": leave_time_str,
        "yandex_url": yandex_url,
    }


# ==================== ПОГОДА ====================
async def get_weather_and_clothing_advice(lat: float, lon: float) -> tuple[str, str]:
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat:.4f}&longitude={lon:.4f}&current=temperature_2m,apparent_temperature,precipitation&timezone=auto"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                data = await resp.json()
                current = data.get("current", {})
                temp = round(current.get("temperature_2m", 10))
                apparent = round(current.get("apparent_temperature", temp))
                precip = current.get("precipitation", 0)

                temp_sign = f"+{temp}" if temp > 0 else str(temp)
                app_sign = f"+{apparent}" if apparent > 0 else str(apparent)
                rain_str = ", возможен дождь" if precip > 0.1 else ", без осадков"
                weather_summary = f"{temp_sign}°C (ощущается как {app_sign}°C){rain_str}"

                if apparent < 0:
                    advice = "На улице морозно: надевайте тёплую куртку, шапку и шарф."
                elif 0 <= apparent <= 8:
                    advice = "Холодно и сыро: надевайте демисезонную куртку и непромокаемую обувь."
                elif 9 <= apparent <= 16:
                    advice = "Прохладная погода: накиньте легкую куртку поверх худи."
                else:
                    advice = "На улице тепло: надевайте ветровку или рубашку."

                if precip > 0.1:
                    advice = advice.rstrip(".") + " и обязательно захватите зонт."
                return weather_summary, advice
    except Exception:
        return "+10°C, облачно", "Одевайтесь по погоде."


def format_lesson_quote(l: dict) -> str:
    num = l["num"]
    time_str = html.escape(l.get("time", MIREA_TIMES.get(num, "")))
    room = html.escape(l.get("room", "Аудитория не указана"))
    ltype = html.escape(l.get("type", "ПР"))
    sub = html.escape(l.get("subject", ""))
    teacher = html.escape(l.get("teacher", ""))

    header = f"<b>{num} · {room} · {time_str}</b>\n{ltype} · {sub}"
    if teacher:
        header += f"\n{teacher}"
    return f"<blockquote>{header}</blockquote>"


def build_week_overview(lessons_by_day: dict, group: str, parity: str, expanded_day: str | None = None) -> str:
    lines = [f"📅 <b>Расписание на неделю ({parity} неделя) • {group}</b>\n"]
    for day in DAYS_OF_WEEK[:-1]:
        day_lessons = lessons_by_day.get(day, [])
        count = len(day_lessons)
        count_str = "выходной" if count == 0 else f"{count} пар"

        if expanded_day == day and day_lessons:
            lines.append(f"∧ <b>{day} · {count_str}</b>")
            for item in day_lessons:
                lines.append(format_lesson_quote(item))
            lines.append("")
        else:
            lines.append(f"∨ {day} · {count_str}")
    return "\n".join(lines)


# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="⏭ Завтра")],
        [KeyboardButton(text="🗓 Расписание на неделю"), KeyboardButton(text="👤 Профиль")],
    ]
    if user_id in ADMIN_IDS:
        buttons.append([KeyboardButton(text="📷 Распознаватель"), KeyboardButton(text="⚙️ Админ-панель")])
    if is_starosta(user_id):
        buttons.append([KeyboardButton(text="🎓 Панель старосты")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_groups_inline_keyboard(prefix: str = "reg_grp") -> InlineKeyboardMarkup:
    groups = get_existing_groups()
    rows = []
    row = []
    for g in groups:
        row.append(InlineKeyboardButton(text=g, callback_data=f"{prefix}:{g}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


location_request_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Отправить геопозицию", request_location=True)],
        [KeyboardButton(text="🚫 Пропустить")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

recognizer_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Выйти из режима распознавания")]],
    resize_keyboard=True,
)


def get_week_keyboard(parity: str, expanded_day: str | None, current_parity: str) -> InlineKeyboardMarkup:
    w_code = "e" if parity == "чётная" else "o"
    d_code = str(REV_DAY_MAP[expanded_day]) if expanded_day in REV_DAY_MAP else "-"

    row1 = []
    for idx in range(6):
        short = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"][idx]
        next_d = "-" if d_code == str(idx) else str(idx)
        row1.append(InlineKeyboardButton(text=short, callback_data=f"w:{w_code}:{next_d}"))

    next_w_code = "o" if w_code == "e" else "e"
    next_week_name = "нечётная" if parity == "чётная" else "чётная"
    btn_text = f"🔄 Перейти на {next_week_name}ую" if parity == current_parity else f"🔄 Вернуться к текущей ({current_parity}ой)"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            row1,
            [
                InlineKeyboardButton(text=btn_text, callback_data=f"w:{next_w_code}:{d_code}"),
                InlineKeyboardButton(text="■ Свернуть", callback_data=f"w:{w_code}:-"),
            ],
        ]
    )


def get_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    m_icon = "✅" if settings.get("morning_notify", True) else "❌"
    e_icon = "✅" if settings.get("evening_notify", True) else "❌"
    p_icon = "✅" if settings.get("pair_notify", True) else "❌"
    r_icon = "✅" if settings.get("show_route", True) else "❌"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"☀️ Утренняя сводка (08:00): {m_icon}", callback_data="set_tog:morning_notify")],
            [InlineKeyboardButton(text=f"🌙 Вечерний план (22:00): {e_icon}", callback_data="set_tog:evening_notify")],
            [InlineKeyboardButton(text=f"🔔 Напоминание за 10 мин: {p_icon}", callback_data="set_tog:pair_notify")],
            [InlineKeyboardButton(text=f"🚇 Маршрут в утренней сводке: {r_icon}", callback_data="set_tog:show_route")],
            [InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="profile:back")],
        ]
    )


# ==================== УТРЕННЯЯ И ВЕЧЕРНЯЯ СВОДКИ ====================
async def generate_morning_payload(user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    now = datetime.now(TZ)
    weekday_idx = now.weekday()
    day_name = DAYS_OF_WEEK[weekday_idx]

    user_info = get_user(user_id)
    group = user_info.get("group", DEFAULT_GROUP)
    user_loc = user_info.get("location")
    user_settings = user_info.get("settings", {})

    lat = user_loc["lat"] if user_loc else MOSCOW_FALLBACK["lat"]
    lon = user_loc["lon"] if user_loc else MOSCOW_FALLBACK["lon"]
    weather_info, advice = await get_weather_and_clothing_advice(lat, lon)

    parity = get_academic_week_parity(now)
    parity_title = "Чётная" if parity == "чётная" else "Нечётная"

    group_sched = get_group_schedule(group)
    today_lessons = group_sched.get(parity_title, {}).get(day_name, []) if weekday_idx < 6 else []

    msg = [
        "☀️ <b>Доброе утро!</b>\n",
        f"📅 Сегодня <b>{day_name} • {parity} неделя • {group}</b>",
        f"🌡 <b>Погода:</b> {weather_info}",
        f"💡 <b>Рекомендация:</b> {advice}\n",
    ]

    kb_buttons = []

    if today_lessons:
        first = today_lessons[0]
        commute = calculate_commute(first, user_loc)

        if user_settings.get("show_route", True):
            if not commute.get("has_location"):
                msg.extend([
                    "🚇 <b>Маршрут:</b>",
                    f"📍 Корпус: <code>{commute['campus']}</code>",
                    "⏱ Время в пути: <i>Не определено</i>",
                    "🚪 <b>Выходить из дома в:</b> <i>Не определено</i>",
                    f"<i>(1-я пара начнется в {first['time'].split('–')[0].strip()})</i>\n",
                    "💡 <i>Отправьте /geo чтобы задать адрес и рассчитывать маршрут.</i>\n",
                ])
                kb_buttons.append([InlineKeyboardButton(text=f"🗺 Корпус на Картах ({commute['short_campus']})", url=commute["yandex_url"])])
            elif commute.get("too_far"):
                msg.extend([
                    "🚇 <b>Маршрут (Ваша геопозиция):</b>",
                    f"📍 Корпус: <code>{commute['campus']}</code>",
                    f"✈️ <b>Внимание:</b> Вы находитесь в другом городе (~{commute['dist_km']} км от Москвы).",
                    "<i>На метро не доехать — берите билет на поезд/самолет или подключайтесь на дистант!</i>\n",
                ])
                kb_buttons.append([InlineKeyboardButton(text=f"🗺 Посмотреть в Картах ({commute['short_campus']})", url=commute["yandex_url"])])
            else:
                msg.extend([
                    "🚇 <b>Маршрут (Ваша геопозиция):</b>",
                    f"📍 Корпус: <code>{commute['campus']}</code>",
                    f"⏱ Время в пути: {commute['travel_time']}",
                    f"🚪 <b>Выходить из дома в: {commute['leave_time']}</b>",
                    f"<i>(1-я пара начнется в {first['time'].split('–')[0].strip()})</i>\n",
                ])
                kb_buttons.append([InlineKeyboardButton(text=f"🗺 Проложить маршрут ({commute['short_campus']})", url=commute["yandex_url"])])

        msg.append("<b>Пары на сегодня:</b>")
        for item in today_lessons:
            msg.append(format_lesson_quote(item))
    else:
        next_day = find_next_study_day(group, now)
        if next_day:
            nxt_dt, nxt_day_name, _, _ = next_day
            msg.append(f"✨ Сегодня пар нет!\nБлижайший учебный день — <b>{nxt_day_name}</b> ({nxt_dt.strftime('%d.%m')}).")
            kb_buttons.append([InlineKeyboardButton(text=f"📅 {nxt_day_name}", callback_data=f"show_day:{nxt_dt.strftime('%Y-%m-%d')}")])
        else:
            msg.append("✨ Сегодня пар нет, можно отдыхать!")

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons) if kb_buttons else None
    return "\n".join(msg), kb


async def generate_evening_payload(user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    tomorrow = datetime.now(TZ) + timedelta(days=1)
    weekday_idx = tomorrow.weekday()
    day_name = DAYS_OF_WEEK[weekday_idx]

    user_info = get_user(user_id)
    group = user_info.get("group", DEFAULT_GROUP)

    parity = get_academic_week_parity(tomorrow)
    parity_title = "Чётная" if parity == "чётная" else "Нечётная"

    group_sched = get_group_schedule(group)
    lessons = group_sched.get(parity_title, {}).get(day_name, []) if weekday_idx < 6 else []

    header = f"🌙 <b>Добрый вечер!</b>\nРасписание на завтра (<b>{day_name} • {parity} неделя • {group}</b>):\n"

    if lessons:
        quotes = [format_lesson_quote(l) for l in lessons]
        return header + "\n\n".join(quotes) + "\n\nПриятного отдыха и продуктивного завтрашнего дня! 🛌", None
    else:
        next_day = find_next_study_day(group, tomorrow)
        kb = None
        if next_day:
            nxt_dt, nxt_day_name, _, _ = next_day
            day_status = f"Завтра {day_name.lower()}: занятий нет!" if weekday_idx == 6 else "Завтра занятий нет!"
            text = f"{header}✨ {day_status}\nБлижайший учебный день — <b>{nxt_day_name}</b> ({nxt_dt.strftime('%d.%m')})."
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=f"📅 {nxt_day_name}", callback_data=f"show_day:{nxt_dt.strftime('%Y-%m-%d')}")] ]
            )
        else:
            text = f"{header}✨ Завтра занятий нет, можно выспаться!"
        return text, kb


# ==================== ФОНОВЫЙ ВОРКЕР ====================
async def notifications_worker():
    sent_morning = ""
    sent_evening = ""
    sent_pairs = set()

    while True:
        try:
            now = datetime.now(TZ)
            today_str = now.strftime("%Y-%m-%d")
            users = load_users()

            # 1. Утренняя сводка в 08:00
            if now.hour == 8 and now.minute == 0 and sent_morning != today_str:
                sent_morning = today_str
                for uid, udata in users.items():
                    if udata.get("settings", {}).get("morning_notify", True):
                        try:
                            text, kb = await generate_morning_payload(int(uid))
                            await bot.send_message(int(uid), text, reply_markup=kb, parse_mode="HTML")
                        except Exception:
                            pass

            # 2. Вечерняя сводка в 22:00
            if now.hour == 22 and now.minute == 0 and sent_evening != today_str:
                sent_evening = today_str
                for uid, udata in users.items():
                    if udata.get("settings", {}).get("evening_notify", True):
                        try:
                            text, kb = await generate_evening_payload(int(uid))
                            await bot.send_message(int(uid), text, reply_markup=kb, parse_mode="HTML")
                        except Exception:
                            pass

            # 3. Напоминание за 10 минут до пары
            if now.weekday() < 6:
                day_name = DAYS_OF_WEEK[now.weekday()]
                parity = get_academic_week_parity(now)
                parity_title = "Чётная" if parity == "чётная" else "Нечётная"
                sched = load_schedule()

                for uid, udata in users.items():
                    if not udata.get("settings", {}).get("pair_notify", True):
                        continue

                    u_group = udata.get("group")
                    if not u_group:
                        continue
                    group_sched = sched.get("groups", {}).get(u_group, {})
                    today_pairs = group_sched.get(parity_title, {}).get(day_name, [])

                    for p in today_pairs:
                        time_str = p.get("time", "")
                        m = re.search(r"(\d{1,2}):(\d{2})", time_str)
                        if not m:
                            continue
                        start_h, start_m = int(m.group(1)), int(m.group(2))
                        pair_start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                        notif_time = pair_start - timedelta(minutes=10)

                        if now.hour == notif_time.hour and now.minute == notif_time.minute:
                            key = (today_str, p["num"], uid)
                            if key not in sent_pairs:
                                sent_pairs.add(key)
                                quote = format_lesson_quote(p)
                                msg = f"🔔 <b>{p['num']} пара начнется через 10 минут:</b>\n{quote}"
                                try:
                                    await bot.send_message(int(uid), msg, parse_mode="HTML")
                                except Exception:
                                    pass

            if now.hour == 0 and now.minute == 0:
                sent_pairs.clear()

        except Exception as e:
            logging.error(f"Worker error: {e}")

        await asyncio.sleep(25)


# ==================== СТАРТ И РЕГИСТРАЦИЯ ====================
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    user_info = get_user(uid)

    if not user_info.get("group"):
        await state.set_state(BotStates.waiting_for_reg_group)
        kb = get_groups_inline_keyboard(prefix="reg_grp")
        await message.answer(
            "Привет! Добро пожаловать в бот расписания РТУ МИРЭА.\n\n"
            "Пожалуйста, <b>выберите вашу учебную группу</b> из списка ниже:",
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"Привет! Ваша группа: <b>{user_info.get('group')}</b>.\n"
            "Используйте кнопки меню внизу для просмотра расписания.",
            reply_markup=get_main_keyboard(uid),
            parse_mode="HTML",
        )


@dp.callback_query(BotStates.waiting_for_reg_group, F.data.startswith("reg_grp:"))
async def reg_group_picked(call: types.CallbackQuery, state: FSMContext):
    group_name = call.data.split(":")[1]
    update_user(call.from_user.id, group=group_name)

    await state.set_state(BotStates.waiting_for_reg_location)
    await call.message.edit_text(f"Группа <b>{group_name}</b> выбрана!", parse_mode="HTML")
    await call.message.answer(
        "Теперь отправьте свою геопозицию кнопкой ниже, чтобы бот мог рассчитывать время в пути до корпусов МИРЭА, "
        "или нажмите «🚫 Пропустить»:",
        reply_markup=location_request_kb,
        parse_mode="HTML",
    )
    await call.answer()


@dp.message(BotStates.waiting_for_reg_group)
async def reg_group_text_entered(message: types.Message, state: FSMContext):
    text = message.text.strip()
    available = get_existing_groups()
    if text in available:
        update_user(message.from_user.id, group=text)
        await state.set_state(BotStates.waiting_for_reg_location)
        await message.answer(
            f"Группа <b>{text}</b> сохранена!\n\n"
            "Отправьте геопозицию кнопкой ниже или нажмите «🚫 Пропустить»:",
            reply_markup=location_request_kb,
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "❌ Такой группы пока нет в базе расписания.\n"
            "Пожалуйста, выберите группу кнопкой ниже:",
            reply_markup=get_groups_inline_keyboard(prefix="reg_grp"),
        )


@dp.message(BotStates.waiting_for_reg_location, F.location)
async def process_reg_location(message: types.Message, state: FSMContext):
    loc = message.location
    update_user(message.from_user.id, location={"lat": loc.latitude, "lon": loc.longitude})
    await state.clear()
    await message.answer(
        "✅ Геолокация сохранена! Настройка завершена.",
        reply_markup=get_main_keyboard(message.from_user.id),
    )


@dp.message(BotStates.waiting_for_reg_location, F.text == "🚫 Пропустить")
async def process_reg_skip(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Настройка завершена! Вы всегда сможете задать геопозицию позже через команду /geo.",
        reply_markup=get_main_keyboard(message.from_user.id),
    )


# ==================== СМЕНА ГРУППЫ ====================
@dp.message(Command(commands=["changegroup"]))
async def changegroup_cmd(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.waiting_for_change_group)
    kb = get_groups_inline_keyboard(prefix="ch_grp")
    await message.answer("Выберите группу из списка доступных:", reply_markup=kb)


@dp.callback_query(BotStates.waiting_for_change_group, F.data.startswith("ch_grp:"))
async def change_group_callback(call: types.CallbackQuery, state: FSMContext):
    group_name = call.data.split(":")[1]
    update_user(call.from_user.id, group=group_name)
    await state.clear()
    await call.message.edit_text(f"✅ Группа успешно изменена на <b>{group_name}</b>!", parse_mode="HTML")
    await call.message.answer("Используйте меню для работы с расписанием:", reply_markup=get_main_keyboard(call.from_user.id))
    await call.answer()


@dp.message(BotStates.waiting_for_change_group)
async def change_group_text(message: types.Message, state: FSMContext):
    text = message.text.strip()
    available = get_existing_groups()
    if text in available:
        update_user(message.from_user.id, group=text)
        await state.clear()
        await message.answer(
            f"✅ Группа успешно изменена на <b>{text}</b>!",
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "❌ Данная группа не создана. Выберите одну из существующих:",
            reply_markup=get_groups_inline_keyboard(prefix="ch_grp"),
        )


# ==================== МОЙ ПРОФИЛЬ И НАСТРОЙКИ ====================
@dp.message(F.text == "👤 Профиль")
async def profile_cmd(message: types.Message):
    uid = message.from_user.id
    u = get_user(uid)
    group = u.get("group", "Не выбрана")
    loc_status = "✅ Сохранена" if u.get("location") else "❌ Не указана (/geo)"

    role = "Студент"
    if uid in ADMIN_IDS:
        role = "Администратор"
    elif is_starosta(uid):
        role = f"Староста группы {is_starosta(uid)}"

    text = (
        f"👤 <b>Личный профиль:</b>\n\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"👥 <b>Группа:</b> <b>{group}</b>\n"
        f"📍 <b>Геопозиция:</b> {loc_status}\n"
        f"🎓 <b>Статус:</b> {role}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настройки уведомлений", callback_data="open:settings")],
            [InlineKeyboardButton(text="🔄 Сменить группу", callback_data="open:changegroup")],
            [InlineKeyboardButton(text="📨 Создать обращение", callback_data="ticket:new")],
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data == "open:settings")
async def settings_open_callback(call: types.CallbackQuery):
    u = get_user(call.from_user.id)
    kb = get_settings_keyboard(u.get("settings", {}))
    await call.message.edit_text(
        "⚙️ <b>Настройки персональных уведомлений:</b>\n\n"
        "Нажимайте на кнопки, чтобы включать или отключать нужные опции:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await call.answer()


@dp.callback_query(F.data.startswith("set_tog:"))
async def toggle_setting_callback(call: types.CallbackQuery):
    param = call.data.split(":")[1]
    u = get_user(call.from_user.id)
    cur_settings = u.get("settings", {})
    cur_settings[param] = not cur_settings.get(param, True)

    update_user(call.from_user.id, settings=cur_settings)
    kb = get_settings_keyboard(cur_settings)
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest:
        pass
    await call.answer()


@dp.callback_query(F.data == "profile:back")
async def profile_back_callback(call: types.CallbackQuery):
    uid = call.from_user.id
    u = get_user(uid)
    group = u.get("group", "Не выбрана")
    loc_status = "✅ Сохранена" if u.get("location") else "❌ Не указана (/geo)"

    role = "Студент"
    if uid in ADMIN_IDS:
        role = "Администратор"
    elif is_starosta(uid):
        role = f"Староста группы {is_starosta(uid)}"

    text = (
        f"👤 <b>Личный профиль:</b>\n\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"👥 <b>Группа:</b> <b>{group}</b>\n"
        f"📍 <b>Геопозиция:</b> {loc_status}\n"
        f"🎓 <b>Статус:</b> {role}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настройки уведомлений", callback_data="open:settings")],
            [InlineKeyboardButton(text="🔄 Сменить группу", callback_data="open:changegroup")],
            [InlineKeyboardButton(text="📨 Создать обращение", callback_data="ticket:new")],
        ]
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data == "open:changegroup")
async def open_change_group_from_profile(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.waiting_for_change_group)
    kb = get_groups_inline_keyboard(prefix="ch_grp")
    await call.message.edit_text("Выберите группу из списка созданных:", reply_markup=kb)
    await call.answer()


# ==================== СИСТЕМА ОБРАЩЕНИЙ (ТИКЕТЫ) ====================
@dp.callback_query(F.data == "ticket:new")
async def user_start_ticket(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.user_submitting_ticket)
    await call.message.answer(
        "📝 <b>Создание обращения:</b>\n\n"
        "Опишите вашу проблему, вопрос или предложение одним текстовым сообщением. "
        "Администраторы увидят его и ответят прямо через бота:",
        parse_mode="HTML",
    )
    await call.answer()


@dp.message(BotStates.user_submitting_ticket)
async def user_send_ticket_text(message: types.Message, state: FSMContext):
    text = message.text.strip() if message.text else "Вложение/Медиа"
    uid = message.from_user.id
    username = message.from_user.username or "без username"
    user_info = get_user(uid)
    group = user_info.get("group", "Не указана")

    tickets = load_tickets()
    ticket_id = str(len(tickets) + 1)

    tickets[ticket_id] = {
        "user_id": uid,
        "username": username,
        "first_name": message.from_user.first_name,
        "group": group,
        "text": text,
        "date": datetime.now(TZ).strftime("%d.%m.%Y %H:%M"),
        "status": "open",
    }
    save_tickets(tickets)
    await state.clear()

    await message.answer(
        f"✅ Ваше обращение <b>#{ticket_id}</b> успешно отправлено администрации!\n"
        "Когда вам ответят, уведомление придёт сюда в диалог с ботом.",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(uid),
    )

    # Оповещение администраторов
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                aid,
                f"📬 <b>Новое обращение #{ticket_id}</b>\n"
                f"От: @{username} (ID: <code>{uid}</code>)\n"
                f"Группа: <b>{group}</b>\n\n"
                f"💬 <i>{html.escape(text)}</i>",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="✍️ Ответить", callback_data=f"adm_t_reply:{ticket_id}")]]
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass


# ==================== УПРАВЛЕНИЕ ГЕОЛОКАЦИЕЙ ====================
@dp.message(Command(commands=["geo"]))
async def geo_cmd(message: types.Message):
    await message.answer(
        "📍 Отправьте геопозицию кнопкой ниже для расчёта маршрута и времени выезда:",
        reply_markup=location_request_kb,
    )


@dp.message(F.location)
async def handle_direct_location(message: types.Message):
    loc = message.location
    update_user(message.from_user.id, location={"lat": loc.latitude, "lon": loc.longitude})
    await message.answer(
        "✅ Геолокация сохранена! Маршрут и время выхода обновлены.",
        reply_markup=get_main_keyboard(message.from_user.id),
    )


# ==================== ПРОСМОТР РАСПИСАНИЯ ====================
@dp.message(F.text == "📅 Сегодня")
async def today_cmd(message: types.Message):
    now = datetime.now(TZ)
    weekday_idx = now.weekday()
    day_name = DAYS_OF_WEEK[weekday_idx]

    user_info = get_user(message.from_user.id)
    group = user_info.get("group", DEFAULT_GROUP)

    parity = get_academic_week_parity(now)
    parity_title = "Чётная" if parity == "чётная" else "Нечётная"

    group_sched = get_group_schedule(group)
    lessons = group_sched.get(parity_title, {}).get(day_name, []) if weekday_idx < 6 else []

    header = f"📅 <b>{day_name} • {parity} неделя • {group}</b>\n\n"

    if not lessons:
        next_day = find_next_study_day(group, now)
        if next_day:
            nxt_dt, nxt_day_name, _, _ = next_day
            text = f"{header}✨ Сегодня занятий нет!\nБлижайший учебный день — <b>{nxt_day_name}</b> ({nxt_dt.strftime('%d.%m')})."
            day_btn = InlineKeyboardButton(text=f"📅 {nxt_day_name}", callback_data=f"show_day:{nxt_dt.strftime('%Y-%m-%d')}")
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[day_btn]]), parse_mode="HTML")
        else:
            await message.answer(header + "✨ Занятий нет!", parse_mode="HTML")
        return

    quotes = [format_lesson_quote(l) for l in lessons]
    await message.answer(header + "\n\n".join(quotes), parse_mode="HTML")


@dp.message(F.text == "⏭ Завтра")
async def tomorrow_cmd(message: types.Message):
    tomorrow = datetime.now(TZ) + timedelta(days=1)
    weekday_idx = tomorrow.weekday()
    day_name = DAYS_OF_WEEK[weekday_idx]

    user_info = get_user(message.from_user.id)
    group = user_info.get("group", DEFAULT_GROUP)

    parity = get_academic_week_parity(tomorrow)
    parity_title = "Чётная" if parity == "чётная" else "Нечётная"

    group_sched = get_group_schedule(group)
    lessons = group_sched.get(parity_title, {}).get(day_name, []) if weekday_idx < 6 else []

    header = f"📅 <b>{day_name} • {parity} неделя • {group}</b>\n\n"

    if not lessons:
        next_day = find_next_study_day(group, tomorrow)
        if next_day:
            nxt_dt, nxt_day_name, _, _ = next_day
            day_status = f"Завтра {day_name.lower()}: занятий нет!" if weekday_idx == 6 else "Завтра занятий нет!"
            text = f"{header}✨ {day_status}\nБлижайший учебный день — <b>{nxt_day_name}</b> ({nxt_dt.strftime('%d.%m')})."
            day_btn = InlineKeyboardButton(text=f"📅 {nxt_day_name}", callback_data=f"show_day:{nxt_dt.strftime('%Y-%m-%d')}")
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[day_btn]]), parse_mode="HTML")
        else:
            await message.answer(header + "✨ Завтра занятий нет!", parse_mode="HTML")
        return

    quotes = [format_lesson_quote(l) for l in lessons]
    await message.answer(header + "\n\n".join(quotes), parse_mode="HTML")


@dp.callback_query(F.data.startswith("show_day:"))
async def show_specific_day_callback(call: types.CallbackQuery):
    date_str = call.data.split(":")[1]
    target_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=TZ)
    w_idx = target_dt.weekday()
    day_name = DAYS_OF_WEEK[w_idx]

    parity = get_academic_week_parity(target_dt)
    parity_title = "Чётная" if parity == "чётная" else "Нечётная"

    user_info = get_user(call.message.chat.id)
    group = user_info.get("group", DEFAULT_GROUP)

    group_sched = get_group_schedule(group)
    lessons = group_sched.get(parity_title, {}).get(day_name, [])

    header = f"📅 <b>{day_name} ({target_dt.strftime('%d.%m')}) • {parity} неделя • {group}</b>\n\n"
    if not lessons:
        text = header + "✨ Занятий нет!"
    else:
        quotes = [format_lesson_quote(l) for l in lessons]
        text = header + "\n\n".join(quotes)

    await call.message.answer(text, parse_mode="HTML")
    await call.answer()


@dp.message(F.text == "🗓 Расписание на неделю")
async def week_cmd(message: types.Message):
    now = datetime.now(TZ)
    parity = get_academic_week_parity(now)
    parity_title = "Чётная" if parity == "чётная" else "Нечётная"

    user_info = get_user(message.from_user.id)
    group = user_info.get("group", DEFAULT_GROUP)

    group_sched = get_group_schedule(group)
    text = build_week_overview(group_sched.get(parity_title, {}), group, parity, None)
    kb = get_week_keyboard(parity, None, parity)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("w:"))
async def week_callback(call: types.CallbackQuery):
    parts = call.data.split(":")
    w_code, d_code = parts[1], parts[2]

    parity = "чётная" if w_code == "e" else "нечётная"
    parity_title = "Чётная" if parity == "чётная" else "Нечётная"
    expanded_day = DAY_INDEX_MAP[int(d_code)] if d_code.isdigit() and int(d_code) in DAY_INDEX_MAP else None

    now = datetime.now(TZ)
    current_parity = get_academic_week_parity(now)

    user_info = get_user(call.message.chat.id)
    group = user_info.get("group", DEFAULT_GROUP)

    group_sched = get_group_schedule(group)
    text = build_week_overview(group_sched.get(parity_title, {}), group, parity, expanded_day)
    kb = get_week_keyboard(parity, expanded_day, current_parity)

    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()


# ==================== ПАНЕЛЬ СТАРОСТЫ ====================
@dp.message(F.text == "🎓 Панель старосты")
async def starosta_menu(message: types.Message):
    group = is_starosta(message.from_user.id)
    if not group:
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить пару", callback_data=f"edit_group:{group}")],
            [InlineKeyboardButton(text="📢 Объявление для своей группы", callback_data="starosta:broadcast")],
        ]
    )
    await message.answer(f"🎓 <b>Панель старосты группы {group}:</b>", reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data == "starosta:broadcast")
async def starosta_broadcast_prompt(call: types.CallbackQuery, state: FSMContext):
    group = is_starosta(call.from_user.id)
    if not group:
        return
    await state.set_state(BotStates.starosta_broadcast)
    await call.message.answer(f"Введите текст объявления для студентов группы <b>{group}</b>:", parse_mode="HTML")
    await call.answer()


@dp.message(BotStates.starosta_broadcast)
async def starosta_broadcast_send(message: types.Message, state: FSMContext):
    group = is_starosta(message.from_user.id)
    if not group:
        await state.clear()
        return

    users = load_users()
    count = 0
    for uid, data in users.items():
        if data.get("group") == group:
            try:
                await bot.send_message(
                    int(uid),
                    f"📢 <b>Объявление от старосты ({group}):</b>\n\n{html.escape(message.text)}",
                    parse_mode="HTML",
                )
                count += 1
            except Exception:
                pass

    await state.clear()
    await message.answer(f"✅ Объявление доставлено {count} студентам вашей группы.", reply_markup=get_main_keyboard(message.from_user.id))


# ==================== АДМИН-ПАНЕЛЬ ====================
@dp.message(F.text == "⚙️ Админ-панель", F.from_user.id.in_(ADMIN_IDS))
async def admin_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📬 Обращения", callback_data="adm:tickets_menu")],
            [InlineKeyboardButton(text="➕ Создать новую группу", callback_data="adm:add_new_group")],
            [InlineKeyboardButton(text="🗑 Удалить группу", callback_data="adm:delete_group_menu")],
            [InlineKeyboardButton(text="👑 Назначить/Снять старосту", callback_data="adm:starostas_menu")],
            [InlineKeyboardButton(text="✏️ Редактировать расписание", callback_data="adm:select_group_to_edit")],
            [InlineKeyboardButton(text="📢 Общая рассылка (всем)", callback_data="adm:broadcast_all")],
            [InlineKeyboardButton(text="📤 Выгрузить schedule.json", callback_data="adm:export_file")],
        ]
    )
    await message.answer("⚙️ <b>Панель главного администратора:</b>", reply_markup=kb, parse_mode="HTML")


# Меню тикетов в админке
@dp.callback_query(F.data == "adm:tickets_menu", F.from_user.id.in_(ADMIN_IDS))
async def adm_tickets_menu(call: types.CallbackQuery):
    tickets = load_tickets()
    open_tickets = {tid: t for tid, t in tickets.items() if t.get("status") == "open"}

    if not open_tickets:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")]])
        await call.message.edit_text("📬 <b>Открытых обращений нет.</b>", reply_markup=kb, parse_mode="HTML")
        await call.answer()
        return

    rows = []
    for tid, t in open_tickets.items():
        short_desc = (t['text'][:25] + "...") if len(t['text']) > 25 else t['text']
        rows.append([InlineKeyboardButton(text=f"#{tid} ({t['group']}): {short_desc}", callback_data=f"adm_t_view:{tid}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")])

    await call.message.edit_text("📬 <b>Список открытых обращений:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("adm_t_view:"), F.from_user.id.in_(ADMIN_IDS))
async def adm_ticket_view(call: types.CallbackQuery):
    tid = call.data.split(":")[1]
    tickets = load_tickets()
    t = tickets.get(tid)

    if not t:
        await call.message.answer("Обращение не найдено.")
        await call.answer()
        return

    text = (
        f"📬 <b>Обращение #{tid}</b>\n\n"
        f"👤 От: @{t.get('username', '–')} (ID: <code>{t['user_id']}</code>)\n"
        f"👥 Группа: <b>{t['group']}</b>\n"
        f"📅 Дата: {t['date']}\n"
        f"Статус: <b>{t['status']}</b>\n\n"
        f"💬 <b>Текст:</b>\n{html.escape(t['text'])}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Ответить", callback_data=f"adm_t_reply:{tid}")],
            [InlineKeyboardButton(text="✅ Закрыть обращение", callback_data=f"adm_t_close:{tid}")],
            [InlineKeyboardButton(text="⬅️ К списку обращений", callback_data="adm:tickets_menu")],
        ]
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("adm_t_close:"), F.from_user.id.in_(ADMIN_IDS))
async def adm_ticket_close(call: types.CallbackQuery):
    tid = call.data.split(":")[1]
    tickets = load_tickets()
    if tid in tickets:
        tickets[tid]["status"] = "closed"
        save_tickets(tickets)
        await call.message.answer(f"✅ Обращение #{tid} закрыто.")
    await adm_tickets_menu(call)


@dp.callback_query(F.data.startswith("adm_t_reply:"), F.from_user.id.in_(ADMIN_IDS))
async def adm_ticket_reply_prompt(call: types.CallbackQuery, state: FSMContext):
    tid = call.data.split(":")[1]
    tickets = load_tickets()
    t = tickets.get(tid)

    if not t:
        await call.message.answer("Обращение не найдено.")
        await call.answer()
        return

    await state.set_state(BotStates.admin_replying_ticket)
    await state.update_data(tid=tid, user_id=t["user_id"])
    await call.message.answer(
        f"✍️ Введите текст ответа на обращение <b>#{tid}</b> (пользователю @{t.get('username')}):",
        parse_mode="HTML",
    )
    await call.answer()


@dp.message(BotStates.admin_replying_ticket, F.from_user.id.in_(ADMIN_IDS))
async def adm_ticket_reply_send(message: types.Message, state: FSMContext):
    data = await state.get_data()
    tid = data["tid"]
    target_uid = data["user_id"]
    reply_text = message.text.strip()

    try:
        await bot.send_message(
            target_uid,
            f"📬 <b>Ответ администрации на ваше обращение #{tid}:</b>\n\n"
            f"{html.escape(reply_text)}",
            parse_mode="HTML",
        )
        tickets = load_tickets()
        if tid in tickets:
            tickets[tid]["status"] = "closed"
            save_tickets(tickets)

        await message.answer(f"✅ Ответ успешно доставлен пользователю! Обращение #{tid} закрыто.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить ответ пользователю: {e}")

    await state.clear()


@dp.callback_query(F.data == "adm:delete_group_menu", F.from_user.id.in_(ADMIN_IDS))
async def adm_delete_group_menu(call: types.CallbackQuery):
    groups = get_existing_groups()
    rows = []
    row = []
    for g in groups:
        row.append(InlineKeyboardButton(text=f"❌ {g}", callback_data=f"adm_del_grp:{g}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")])
    await call.message.edit_text("Выберите группу, которую хотите <b>удалить</b>:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("adm_del_grp:"), F.from_user.id.in_(ADMIN_IDS))
async def adm_delete_group_confirm(call: types.CallbackQuery):
    grp_name = call.data.split(":")[1]
    sched = load_schedule()
    if grp_name in sched.get("groups", {}):
        del sched["groups"][grp_name]
        save_schedule(sched)
        await call.message.answer(f"✅ Группа <b>{grp_name}</b> успешно удалена из системы!", parse_mode="HTML")
    await adm_delete_group_menu(call)


@dp.callback_query(F.data == "adm:back", F.from_user.id.in_(ADMIN_IDS))
async def adm_back_callback(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📬 Обращения", callback_data="adm:tickets_menu")],
            [InlineKeyboardButton(text="➕ Создать новую группу", callback_data="adm:add_new_group")],
            [InlineKeyboardButton(text="🗑 Удалить группу", callback_data="adm:delete_group_menu")],
            [InlineKeyboardButton(text="👑 Назначить/Снять старосту", callback_data="adm:starostas_menu")],
            [InlineKeyboardButton(text="✏️ Редактировать расписание", callback_data="adm:select_group_to_edit")],
            [InlineKeyboardButton(text="📢 Общая рассылка (всем)", callback_data="adm:broadcast_all")],
            [InlineKeyboardButton(text="📤 Выгрузить schedule.json", callback_data="adm:export_file")],
        ]
    )
    await call.message.edit_text("⚙️ <b>Панель главного администратора:</b>", reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data == "adm:add_new_group", F.from_user.id.in_(ADMIN_IDS))
async def adm_add_new_group_prompt(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.admin_add_new_group)
    await call.message.answer("Введите название новой учебной группы для добавления (например, <code>УЭБО-14</code>):", parse_mode="HTML")
    await call.answer()


@dp.message(BotStates.admin_add_new_group, F.from_user.id.in_(ADMIN_IDS))
async def adm_add_new_group_save(message: types.Message, state: FSMContext):
    grp_name = message.text.strip()
    sched = load_schedule()
    if grp_name not in sched.get("groups", {}):
        get_group_schedule(grp_name)
        await message.answer(f"✅ Группа <b>{grp_name}</b> успешно создана!", parse_mode="HTML")
    else:
        await message.answer(f"Группа <b>{grp_name}</b> уже существовала.", parse_mode="HTML")
    await state.clear()


@dp.callback_query(F.data == "adm:starostas_menu", F.from_user.id.in_(ADMIN_IDS))
async def adm_starostas_menu(call: types.CallbackQuery):
    starostas = load_starostas()
    lines = ["👑 <b>Список назначенных старост:</b>\n"]
    if not starostas:
        lines.append("<i>Старосты пока не назначены.</i>")
    else:
        for sid, grp in starostas.items():
            lines.append(f"• ID: <code>{sid}</code> — Группа: <b>{grp}</b>")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Назначить старосту", callback_data="adm:add_starosta")],
        ]
    )
    await call.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data == "adm:add_starosta", F.from_user.id.in_(ADMIN_IDS))
async def adm_add_starosta_prompt(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.admin_assign_starosta)
    await call.message.answer(
        "Отправьте сообщение формата:\n"
        "<code>Telegram_ID ; Название_Группы</code>\n\n"
        f"Пример:\n<code>123456789 ; {DEFAULT_GROUP}</code>",
        parse_mode="HTML",
    )
    await call.answer()


@dp.message(BotStates.admin_assign_starosta, F.from_user.id.in_(ADMIN_IDS))
async def adm_add_starosta_save(message: types.Message, state: FSMContext):
    parts = [p.strip() for p in message.text.split(";")]
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("Неверный формат. Нужно: <code>ID ; Название_Группы</code>", parse_mode="HTML")
        return

    sid, grp = parts[0], parts[1]
    starostas = load_starostas()
    starostas[sid] = grp
    save_starostas(starostas)

    update_user(int(sid), group=grp)
    try:
        await bot.send_message(
            int(sid),
            f"🎉 Вам выданы права старосты для группы <b>{grp}</b>!",
            reply_markup=get_main_keyboard(int(sid)),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await state.clear()
    await message.answer(f"✅ Пользователь <code>{sid}</code> назначен старостой группы <b>{grp}</b>.", parse_mode="HTML")


@dp.callback_query(F.data == "adm:select_group_to_edit", F.from_user.id.in_(ADMIN_IDS))
async def adm_select_group(call: types.CallbackQuery):
    groups = get_existing_groups()
    rows = []
    row = []
    for g in groups:
        row.append(InlineKeyboardButton(text=g, callback_data=f"edit_group:{g}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    await call.message.edit_text("Выберите группу для редактирования расписания:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data == "adm:export_file", F.from_user.id.in_(ADMIN_IDS))
async def adm_export_file(call: types.CallbackQuery):
    if os.path.exists(SCHEDULE_FILE):
        await call.message.answer_document(types.FSInputFile(SCHEDULE_FILE), caption="Текущая база расписания.")
    await call.answer()


@dp.callback_query(F.data == "adm:broadcast_all", F.from_user.id.in_(ADMIN_IDS))
async def adm_broadcast_all_prompt(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.admin_broadcast)
    await call.message.answer("Введите текст общей рассылки для всех пользователей бота:", parse_mode="HTML")
    await call.answer()


@dp.message(BotStates.admin_broadcast, F.from_user.id.in_(ADMIN_IDS))
async def adm_broadcast_all_send(message: types.Message, state: FSMContext):
    users = load_users()
    count = 0
    for uid in users.keys():
        try:
            await bot.send_message(int(uid), f"📢 <b>Объявление:</b>\n\n{html.escape(message.text)}", parse_mode="HTML")
            count += 1
        except Exception:
            pass
    await state.clear()
    await message.answer(f"✅ Сообщение доставлено {count} пользователям.")


# ==================== РЕДАКТОР ПАР ====================
@dp.callback_query(F.data.startswith("edit_group:"))
async def edit_group_pick_parity(call: types.CallbackQuery):
    group = call.data.split(":")[1]
    uid = call.from_user.id
    if uid not in ADMIN_IDS and is_starosta(uid) != group:
        await call.answer("У вас нет прав для изменения этой группы.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣ Нечётная неделя", callback_data=f"ed_par:{group}:Нечётная"),
                InlineKeyboardButton(text="2️⃣ Чётная неделя", callback_data=f"ed_par:{group}:Чётная"),
            ]
        ]
    )
    await call.message.edit_text(f"Группа: <b>{group}</b>\nВыберите неделю:", reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("ed_par:"))
async def edit_group_pick_day(call: types.CallbackQuery):
    _, group, parity = call.data.split(":")
    rows = []
    for idx, day in enumerate(DAYS_OF_WEEK[:-1]):
        rows.append([InlineKeyboardButton(text=day, callback_data=f"ed_day:{group}:{parity}:{idx}")])
    await call.message.edit_text(
        f"Группа: <b>{group}</b> • <b>{parity} неделя</b>\nВыберите день недели:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("ed_day:"))
async def edit_group_pick_pair(call: types.CallbackQuery):
    _, group, parity, day_idx = call.data.split(":")
    day_name = DAY_INDEX_MAP[int(day_idx)]

    rows = []
    for pair_num in range(1, 8):
        rows.append([
            InlineKeyboardButton(
                text=f"Пара №{pair_num} ({MIREA_TIMES[pair_num]})",
                callback_data=f"ed_pnum:{group}:{parity}:{day_name}:{pair_num}",
            )
        ])
    await call.message.edit_text(
        f"<b>{group} • {parity} неделя • {day_name}</b>\nВыберите пару для изменения:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("ed_pnum:"))
async def edit_pair_input_prompt(call: types.CallbackQuery, state: FSMContext):
    _, group, parity, day_name, pair_num = call.data.split(":")
    await state.set_state(BotStates.editing_pair)
    await state.update_data(group=group, parity=parity, day=day_name, num=int(pair_num))

    await call.message.answer(
        f"Редактирование: <b>{group} • {parity} • {day_name} • Пара №{pair_num}</b>\n\n"
        "Отправьте данные через <b>точку с запятой ( ; )</b>:\n"
        "<code>Предмет ; Тип (ЛК/ПР/ЛАБ) ; Аудитория (Корпус) ; Преподаватель</code>\n\n"
        "Пример:\n"
        "<code>Математический анализ ; ПР ; А-400 (МП-1) ; Богатырева Э.М.</code>\n\n"
        "<i>Если пары не будет — напишите <b>УДАЛИТЬ</b></i>.",
        parse_mode="HTML",
    )
    await call.answer()


@dp.message(BotStates.editing_pair)
async def edit_pair_save(message: types.Message, state: FSMContext):
    data_ctx = await state.get_data()
    group = data_ctx["group"]
    parity = data_ctx["parity"]
    day_name = data_ctx["day"]
    pair_num = data_ctx["num"]

    sched = load_schedule()
    day_list = sched["groups"][group][parity][day_name]
    day_list = [p for p in day_list if p["num"] != pair_num]

    text = message.text.strip()
    if text.lower() != "удалить":
        parts = [p.strip() for p in text.split(";")]
        subject = parts[0] if len(parts) > 0 else "Занятие"
        ltype = parts[1] if len(parts) > 1 else "ПР"
        room = parts[2] if len(parts) > 2 else "Аудитория не указана"
        teacher = parts[3] if len(parts) > 3 else ""

        day_list.append({
            "num": pair_num,
            "time": MIREA_TIMES.get(pair_num, "09:00"),
            "type": ltype,
            "subject": subject,
            "room": room,
            "teacher": teacher,
        })
        day_list.sort(key=lambda x: x["num"])

    sched["groups"][group][parity][day_name] = day_list
    save_schedule(sched)
    await state.clear()

    await message.answer(
        f"✅ Пара №{pair_num} ({day_name}, {group}) сохранена!",
        reply_markup=get_main_keyboard(message.from_user.id),
    )


# Загрузка JSON документа админом
@dp.message(F.document, F.from_user.id.in_(ADMIN_IDS))
async def adm_upload_schedule_doc(message: types.Message):
    if not message.document.file_name.lower().endswith(".json"):
        return
    file_info = await bot.get_file(message.document.file_id)
    raw = io.BytesIO()
    await bot.download_file(file_info.file_path, raw)
    try:
        new_data = json.loads(raw.getvalue().decode("utf-8"))
        if "groups" not in new_data:
            await message.answer("❌ Ошибка: отсутствует корневой ключ 'groups'.")
            return
        save_schedule(new_data)
        await message.answer("✅ База расписания успешно перезаписана из файла!")
    except Exception as err:
        await message.answer(f"❌ Ошибка обработки файла: {err}")


# ==================== РАСПОЗНАВАТЕЛЬ GEMINI (ТОЛЬКО ДЛЯ АДМИНА) ====================
async def call_gemini_vision(images_b64: list[str], prompt_text: str | None) -> str:
    if not GEMINI_API_KEY:
        return "⚠️ Не настроен GEMINI_API_KEY."

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    user_query = prompt_text if prompt_text else "Реши задание или подробно поясни конспект/материал на фото."

    parts = [{"text": user_query}]
    for b64 in images_b64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json={"contents": [{"parts": parts}]}, timeout=aiohttp.ClientTimeout(total=40)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        return candidates[0]["content"]["parts"][0]["text"]
                    return "Ответ пуст."
                return f"Ошибка Google AI ({resp.status})."
    except Exception as e:
        return f"Ошибка сервиса: {e}"


@dp.message(F.text == "📷 Распознаватель", F.from_user.id.in_(ADMIN_IDS))
async def recognizer_btn(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.waiting_for_photo)
    await message.answer("📷 Отправьте фото задания или конспекта с вопросом:", reply_markup=recognizer_kb)


@dp.message(F.text == "❌ Выйти из режима распознавания")
async def exit_recognizer_btn(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Режим распознавания закрыт.", reply_markup=get_main_keyboard(message.from_user.id))


@dp.message(F.photo, F.from_user.id.in_(ADMIN_IDS))
async def handle_photo_input(message: types.Message):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_io = io.BytesIO()
    await bot.download_file(file.file_path, file_io)
    b64_img = base64.b64encode(file_io.getvalue()).decode("utf-8")

    status = await message.answer("🧠 <i>Google AI обрабатывает изображение...</i>", parse_mode="HTML")
    ans = await call_gemini_vision([b64_img], message.caption)
    try:
        await bot.delete_message(message.chat.id, status.message_id)
    except Exception:
        pass

    full_text = f"🔮 <b>Ответ:</b>\n\n{ans}"
    if len(full_text) > 4000:
        for chunk in [full_text[i:i + 3900] for i in range(0, len(full_text), 3900)]:
            await message.answer(chunk)
    else:
        try:
            await message.answer(full_text, parse_mode="HTML")
        except TelegramBadRequest:
            await message.answer(full_text)


# ==================== ТЕСТОВЫЕ КОМАНДЫ ====================
@dp.message(Command(commands=["morning", "test_morning"]))
async def test_morning_cmd(message: types.Message):
    text, kb = await generate_morning_payload(message.from_user.id)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.message(Command(commands=["evening", "test_evening"]))
async def test_evening_cmd(message: types.Message):
    text, kb = await generate_evening_payload(message.from_user.id)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def main():
    load_schedule()
    asyncio.create_task(notifications_worker())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
