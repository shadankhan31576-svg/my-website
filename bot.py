import os
import re
import time
import json
import logging
import requests
import telebot
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===================== 🔑 BOT TOKEN =====================
BOT_TOKEN = '8825684447:AAGEUFRMV89KrIo8m2WVwk8PqAWNFFksMLs'
DEV_USERNAME = 'MSK0047'
# ========================================================

# ===================== LOGGING =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('error.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===================== STATS =====================
STATS_FILE = 'stats.json'
if not os.path.exists(STATS_FILE):
    with open(STATS_FILE, 'w') as f:
        json.dump({"users": [], "total_requests": 0, "errors": 0}, f)

def update_stats(user_id, error=False):
    try:
        with open(STATS_FILE, 'r') as f:
            stats = json.load(f)
        if user_id not in stats['users']:
            stats['users'].append(user_id)
        stats['total_requests'] += 1
        if error:
            stats['errors'] += 1
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f)
    except:
        pass

# ===================== API ENDPOINTS =====================
NUMBER_API_URL = 'https://movements-invoice-amanda-victoria.trycloudflare.com/search/number'
NUMBER_API_KEY = 'mysecretkey123'
VEHICLE_API_URL = 'https://vehicleinfo-byrack.vercel.app/api'
PINCODE_API_URL = 'https://rack-pincodeapi.vercel.app/api'
IFSC_API_URL = 'https://vercei-kappa.vercel.app/ifsc'
VEHICLE_TO_PHONE_API = 'https://bronx-web-api.onrender.com/api/key-bronx/veh2num'
VEHICLE_TO_PHONE_KEY = 'paid-key-lifetime'
AADHAR_API_URL = 'https://aadhar.ek4nsh.in/'
# =========================================================

# ===================== INIT BOT =====================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
user_states = {}

# ===================== HELPERS =====================

def api_request_with_retry(url, params=None, timeout=15, retries=2):
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            return resp
        except requests.exceptions.Timeout:
            if attempt == retries - 1:
                raise Exception("⏰ सर्वर टाइमआउट (बहुत धीमा)")
            time.sleep(1.5)
        except requests.exceptions.ConnectionError:
            if attempt == retries - 1:
                raise Exception("🌐 कनेक्शन नहीं हो पाया")
            time.sleep(2)
    return None

def clean_dict(data):
    if not data:
        return {}
    return {k: v for k, v in data.items() if v and str(v).strip() not in ['N/A', 'None', '']}

# ---------- Number ----------
def format_number_info(result_list):
    if not result_list:
        return "❌ <b>इस नंबर की कोई जानकारी नहीं मिली</b>"
    parts = []
    for i, entry in enumerate(result_list, 1):
        clean = clean_dict(entry)
        if not clean:
            continue
        text = f"<b>📌 एंट्री {i}</b>\n"
        field_order = [
            ('num', '📱 मोबाइल'),
            ('name', '👤 नाम'),
            ('fname', '👨 पिता का नाम'),
            ('aadhar', '🆔 आधार'),
            ('email', '✉️ ईमेल'),
            ('address', '📍 पता'),
            ('circle', '📡 सर्कल')
        ]
        for key, label in field_order:
            if key in clean and clean[key]:
                text += f"  {label}: <code>{clean[key]}</code>\n"
        parts.append(text.strip())
    if not parts:
        return "❌ <b>डेटा खाली है</b>"
    return "\n\n".join(parts)

# ---------- 🚗 Vehicle ----------
def extract_vehicle_fields(data):
    if not data:
        return {}
    base = data.get('response')
    if not base or not isinstance(base, dict):
        base = data
    merged = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if k != 'response' and v is not None and v != '':
                merged[k] = v
    if isinstance(base, dict):
        for k, v in base.items():
            if v is not None and v != '':
                merged[k] = v
    mapping = {
        'regNo': '🚘 Registration No',
        'owner': '👤 Owner Name',
        'ownerFatherName': '👨 Father Name',
        'regAuthority': '🏛️ RTO Office',
        'regDate': '📅 Registration Date',
        'presentAddress': '🏙️ City',
        'pincode': '📍 PIN Code',
        'vehicle': '🚗 Vehicle',
        'variant': '🏷️ Variant',
        'cubicCapacity': '📐 CC (Engine)',
        'fuelType': '⛽ Fuel Type',
        'seatCapacity': '🧑‍🤝‍🧑 Seating Capacity',
        'manufacturer': '🏭 Manufacturer',
        'manufacturerMonthYear': '📅 Manufacture Date',
        'chassis': '🔢 Chassis Number',
        'engine': '🔧 Engine Number',
        'insuranceCompanyName': '📋 Insurance Company',
        'insuranceUpto': '📅 Insurance Upto',
        'puccNumber': '🧾 PUC Number',
        'pucNumber': '🧾 PUC Number',
        'puccValidUpto': '📅 PUC Valid Upto',
        'pucValidityDate': '📅 PUC Valid Upto',
        'financerName': '🏦 Financer',
    }
    fields = {}
    for key, label in mapping.items():
        value = merged.get(key)
        if value and value != 'N/A' and value != '':
            if key == 'presentAddress' and isinstance(value, str):
                parts = value.split(',')
                if parts:
                    value = parts[0].strip()
            fields[label] = value
    return fields

def format_vehicle_info(data):
    if not data:
        return "❌ <b>API से कोई रिस्पांस नहीं आया</b>"
    if 'error' in data:
        error_msg = data['error']
        if "Invalid" in error_msg:
            return "❌ <b>गलत व्हीकल नंबर!</b>\n\nसही फॉर्मेट: <code>UP14AB1234</code> या <code>RJ14CV0002</code>"
        elif "not found" in error_msg.lower():
            return "❌ <b>व्हीकल नहीं मिला!</b>\n\n🔍 इस नंबर का डेटा RTO डेटाबेस में उपलब्ध नहीं है।"
        else:
            return f"❌ <b>एरर:</b> {error_msg}"
    if data.get('success') == False or data.get('status') == False:
        msg = data.get('message', data.get('error', 'Unknown error'))
        return f"❌ <b>API एरर:</b> {msg}"
    fields = extract_vehicle_fields(data)
    if not fields:
        return "❌ <b>इस व्हीकल नंबर की कोई जानकारी नहीं मिली</b>"
    lines = ["🚗 <b>VEHICLE INFORMATION</b>", "━" * 20, ""]
    for label, value in fields.items():
        if value and value != 'N/A' and value != '':
            lines.append(f"{label}: <code>{value}</code>")
    return "\n".join(lines)

# ---------- Vehicle to Phone ----------
def format_vehicle_to_phone_info(data):
    if not data:
        return "❌ <b>API से कोई रिस्पांस नहीं आया</b>"
    if 'error' in data:
        return f"❌ <b>एरर:</b> {data['error']}"
    if not data.get('success', False):
        msg = data.get('message', 'Unknown error')
        return f"❌ <b>API एरर:</b> {msg}"
    lines = ["🚗 <b>VEHICLE TO PHONE NUMBER</b>", "━" * 20, ""]
    fields = {
        '🚘 Vehicle': data.get('vehicle', 'N/A'),
        '📱 Mobile Number': data.get('mobile_number', 'N/A'),
        '🔢 Chassis Number': data.get('chassis_number', 'N/A'),
        '🔧 Engine Number': data.get('engine_number', 'N/A'),
    }
    for label, value in fields.items():
        if value and value != 'N/A':
            lines.append(f"{label}: <code>{value}</code>")
    return "\n".join(lines)

def get_vehicle_to_phone_info(vehicle_number):
    try:
        params = {'key': VEHICLE_TO_PHONE_KEY, 'vehicle': vehicle_number.strip().upper()}
        resp = requests.get(VEHICLE_TO_PHONE_API, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": f"⚠️ एरर: {str(e)}"}

# ---------- 🆕 Aadhar Search (20 records, no extra waiting message) ----------
def format_aadhar_info(data):
    if not data:
        return "❌ <b>API से कोई रिस्पांस नहीं आया</b>"
    if 'error' in data:
        return f"❌ <b>एरर:</b> {data['error']}"
    count = data.get('count', 0)
    records = data.get('data', [])
    if count == 0 or not records:
        return "❌ <b>इस नाम की कोई रिकॉर्ड नहीं मिली</b>"
    lines = [
        "🆔 <b>AADHAR SEARCH RESULT</b>",
        f"📊 <b>कुल रिकॉर्ड्स:</b> {count}",
        "━" * 20,
        ""
    ]
    for i, rec in enumerate(records[:20], 1):
        lines.append(f"<b>{i}. {rec.get('name', 'N/A')}</b>")
        lines.append(f"  🆔 Aadhar: <code>{rec.get('aadharNumber', 'N/A')}</code>")
        lines.append(f"  📱 Phone: <code>{rec.get('phoneNumber', 'N/A')}</code>")
        lines.append(f"  📍 Address: {rec.get('address', 'N/A')}")
        lines.append(f"  🏙️ District: {rec.get('district', 'N/A')}")
        lines.append(f"  🌍 State: {rec.get('state', 'N/A')}")
        lines.append(f"  🔞 Age: {rec.get('age', 'N/A')}")
        lines.append(f"  ⚥ Gender: {rec.get('gender', 'N/A')}")
        lines.append("")
    if count > 20:
        lines.append(f"📌 ... और {count - 20} रिकॉर्ड्स हैं")
    return "\n".join(lines)

def get_aadhar_info(name):
    try:
        params = {'name': name.strip()}
        resp = requests.get(AADHAR_API_URL, params=params, timeout=30)  # long timeout
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": f"⚠️ एरर: {str(e)}"}

# ---------- Pincode ----------
def format_pincode_info(data):
    if data.get('status') != 'success':
        return "❌ <b>PIN Code नहीं मिला</b>"
    total = data.get('total_records_found', 0)
    records = data.get('records', [])
    pincode = data.get('pincode', 'N/A')
    if not records:
        return f"❌ <b>PIN Code {pincode} के लिए कोई रिकॉर्ड नहीं</b>"
    lines = [
        f"📍 <b>PIN Code: {pincode}</b>",
        f"📊 <b>कुल रिकॉर्ड्स:</b> {total}",
        "",
        "━" * 20,
        ""
    ]
    for i, rec in enumerate(records[:10], 1):
        name = rec.get('office_name', 'N/A')
        branch = rec.get('branch_type', 'N/A')
        delivery = rec.get('delivery_status', 'N/A')
        district = rec.get('district', 'N/A')
        state = rec.get('state', 'N/A')
        circle = rec.get('circle', 'N/A')
        lines.append(
            f"<b>{i}. {name}</b>\n"
            f"  🏢 {branch} | 📬 {delivery}\n"
            f"  📍 {district}, {state}\n"
            f"  🔵 {circle}"
        )
    if total > 10:
        lines.append(f"\n... और {total - 10} रिकॉर्ड्स हैं")
    return "\n".join(lines)

# ---------- IFSC Code ----------
def is_valid_ifsc(ifsc_code):
    return bool(re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_code.upper().strip()))

def format_ifsc_info(data):
    if not data:
        return "❌ <b>API से कोई रिस्पांस नहीं आया</b>"
    if 'error' in data:
        return f"❌ <b>एरर:</b> {data['error']}"
    bank_data = data.get('data', {})
    if not bank_data or bank_data.get('success') == 'false':
        return "❌ <b>IFSC Code नहीं मिला</b>"
    fields = {
        '🏦 Bank': bank_data.get('BANK', 'N/A'),
        '🏛️ Branch': bank_data.get('BRANCH', 'N/A'),
        '📍 Address': bank_data.get('ADDRESS', 'N/A'),
        '🏙️ City': bank_data.get('CITY', 'N/A'),
        '📌 Centre': bank_data.get('CENTRE', 'N/A'),
        '🗺️ District': bank_data.get('DISTRICT', 'N/A'),
        '🌍 State': bank_data.get('STATE', 'N/A'),
        '📮 PIN Code': bank_data.get('PIN', 'N/A'),
        '🔢 IFSC Code': bank_data.get('IFSC', 'N/A'),
        '🔢 MICR Code': bank_data.get('MICR', 'N/A'),
        '📞 Contact': bank_data.get('CONTACT', 'N/A'),
        '📡 Bank Code': bank_data.get('BANKCODE', 'N/A'),
        '✅ NEFT': bank_data.get('NEFT', 'N/A'),
        '✅ RTGS': bank_data.get('RTGS', 'N/A'),
        '✅ UPI': bank_data.get('UPI', 'N/A'),
        '✅ IMPS': bank_data.get('IMPS', 'N/A'),
        '🌐 SWIFT': bank_data.get('SWIFT', 'N/A'),
        '🔗 ISO3166': bank_data.get('ISO3166', 'N/A'),
    }
    lines = ["🏦 <b>IFSC CODE LOOKUP</b>", "━" * 20, ""]
    for label, value in fields.items():
        if value and value != 'N/A' and value != '' and value != 'null':
            if value in ['true', 'True']:
                lines.append(f"{label}: ✅ <b>Yes</b>")
            elif value in ['false', 'False']:
                lines.append(f"{label}: ❌ <b>No</b>")
            else:
                lines.append(f"{label}: <code>{value}</code>")
    return "\n".join(lines)

# ===================== VALIDATIONS =====================

def is_valid_indian_mobile(number):
    return bool(re.match(r'^[6-9]\d{9}$', number.strip()))

def is_valid_vehicle_number(vehicle):
    vehicle = vehicle.strip().upper().replace(' ', '').replace('-', '')
    return bool(re.match(r'^[A-Z]{2}\d{1,2}[A-Z]{0,2}\d{1,4}$', vehicle))

def is_valid_pincode(pincode):
    return bool(re.match(r'^[1-9][0-9]{5}$', pincode.strip()))

def is_valid_name(name):
    return bool(re.match(r'^[A-Za-z\s]{2,50}$', name.strip()))

# ===================== MENUS =====================

def get_main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📞 Num to Info", callback_data="num_info"),
        InlineKeyboardButton("🚗 Vehicle Info", callback_data="vehicle_info"),
        InlineKeyboardButton("📍 PIN Code", callback_data="pincode_info"),
        InlineKeyboardButton("🏦 IFSC Code", callback_data="ifsc_info"),
        InlineKeyboardButton("📱 V to Phone", callback_data="vehicle_to_phone"),
        InlineKeyboardButton("🆔 Aadhar Search", callback_data="aadhar_search")
    )
    return markup

def get_cancel_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_input"),
        InlineKeyboardButton("🔙 मेनू में वापस", callback_data="back_menu")
    )
    return markup

# ===================== COMMANDS =====================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    update_stats(user_id)
    bot.reply_to(
        message,
        "👋 <b>सुपर डिटेक्टिव बॉट</b>\n\n"
        "मैं आपको 6 तरह की जानकारी देता हूँ:\n"
        "1️⃣ <b>📞 नंबर इन्फो</b> – मोबाइल नंबर से नाम, पता, आधार\n"
        "2️⃣ <b>🚗 व्हीकल इन्फो</b> – गाड़ी के नंबर से RTO, मालिक, इंश्योरेंस\n"
        "3️⃣ <b>📍 PIN Code</b> – PIN Code से Post Office, जिला, राज्य\n"
        "4️⃣ <b>🏦 IFSC Code</b> – IFSC Code से बैंक, ब्रांच, पता, MICR, NEFT/RTGS/UPI\n"
        "5️⃣ <b>📱 व्हीकल से फोन नंबर</b> – वाहन नंबर से मालिक का मोबाइल नंबर\n"
        "6️⃣ <b>🆔 आधार सर्च</b> – नाम से आधार नंबर, फोन नंबर, पता (20 रिकॉर्ड्स)\n\n"
        "👇 नीचे दिए गए बटन में से कोई एक चुनें:\n\n"
        "👨‍💻 <b>डेवलपर:</b> <a href='https://t.me/MSK0047'>@MSK0047</a>",
        reply_markup=get_main_menu(),
        disable_web_page_preview=True
    )

@bot.message_handler(commands=['cancel'])
def handle_cancel(message):
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    bot.reply_to(message, "✅ कैंसल कर दिया गया।", reply_markup=get_main_menu())

# ===================== STATS COMMANDS =====================

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.username != DEV_USERNAME:
        bot.reply_to(message, "❌ आपको इस कमांड का उपयोग करने की अनुमति नहीं है।")
        return
    try:
        with open(STATS_FILE, 'r') as f:
            stats = json.load(f)
        lines = [
            "📊 <b>BOT STATISTICS</b>",
            "━" * 20,
            f"👥 Total Users: <code>{len(stats['users'])}</code>",
            f"📥 Total Requests: <code>{stats['total_requests']}</code>",
            f"❌ Total Errors: <code>{stats['errors']}</code>",
            f"📅 Last Updated: <code>{datetime.now().strftime('%d-%m-%Y %H:%M')}</code>"
        ]
        bot.reply_to(message, "\n".join(lines))
    except Exception as e:
        bot.reply_to(message, f"⚠️ एरर: {str(e)}")

@bot.message_handler(commands=['logs'])
def show_logs(message):
    if message.from_user.username != DEV_USERNAME:
        bot.reply_to(message, "❌ आपको इस कमांड का उपयोग करने की अनुमति नहीं है।")
        return
    try:
        with open('error.log', 'r') as f:
            lines = f.readlines()
        last_lines = lines[-20:] if len(lines) > 20 else lines
        if not last_lines:
            bot.reply_to(message, "✅ कोई एरर नहीं मिला।")
            return
        log_text = "📋 <b>Last 20 Errors</b>\n" + "━" * 20 + "\n"
        for line in last_lines:
            log_text += f"{line.strip()}\n"
        if len(log_text) > 4000:
            log_text = log_text[:4000] + "\n... (और एरर्स हैं)"
        bot.reply_to(message, log_text)
    except Exception as e:
        bot.reply_to(message, f"⚠️ एरर: {str(e)}")

# ===================== CALLBACK =====================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    update_stats(user_id)
    if call.data == "cancel_input":
        if user_id in user_states:
            del user_states[user_id]
        bot.edit_message_text("✅ कैंसल कर दिया गया।", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
        return
    if call.data == "back_menu":
        if user_id in user_states:
            del user_states[user_id]
        bot.edit_message_text("🔙 मेनू में वापस आ गए।", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
        return
    if call.data == "num_info":
        user_states[user_id] = {'state': 'waiting_number'}
        bot.edit_message_text("📞 <b>10 अंकों का मोबाइल नंबर डालें</b>\n(जैसे: 9876543210)\n\n⚠️ रद्द करने के लिए /cancel टाइप करें।", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_menu())
    elif call.data == "vehicle_info":
        user_states[user_id] = {'state': 'waiting_vehicle'}
        bot.edit_message_text("🚗 <b>गाड़ी का रजिस्ट्रेशन नंबर डालें</b>\n(जैसे: <code>RJ14CV0002</code> या <code>UP30H5658</code>)\n\n⚠️ रद्द करने के लिए /cancel टाइप करें।", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_menu())
    elif call.data == "pincode_info":
        user_states[user_id] = {'state': 'waiting_pincode'}
        bot.edit_message_text("📍 <b>6 अंकों का PIN Code डालें</b>\n(जैसे: 411001, 110001)\n\n⚠️ रद्द करने के लिए /cancel टाइप करें।", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_menu())
    elif call.data == "ifsc_info":
        user_states[user_id] = {'state': 'waiting_ifsc'}
        bot.edit_message_text("🏦 <b>IFSC Code डालें</b>\n(जैसे: <code>SBIN0001234</code>)\n\n⚠️ रद्द करने के लिए /cancel टाइप करें।", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_menu())
    elif call.data == "vehicle_to_phone":
        user_states[user_id] = {'state': 'waiting_vehicle_to_phone'}
        bot.edit_message_text(
            "📱 <b>वाहन नंबर डालें</b>\n"
            "(जैसे: <code>KL41V3504</code>)\n\n"
            "⚠️ रद्द करने के लिए /cancel टाइप करें।",
            call.message.chat.id, call.message.message_id,
            reply_markup=get_cancel_menu()
        )
    elif call.data == "aadhar_search":
        user_states[user_id] = {'state': 'waiting_aadhar_name'}
        bot.edit_message_text(
            "🆔 <b>नाम डालें</b>\n"
            "(जैसे: <code>Rahul</code> या <code>Sharma</code>)\n\n"
            "📊 20 सबसे पहले रिकॉर्ड्स दिखेंगे।\n"
            "⚠️ रद्द करने के लिए /cancel टाइप करें।",
            call.message.chat.id, call.message.message_id,
            reply_markup=get_cancel_menu()
        )

# ===================== TEXT HANDLER =====================

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    text = message.text.strip()
    update_stats(user_id)
    
    if user_id not in user_states:
        bot.reply_to(message, "❌ पहले /start करें और मेनू से कोई ऑप्शन चुनें।")
        return
    state = user_states[user_id]['state']

    if state == 'waiting_number':
        if not is_valid_indian_mobile(text):
            bot.reply_to(message, "❌ गलत फॉर्मेट! 10 अंक का वैध मोबाइल नंबर डालें (6/7/8/9 से शुरू)।", reply_markup=get_cancel_menu())
            return
        bot.send_chat_action(message.chat.id, 'typing')
        try:
            params = {'number': text, 'key': NUMBER_API_KEY}
            resp = api_request_with_retry(NUMBER_API_URL, params=params, timeout=12)
            if not resp:
                raise Exception("API से कोई रिस्पांस नहीं आया")
            data = resp.json()
            if data.get('status') != 'success' or not data.get('result'):
                result = "❌ इस नंबर का कोई रिकॉर्ड नहीं मिला।"
            else:
                result = format_number_info(data['result'])
            del user_states[user_id]
            bot.reply_to(message, result, reply_markup=get_main_menu())
        except Exception as e:
            logger.error(f"Number Error - User {user_id}: {str(e)}")
            update_stats(user_id, error=True)
            bot.reply_to(message, f"⚠️ एरर: {str(e)}", reply_markup=get_main_menu())
            if user_id in user_states:
                del user_states[user_id]

    elif state == 'waiting_vehicle':
        if not is_valid_vehicle_number(text):
            bot.reply_to(message, "❌ गलत फॉर्मेट! जैसे: <code>RJ14CV0002</code> या <code>UP30H5658</code> डालें।", parse_mode='HTML', reply_markup=get_cancel_menu())
            return
        bot.send_chat_action(message.chat.id, 'typing')
        try:
            params = {'search': text.strip().upper()}
            resp = api_request_with_retry(VEHICLE_API_URL, params=params, timeout=20)
            if not resp:
                raise Exception("API से कोई रिस्पांस नहीं आया")
            data = resp.json()
            result = format_vehicle_info(data)
            del user_states[user_id]
            bot.reply_to(message, result, reply_markup=get_main_menu())
        except Exception as e:
            logger.error(f"Vehicle Error - User {user_id}: {str(e)}")
            update_stats(user_id, error=True)
            bot.reply_to(message, f"⚠️ एरर: {str(e)}", reply_markup=get_main_menu())
            if user_id in user_states:
                del user_states[user_id]

    elif state == 'waiting_pincode':
        if not is_valid_pincode(text):
            bot.reply_to(message, "❌ गलत फॉर्मेट! 6 अंकों का वैध PIN Code डालें (0 से शुरू नहीं)।", reply_markup=get_cancel_menu())
            return
        bot.send_chat_action(message.chat.id, 'typing')
        try:
            params = {'search': text}
            resp = api_request_with_retry(PINCODE_API_URL, params=params, timeout=10)
            if not resp:
                raise Exception("API से कोई रिस्पांस नहीं आया")
            data = resp.json()
            if data.get('status') != 'success':
                result = "❌ PIN Code नहीं मिला या API एरर।"
            else:
                result = format_pincode_info(data)
            del user_states[user_id]
            bot.reply_to(message, result, reply_markup=get_main_menu())
        except Exception as e:
            logger.error(f"Pincode Error - User {user_id}: {str(e)}")
            update_stats(user_id, error=True)
            bot.reply_to(message, f"⚠️ एरर: {str(e)}", reply_markup=get_main_menu())
            if user_id in user_states:
                del user_states[user_id]

    elif state == 'waiting_ifsc':
        if not is_valid_ifsc(text):
            bot.reply_to(
                message,
                "❌ <b>गलत IFSC Code!</b>\n\n"
                "सही फॉर्मेट: 4 अक्षर + 0 + 6 अंक/अक्षर\n"
                "📌 उदाहरण: <code>SBIN0001234</code>",
                reply_markup=get_cancel_menu()
            )
            return
        bot.send_chat_action(message.chat.id, 'typing')
        try:
            params = {'code': text.upper().strip()}
            resp = api_request_with_retry(IFSC_API_URL, params=params, timeout=12)
            if not resp:
                raise Exception("API से कोई रिस्पांस नहीं आया")
            data = resp.json()
            result = format_ifsc_info(data)
            del user_states[user_id]
            bot.reply_to(message, result, reply_markup=get_main_menu())
        except Exception as e:
            logger.error(f"IFSC Error - User {user_id}: {str(e)}")
            update_stats(user_id, error=True)
            bot.reply_to(message, f"⚠️ एरर: {str(e)}", reply_markup=get_main_menu())
            if user_id in user_states:
                del user_states[user_id]

    elif state == 'waiting_vehicle_to_phone':
        if not is_valid_vehicle_number(text):
            bot.reply_to(
                message,
                "❌ गलत फॉर्मेट! जैसे: <code>KL41V3504</code> या <code>UP50P5434</code> डालें।",
                parse_mode='HTML',
                reply_markup=get_cancel_menu()
            )
            return
        bot.send_chat_action(message.chat.id, 'typing')
        try:
            data = get_vehicle_to_phone_info(text)
            result = format_vehicle_to_phone_info(data)
            del user_states[user_id]
            bot.reply_to(message, result, reply_markup=get_main_menu())
        except Exception as e:
            logger.error(f"Vehicle to Phone Error - User {user_id}: {str(e)}")
            update_stats(user_id, error=True)
            bot.reply_to(message, f"⚠️ एरर: {str(e)}", reply_markup=get_main_menu())
            if user_id in user_states:
                del user_states[user_id]

    # ---------- 🆕 Aadhar Search (without waiting message) ----------
    elif state == 'waiting_aadhar_name':
        if not is_valid_name(text):
            bot.reply_to(
                message,
                "❌ <b>गलत नाम!</b>\n\n"
                "कृपया सही नाम डालें (सिर्फ अक्षर और स्पेस)।\n"
                "📌 उदाहरण: <code>Rahul</code> या <code>Sharma</code>",
                reply_markup=get_cancel_menu()
            )
            return
        bot.send_chat_action(message.chat.id, 'typing')
        try:
            data = get_aadhar_info(text)   # timeout 30 seconds internal
            result = format_aadhar_info(data)
            del user_states[user_id]
            bot.reply_to(message, result, reply_markup=get_main_menu())
        except Exception as e:
            logger.error(f"Aadhar Error - User {user_id}: {str(e)}")
            update_stats(user_id, error=True)
            bot.reply_to(message, f"⚠️ एरर: {str(e)}", reply_markup=get_main_menu())
            if user_id in user_states:
                del user_states[user_id]

# ===================== START =====================
if __name__ == '__main__':
    print("🤖 सुपर डिटेक्टिव बॉट (6 फीचर्स) चालू हो रहा है...")
    print(f"📱 Token: {BOT_TOKEN[:10]}... (सुरक्षित)")
    bot.infinity_polling()