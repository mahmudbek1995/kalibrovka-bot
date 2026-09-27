"""
Kalibrovka Telegram Boti va Web App integratsiyasi
X, Y, Z o'qlari bo'yicha proporsional hisob-kitoblar va tahlillar.
Texnologiya: Python 3, aiogram 3.x
"""

import asyncio
import logging
import math
import os
import sys
from typing import Optional

from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# Windows terminalida UTF-8 ni ta'minlash
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import json
from aiohttp import web
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

# -------------------------------------------------------------
# BOT SOZLAMALARI (.env faylidan olinadi)
# -------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
WEB_APP_URL = os.getenv("WEB_APP_URL", "").strip()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------
# FSM HOLATLARI (Bitta aniq natija bilan hisoblash)
# -------------------------------------------------------------
class CalibState(StatesGroup):
    axis = State()
    target = State()
    measured = State()
    current_val = State()


class ScaleState(StatesGroup):
    target = State()
    measured = State()
    current_percent = State()


# -------------------------------------------------------------
# MATEMATIK HISOB-KITOB FUNKSIYALARI
# -------------------------------------------------------------
def calculate_scale_percent(
    target: float,
    measured: float,
    current_percent: float = 100.0
) -> dict:
    """
    100% da chiqqan bitta o'lcham asosida yangi kerakli masshtab foizini hisoblash.
    Formulasi: Yangi_Foiz = Hozirgi_Foiz * (Kutilgan / Chiqqan_olcham)
    """
    delta = measured - target
    percent_delta = (delta / target) * 100.0 if target > 0 else 0.0

    # Yangi masshtab foizi
    new_percent = current_percent * (target / measured) if measured > 0 else current_percent
    percent_change = new_percent - current_percent

    if abs(delta) <= 0.03:
        status_text = "✅ O'lcham mukammal aniq! O'zgartirish shart emas."
        action_advice = f"Masshtabni {current_percent:.1f}% da qoldirishingiz mumkin."
    elif delta < 0:
        status_text = f"⚠️ Kichik chiqdi (-{abs(delta):.2f} mm kam, -{abs(percent_delta):.2f}%)"
        action_advice = (
            f"Model kichraygan. Sliceda model masshtabini {current_percent:.1f}% dan "
            f"<b>{new_percent:.2f}%</b> ga oshiring (+{abs(percent_change):.2f}%)."
        )
    else:
        status_text = f"⚠️ Katta chiqdi (+{delta:.2f} mm ko'p, +{percent_delta:.2f}%)"
        action_advice = (
            f"Model kengaygan. Sliceda model masshtabini {current_percent:.1f}% dan "
            f"<b>{new_percent:.2f}%</b> ga kamaytiring (-{abs(percent_change):.2f}%)."
        )

    return {
        "target": target,
        "measured": measured,
        "delta": delta,
        "percent_delta": percent_delta,
        "current_percent": current_percent,
        "new_percent": new_percent,
        "percent_change": percent_change,
        "status_text": status_text,
        "action_advice": action_advice,
    }


def format_scale_report(res: dict) -> str:
    """Foizli hisoblash hisoboti"""
    sign_delta = "+" if res["delta"] >= 0 else ""
    sign_change = "+" if res["percent_change"] >= 0 else ""

    text = (
        f"🎯 <b>MASSHTAB VA YANGI FOIZ TAHLILI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📐 <b>Biz xohlagan (kutilgan) o'lcham:</b> <code>{res['target']:.2f} mm</code>\n"
        f"📏 <b>Haqiqatda chiqqan natija:</b> <code>{res['measured']:.2f} mm</code>\n"
        f"⚖️ <b>Xatolik (farq):</b> <code>{sign_delta}{res['delta']:.2f} mm ({sign_delta}{res['percent_delta']:.2f}%)</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ <b>Hozirgi masshtab:</b> <code>{res['current_percent']:.1f}%</code>\n"
        f"🚀 <b>KERAKLI YANGI FOIZ:</b> <code>{res['new_percent']:.2f}%</code>\n"
        f"📈 <b>Kerakli tuzatish farqi:</b> <code>{sign_change}{res['percent_change']:.2f}%</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Holat:</b> {res['status_text']}\n"
        f"💡 <b>Tavsiya:</b> {res['action_advice']}\n\n"
        f"<i>Slicer (Cura, Prusa, Bambu Studio) dasturida model o'lchamini <b>{res['new_percent']:.2f}%</b> qilib belgilang.</i>"
    )
    return text


def calculate_calibration(
    axis: str,
    target: float,
    measured: float,
    current_val: float = 80.0
) -> dict:
    """
    O'qlar (X, Y, Z) bo'yicha qadamlarni hisoblash
    """
    delta = measured - target
    percent_delta = (delta / target) * 100.0 if target > 0 else 0.0

    # 100% proporsiyadagi tuzatish koeffitsiyenti
    correction_ratio = (target / measured) if measured > 0 else 1.0
    correction_percent = correction_ratio * 100.0

    # Yangi qadamlar (steps/mm)
    new_val = current_val * correction_ratio

    if abs(delta) <= 0.03:
        status_text = "✅ Mukammal aniqlik"
    elif delta < -0.03:
        status_text = f"⚠️ Kichrayish (-{abs(delta):.2f} mm kam)"
    else:
        status_text = f"⚠️ Kengayish (+{delta:.2f} mm ortiqcha)"

    return {
        "axis": axis.upper(),
        "target": target,
        "measured": measured,
        "delta": delta,
        "percent_delta": percent_delta,
        "correction_ratio": correction_ratio,
        "correction_percent": correction_percent,
        "current_val": current_val,
        "new_val": new_val,
        "status_text": status_text,
    }


def format_report(res: dict) -> str:
    """O'q kalibrovkasi hisoboti"""
    sign = "+" if res["delta"] >= 0 else ""
    axis = res["axis"]
    gcode_cmd = f"M92 {axis}{res['new_val']:.2f}"

    text = (
        f"🎯 <b>{axis} O'QI KALIBROVKA TAHLILI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📐 <b>Kutilgan o'lcham:</b> <code>{res['target']:.2f} mm</code>\n"
        f"📏 <b>O'lchangan natija:</b> <code>{res['measured']:.2f} mm</code>\n"
        f"⚖️ <b>Og'ish (Xatolik):</b> <code>{sign}{res['delta']:.2f} mm ({sign}{res['percent_delta']:.2f}%)</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ <b>Eski qadam (Steps/mm):</b> <code>{res['current_val']:.2f}</code>\n"
        f"🚀 <b>YANGI TAVSIYA ETILGAN QIYMAT:</b> <code>{res['new_val']:.2f}</code>\n"
        f"🔄 <b>Tuzatish koeffitsiyenti:</b> <code>{res['correction_percent']:.2f}%</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Holat:</b> {res['status_text']}\n\n"
        f"💡 <b>Tavsiya etilgan G-Code:</b>\n"
        f"<code>{gcode_cmd}</code>\n"
        f"<code>M500</code> <i>(Xotiraga saqlash)</i>"
    )
    return text


dp = Dispatcher(storage=MemoryStorage())


async def safe_answer(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass


def get_current_web_url() -> str:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("WEB_APP_URL="):
                        url = line.split("=", 1)[1].strip()
                        if url and url.startswith("https://") and "example.com" not in url:
                            return url
        except Exception:
            pass
    url = os.getenv("WEB_APP_URL", "").strip()
    if url and url.startswith("https://") and "example.com" not in url:
        return url
    return ""


def get_main_keyboard():
    web_url = get_current_web_url()
    buttons = [
        [
            InlineKeyboardButton(
                text="🎯 100% dan Yangi Foizni Hisoblash",
                callback_data="scale_calc"
            )
        ]
    ]

    if web_url:
        buttons.append([
            InlineKeyboardButton(
                text="🚀 Web App (Telegram ichida ochish)",
                web_app=WebAppInfo(url=web_url)
            ),
            InlineKeyboardButton(
                text="🌐 Brauzerda ochish",
                url=web_url
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🌐 Veb Sahifani Ochish", callback_data="web_info")
        ])

    buttons.extend([
        [
            InlineKeyboardButton(text="🔵 X O'qi", callback_data="calc_X"),
            InlineKeyboardButton(text="🟢 Y O'qi", callback_data="calc_Y"),
            InlineKeyboardButton(text="🟡 Z O'qi", callback_data="calc_Z"),
        ],
        [
            InlineKeyboardButton(text="🎲 20mm Kubik Testi", callback_data="preset_cube"),
            InlineKeyboardButton(text="ℹ️ Formulalar", callback_data="help_info"),
        ]
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_reply_keyboard():
    web_url = get_current_web_url()
    buttons = []
    if web_url:
        buttons.append([
            KeyboardButton(text="🚀 Web Appni ochish", web_app=WebAppInfo(url=web_url))
        ])
    buttons.append([
        KeyboardButton(text="🎯 Yangi Foiz"),
        KeyboardButton(text="🔵 X o'qi"),
        KeyboardButton(text="🟢 Y o'qi"),
        KeyboardButton(text="🟡 Z o'qi")
    ])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    web_url = get_current_web_url()
    web_status = f"\n🌐 <b>Veb-Ilova:</b> <a href='{web_url}'>{web_url}</a>\n" if web_url else ""

    welcome_text = (
        f"Assalomu alaykum, <b>{message.from_user.first_name}</b>! 👋\n\n"
        f"Ushbu bot <b>3D printer, stanok yoki har qanday o'qlarni (X, Y, Z)</b> "
        f"bitta o'lchangan natija asosida tezkor kalibrovka qilish uchun mo'ljallangan.{web_status}\n"
        f"🎯 <b>Sizga nima kerak?</b>\n"
        f"1. <b>Kutilgan o'lcham</b> (necha mm chiqishi kerak edi)\n"
        f"2. <b>Chiqqan natija</b> (haqiqatda necha mm chiqdi)\n\n"
        f"Bot darhol <b>modelni necha foizga qo'yish kerakligini</b> yoki <b>yangi qadamni (Steps/mm)</b> hisoblab beradi!\n\n"
        f"⚡ <b>Tezkor usul:</b> Botga shunchaki ikkita raqam yuboring:\n"
        f"👉 <code>50 48.5</code> <i>(Kutilgan 50mm, chiqqani 48.5mm)</i>\n"
        f"👉 <code>20 19.8</code> <i>(Kutilgan 20mm, chiqqani 19.8mm)"
    )
    await message.answer(welcome_text, reply_markup=get_reply_keyboard(), parse_mode="HTML")
    await message.answer("👇 <b>Quyidagi menyu orqali boshlashingiz mumkin:</b>", reply_markup=get_main_keyboard(), parse_mode="HTML")


# -------------------------------------------------------------
# VEB SAHIFA BO'YICHA MA'LUMOT
# -------------------------------------------------------------
@dp.callback_query(F.data == "web_info")
async def web_info_callback(callback: types.CallbackQuery):
    web_url = get_current_web_url()
    if web_url:
        info = (
            f"🌐 <b>KALIBROVKA VEB-SAHIFASI FAOL</b>\n\n"
            f"Siz veb-sahifaga quyidagi havola orqali to'g'ridan-to'g'ri kirishingiz mumkin:\n"
            f"👉 <a href='{web_url}'>{web_url}</a>\n\n"
            f"Shuningdek, menyudagi <b>'🚀 Web App'</b> tugmasi orqali to'g'ridan-to'g'ri Telegram ichida ochiladi!"
        )
    else:
        info = (
            "🌐 <b>KALIBROVKA VEB-SAHIFASINI OCHISH</b>\n\n"
            "Serverni internet orqali Telegramga ulash uchun kompyuteringizda:\n"
            "<code>python server.py</code> buyrug'ini ishga tushiring.\n\n"
            "Shunda Telegram orqali kirish uchun xavfsiz HTTPS havola avtomatik yaratiladi va botga ulanadi!"
        )
    await callback.message.answer(info, parse_mode="HTML")
    await safe_answer(callback)


# -------------------------------------------------------------
# FOIZLI MASSHTAB (SCALE %) BOSQICHMA-BOSQICH
# -------------------------------------------------------------
@dp.callback_query(F.data == "scale_calc")
async def start_scale_calc(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ScaleState.target)
    await callback.message.answer(
        "🎯 <b>YANGI FOIZNI HISOBLASH (MASSHTAB)</b>\n\n"
        "1-qadam: Sizga <b>qanday o'lcham kerak edi</b> (kutilgan razmer, mm)?\n"
        "<i>Masalan: 50 yoki 100 yoki 20</i>",
        parse_mode="HTML"
    )
    await safe_answer(callback)


@dp.message(ScaleState.target)
async def process_scale_target(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0:
            raise ValueError
        await state.update_data(target=val)
        await state.set_state(ScaleState.measured)
        await message.answer(
            f"✅ Kutilgan o'lcham: <b>{val:.2f} mm</b>\n\n"
            f"2-qadam: 100% da chop etilganda <b>haqiqatda necha mm chiqdi</b>?\n"
            f"<i>Masalan: 48.50</i>",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Iltimos, musbat son kiriting (masalan: 50 yoki 100):")


@dp.message(ScaleState.measured)
async def process_scale_measured(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0:
            raise ValueError
        await state.update_data(measured=val)
        await state.set_state(ScaleState.current_percent)
        await message.answer(
            f"✅ Chiqqan natija: <b>{val:.2f} mm</b>\n\n"
            f"3-qadam: Hozirgi model masshtabi necha foizda edi?\n"
            f"<i>(Standart holatda shunchaki <b>100</b> deb yuboring)</i>",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri son kiriting (masalan: 48.5):")


@dp.message(ScaleState.current_percent)
async def process_scale_current(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0:
            raise ValueError
        data = await state.get_data()
        await state.clear()

        res = calculate_scale_percent(
            target=data["target"],
            measured=data["measured"],
            current_percent=val
        )
        report = format_scale_report(res)
        await message.answer(report, parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Iltimos, musbat son kiriting (masalan: 100):")


# -------------------------------------------------------------
# O'QLAR (X, Y, Z) KALIBROVKASI BOSQICHMA-BOSQICH
# -------------------------------------------------------------
@dp.callback_query(F.data.startswith("calc_"))
async def start_axis_calc(callback: types.CallbackQuery, state: FSMContext):
    axis = callback.data.split("_")[1]
    await state.update_data(axis=axis)
    await state.set_state(CalibState.target)

    await callback.message.answer(
        f"🎯 <b>{axis} o'qi tanlandi.</b>\n\n"
        f"1-qadam: Chiqishi kerak bo'lgan <b>kutilgan o'lchamni (mm)</b> kiriting:\n"
        f"<i>Masalan: 20 yoki 100</i>",
        parse_mode="HTML"
    )
    await safe_answer(callback)


@dp.message(CalibState.target)
async def process_axis_target(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0:
            raise ValueError
        await state.update_data(target=val)
        await state.set_state(CalibState.measured)
        await message.answer(
            f"✅ Kutilgan o'lcham: <b>{val:.2f} mm</b>\n\n"
            f"2-qadam: O'lchangan <b>natijani (mm)</b> kiriting:\n"
            f"<i>Masalan: 19.85</i>",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Iltimos, musbat son kiriting (masalan: 20 yoki 100):")


@dp.message(CalibState.measured)
async def process_axis_measured(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0:
            raise ValueError
        await state.update_data(measured=val)
        await state.set_state(CalibState.current_val)

        data = await state.get_data()
        default_step = 400.0 if data.get("axis") == "Z" else 80.0

        await message.answer(
            f"✅ O'lchangan natija: <b>{val:.2f} mm</b>\n\n"
            f"3-qadam: Hozirgi kalibrovka qadamini (steps/mm) kiriting:\n"
            f"<i>(Standart: <b>{default_step:.1f}</b> yoki 100)</i>",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri son kiriting (masalan: 19.85):")


@dp.message(CalibState.current_val)
async def process_axis_current_val(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0:
            raise ValueError
        data = await state.get_data()
        await state.clear()

        res = calculate_calibration(
            axis=data["axis"],
            target=data["target"],
            measured=data["measured"],
            current_val=val
        )
        report = format_report(res)
        await message.answer(report, parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Iltimos, musbat son kiriting (masalan: 80 yoki 100):")


# -------------------------------------------------------------
# BUYRUQLAR: /foiz VA /calc
# -------------------------------------------------------------
@dp.message(Command("foiz", "scale"))
async def quick_foiz_cmd(message: types.Message):
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer(
            "⚡ <b>Tezkor foiz hisoblash:</b>\n"
            "<code>/foiz [Kutilgan] [Chiqqan_natija] [Hozirgi_foiz]</code>\n\n"
            "Misol:\n"
            "<code>/foiz 50 48.5</code>\n"
            "<code>/foiz 100 98.4 100</code>",
            parse_mode="HTML"
        )
        return

    try:
        target = float(parts[1].replace(",", "."))
        measured = float(parts[2].replace(",", "."))
        current_p = float(parts[3].replace(",", ".")) if len(parts) >= 4 else 100.0

        res = calculate_scale_percent(target, measured, current_p)
        await message.answer(format_scale_report(res), parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}")


@dp.message(Command("calc"))
async def quick_calc_cmd(message: types.Message):
    parts = message.text.strip().split()
    if len(parts) < 4:
        await message.answer(
            "⚡ <b>Tezkor o'q hisoblash:</b>\n"
            "<code>/calc [O'Q] [Kutilgan] [Chiqqan_natija] [Hozirgi_qadam]</code>\n\n"
            "Misol:\n"
            "<code>/calc X 20 19.85 80</code>\n"
            "<code>/calc Z 20 20.02 400</code>",
            parse_mode="HTML"
        )
        return

    try:
        axis = parts[1].upper()
        target = float(parts[2].replace(",", "."))
        measured = float(parts[3].replace(",", "."))
        current_val = float(parts[4].replace(",", ".")) if len(parts) >= 5 else (400.0 if axis == "Z" else 80.0)

        res = calculate_calibration(axis, target, measured, current_val)
        await message.answer(format_report(res), parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}")


@dp.callback_query(F.data == "preset_cube")
async def preset_cube_calc(callback: types.CallbackQuery):
    res_x = calculate_calibration("X", 20.0, 19.82, 80.0)
    res_y = calculate_calibration("Y", 20.0, 20.14, 80.0)
    res_z = calculate_calibration("Z", 20.0, 20.00, 400.0)

    summary = (
        "🎲 <b>20mm KALIBROVKA KUBIGI MISOLI</b>\n\n"
        f"🔵 <b>X:</b> Kutilgan 20mm ➔ Chiqqan 19.82mm ➔ <b>Yangi: {res_x['new_val']:.2f}</b>\n"
        f"🟢 <b>Y:</b> Kutilgan 20mm ➔ Chiqqan 20.14mm ➔ <b>Yangi: {res_y['new_val']:.2f}</b>\n"
        f"🟡 <b>Z:</b> Kutilgan 20mm ➔ Chiqqan 20.00mm ➔ <b>Yangi: {res_z['new_val']:.2f}</b>\n\n"
        f"⚙️ <b>Birlashtirilgan G-Code:</b>\n"
        f"<code>M92 X{res_x['new_val']:.2f} Y{res_y['new_val']:.2f} Z{res_z['new_val']:.2f}</code>\n"
        f"<code>M500</code>"
    )
    await callback.message.answer(summary, parse_mode="HTML")
    await safe_answer(callback)


@dp.callback_query(F.data == "help_info")
async def help_callback(callback: types.CallbackQuery):
    info_text = (
        "ℹ️ <b>KALIBROVKA FORMULALARI</b>\n\n"
        "1. <b>Yangi Masshtab Foizi:</b>\n"
        "   <code>Yangi_foiz = 100% * (Kutilgan / Chiqqan_natija)</code>\n\n"
        "2. <b>Yangi Steps/mm:</b>\n"
        "   <code>Yangi_qadam = Eski_qadam * (Kutilgan / Chiqqan_natija)</code>\n\n"
        "3. <b>Og'ish (Xatolik):</b>\n"
        "   <code>Delta = Chiqqan_natija - Kutilgan</code>"
    )
    await callback.message.answer(info_text, parse_mode="HTML")
    await safe_answer(callback)


# -------------------------------------------------------------
# WEB APP DAN KELGAN NATIJALARNI QABUL QILISH
# -------------------------------------------------------------
@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        scale = data.get("scale", "-")
        x = data.get("x", "-")
        y = data.get("y", "-")
        z = data.get("z", "-")
        gcode = data.get("gcode", "-")

        text = (
            "📥 <b>Web Appdan yangi natijalar qabul qilindi:</b>\n\n"
            f"🎯 <b>Yangi tavsiya etilgan masshtab:</b> <code>{scale}</code>\n"
            f"🔵 <b>X o'qi yangi qadam:</b> <code>{x}</code>\n"
            f"🟢 <b>Y o'qi yangi qadam:</b> <code>{y}</code>\n"
            f"🟡 <b>Z o'qi yangi qadam:</b> <code>{z}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>Tavsiya etilgan G-Code:</b>\n"
            f"<code>{gcode}</code>\n"
            f"<code>M500</code> <i>(Xotiraga saqlash)</i>"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"✅ Web App natijalari: {message.web_app_data.data}")


# -------------------------------------------------------------
# REPLY KLAVIATURA TUGMALARI ISHLOVCHILARI
# -------------------------------------------------------------
@dp.message(F.text == "🎯 Yangi Foiz")
async def reply_scale_btn(message: types.Message, state: FSMContext):
    await state.set_state(ScaleState.target)
    await message.answer(
        "🎯 <b>100% dan Yangi Foizni Hisoblash</b>\n\n"
        "1️⃣ <b>Modelning asl (kutilgan) o'lchami necha mm edi?</b>\n"
        "<i>(Masalan: 50 yoki 20)</i>",
        parse_mode="HTML"
    )


@dp.message(F.text.in_(["🔵 X o'qi", "🟢 Y o'qi", "🟡 Z o'qi"]))
async def reply_axis_btn(message: types.Message, state: FSMContext):
    axis = "X" if "X" in message.text else ("Y" if "Y" in message.text else "Z")
    await state.update_data(axis=axis)
    await state.set_state(CalibState.target)
    await message.answer(
        f"<b>{message.text} kalibrovkasi</b>\n\n"
        f"1️⃣ <b>Kutilgan o'lcham necha mm?</b>\n<i>(Masalan: 20 yoki 100)</i>",
        parse_mode="HTML"
    )


# -------------------------------------------------------------
# SMART AVTOMATIK MATN TAHLILI
# Masalan, faqat 2 ta raqam: "50 48.5"
# -------------------------------------------------------------
@dp.message()
async def smart_text_handler(message: types.Message):
    if not message.text:
        return
    text = message.text.strip().replace(",", ".")
    parts = text.split()

    try:
        nums = [float(p) for p in parts]
        if len(nums) == 2:
            target, measured = nums
            res = calculate_scale_percent(target, measured)
            await message.answer(
                "💡 <i>Kutilgan o'lcham va chiqqan natija asosida hisoblandi:</i>\n\n"
                + format_scale_report(res),
                parse_mode="HTML"
            )
            return
        elif len(nums) == 3:
            # Agar 3 ta raqam bo'lsa: Kutilgan, Chiqqan, Hozirgi_qadam
            target, measured, cur_val = nums
            res = calculate_calibration("X", target, measured, cur_val)
            await message.answer(
                "💡 <i>O'q bo'yicha qadam hisoblandi:</i>\n\n"
                + format_report(res),
                parse_mode="HTML"
            )
            return
    except ValueError:
        pass

    await start_handler(message)


# -------------------------------------------------------------
# BULUTLI SERVERLAR UCHUN HEALTHCHECK SERVER (KOYEB / RENDER)
# -------------------------------------------------------------
async def start_health_server():
    port_str = os.getenv("PORT", "")
    if not port_str:
        return
    try:
        port = int(port_str)
        app = web.Application()

        async def health_handler(request):
            return web.Response(text="OK - 3D Kalibrovka Boti ishlamoqda! (@KALIBROVA3D_bot)", content_type="text/plain")

        app.router.add_get("/", health_handler)
        app.router.add_get("/health", health_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"✅ Bulutli server HealthCheck (PORT {port}) faollashtirildi!")
    except Exception as e:
        print(f"⚠️ HealthCheck serverida ogohlantirish: {e}")


# -------------------------------------------------------------
# BOTNI ISHGA TUSHIRISH
# -------------------------------------------------------------
async def main():
    if not BOT_TOKEN:
        print("\n" + "=" * 60)
        print("⚠️ DIQQAT: .env faylida BOT_TOKEN topilmadi!")
        print("=" * 60 + "\n")
        return

    # Agar Koyeb / Render kabi serverlarda PORT berilsa, HTTP serverni yoqamiz
    await start_health_server()

    while True:
        try:
            bot = Bot(token=BOT_TOKEN)
            me = await bot.get_me()
            print("\n" + "=" * 60)
            print(f"✅ Bot muvaffaqiyatli ulandi!")
            print(f"🤖 Bot: @{me.username} ({me.first_name})")
            print("=" * 60 + "\n")

            web_url = get_current_web_url()
            if web_url:
                try:
                    await bot.set_chat_menu_button(
                        menu_button=MenuButtonWebApp(
                            text="🚀 Web App",
                            web_app=WebAppInfo(url=web_url)
                        )
                    )
                    print(f"🌐 Telegram Chat Menu Button o'rnatildi: {web_url}")
                except Exception as e:
                    print(f"⚠️ Menu button o'rnatishda xatolik: {e}")

            if ADMIN_ID and ADMIN_ID.isdigit():
                try:
                    await bot.send_message(
                        chat_id=int(ADMIN_ID),
                        text=(
                            f"🚀 <b>Kalibrovka Boti yangilandi va ishga tushdi!</b>\n\n"
                            f"🔹 Endi hisob-kitoblar faqat <b>bitta o'lchangan natija</b> bilan ishlaydi.\n"
                            f"🔹 Masalan shunchaki <code>50 48.5</code> deb yozib yuborishingiz mumkin."
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

            print("🚀 Polling boshlanmoqda... (To'xtatish uchun Ctrl + C)")
            await dp.start_polling(bot, drop_pending_updates=True)
            break
        except Exception as err:
            print(f"⚠️ Telegram serveriga ulanishda vaqtinchalik uzilish: {err}")
            print("3 soniyadan so'ng qayta ulanishga urinilmoqda...")
            await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi.")
