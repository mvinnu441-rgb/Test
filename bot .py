import os
import sqlite3
import re
import asyncio
import time
import logging
import socket
import json
import urllib.error
import urllib.parse
import urllib.request
import aiohttp
import zipfile
import shutil
import html
import random
import string
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient, events, Button
from telethon.errors import (
    SessionPasswordNeededError, MessageNotModifiedError, UserNotParticipantError
)
from telethon.errors.rpcerrorlist import QueryIdInvalidError
from telethon.tl import types as tl_types
from telethon.tl.types import KeyboardButtonCallback, KeyboardButtonUrl
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.functions.account import GetPasswordRequest, UpdatePasswordSettingsRequest, GetAuthorizationsRequest

# ================= INITIALIZE LOGGING =================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logging.getLogger('telethon').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def save_env_key(key, val):
    """Update environment variable in memory and persist to .env file."""
    os.environ[key] = val
    if os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                lines = f.readlines()
            new_lines = []
            found = False
            for line in lines:
                if line.strip().startswith(f"{key}="):
                    new_lines.append(f"{key}={val}\n")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"{key}={val}\n")
            with open(".env", "w") as f:
                f.writelines(new_lines)
        except Exception:
            pass

# ================= LOAD ENVIRONMENT VARIABLES FROM .ENV =================
env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_file_path):
    with open(env_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("'").strip('"')
                if k:
                    os.environ[k] = v

def _require_env(name):
    """Secrets are never hardcoded: the bot refuses to start if one is missing."""
    val = os.getenv(name, "").strip()
    if not val:
        raise SystemExit(f"CRITICAL: {name} is missing. Copy .env.example to .env and fill it in.")
    return val

# ================= BASE CONFIGURATIONS (STRICTLY FROM .ENV) =================
API_ID = int(_require_env("TELEGRAM_API_ID"))
API_HASH = _require_env("TELEGRAM_API_HASH")
BOT_TOKEN = _require_env("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(_require_env("ADMIN_ID"))
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip() and x.strip().lstrip("-").isdigit()]
if ADMIN_ID and ADMIN_ID not in ADMIN_IDS:
    ADMIN_IDS.append(ADMIN_ID)

if not BOT_TOKEN:
    raise ValueError("CRITICAL ERROR: TELEGRAM_BOT_TOKEN is missing in .env file! Please set TELEGRAM_BOT_TOKEN in .env.")

ADMIN_LOG_CHANNEL_ID = int(os.getenv("ADMIN_LOG_CHANNEL_ID", "0"))
PUBLIC_LOG_CHANNEL_ID = int(os.getenv("PUBLIC_LOG_CHANNEL_ID", "0"))
LOG_CHANNEL_ID = PUBLIC_LOG_CHANNEL_ID
FORCE_JOIN_ENABLED = os.getenv("FORCE_JOIN_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
CHECK_CHANNELS = [x.strip() for x in os.getenv("CHECK_CHANNELS", "").split(",") if x.strip()]
JOIN_URLS = [x.strip() for x in os.getenv("JOIN_URLS", "").split(",") if x.strip()]

SUPPORT_HANDLE = os.getenv("SUPPORT_HANDLE", "").strip()
SALES_URL = os.getenv("SALES_URL", "").strip()
HELP_URL = os.getenv("HELP_URL", "").strip()
FIXED_2FA_PASSWORD = os.getenv("FIXED_2FA_PASSWORD", "").strip()
YEAR_LOOKUP_BOT = os.getenv("YEAR_LOOKUP_BOT", "TGDNAbot").strip().lstrip("@")
TERMS_URL = os.getenv("TERMS_URL", "").strip()
CWALLET_QR = os.getenv("CWALLET_QR", "").strip()
CWALLET_ID = os.getenv("CWALLET_ID", "").strip()

UPI_MID = os.getenv("UPI_MID", "").strip()
UPI_ID = os.getenv("UPI_ID", "").strip()

LZT_TOKEN = os.getenv("LZT_TOKEN", "").strip()
LZT_BASE_URL = os.getenv("LZT_BASE_URL", "https://prod-api.lzt.market").rstrip("/")
LZT_REQUEST_TIMEOUT = float(os.getenv("LZT_REQUEST_TIMEOUT", "8"))
LZT_STOCK_TIMEOUT = float(os.getenv("LZT_STOCK_TIMEOUT", "12"))
LZT_MAX_RETRIES = int(os.getenv("LZT_MAX_RETRIES", "2"))
LZT_STOCK_RETRIES = int(os.getenv("LZT_STOCK_RETRIES", "1"))
LZT_CACHE_CONCURRENCY = int(os.getenv("LZT_CACHE_CONCURRENCY", "1"))
LZT_CACHE_REFRESH_SECONDS = float(os.getenv("LZT_CACHE_REFRESH_SECONDS", "300"))
LZT_FORCE_IPV4 = os.getenv("LZT_FORCE_IPV4", "1").strip().lower() not in ("0", "false", "no", "off")
LZT_HTTP_FALLBACK = os.getenv("LZT_HTTP_FALLBACK", "1").strip().lower() not in ("0", "false", "no", "off")
LZT_PROXY = os.getenv("LZT_PROXY", "").strip()
LZT_REQUEST_DEBUG = os.getenv("LZT_REQUEST_DEBUG", "1").strip().lower() not in ("0", "false", "no", "off")
LZT_FAST_BUY_RETRIES = int(os.getenv("LZT_FAST_BUY_RETRIES", "5"))
LZT_PRICE_CURRENCY = os.getenv("LZT_PRICE_CURRENCY", "rub").strip().lower() or "rub"
LZT_MIN_REQUEST_INTERVAL = max(0.2, float(os.getenv("LZT_MIN_REQUEST_INTERVAL", "0.25")))
LZT_RATE_LIMIT_COOLDOWN = float(os.getenv("LZT_RATE_LIMIT_COOLDOWN", "30"))
AUTO_CANCEL_SECONDS = int(os.getenv("AUTO_CANCEL_SECONDS", "600"))

PREMIUM_EMOJI_IDS = {
    "store": os.getenv("PREMIUM_EMOJI_STORE", "").strip(),
    "account": os.getenv("PREMIUM_EMOJI_ACCOUNT", "").strip(),
    "balance": os.getenv("PREMIUM_EMOJI_BALANCE", "").strip(),
    "help": os.getenv("PREMIUM_EMOJI_HELP", "").strip(),
    "buy": os.getenv("PREMIUM_EMOJI_BUY", "").strip(),
    "sell": os.getenv("PREMIUM_EMOJI_SELL", "").strip(),
    "topup": os.getenv("PREMIUM_EMOJI_TOPUP", "").strip(),
    "history": os.getenv("PREMIUM_EMOJI_HISTORY", "").strip(),
    "sales": os.getenv("PREMIUM_EMOJI_SALES", "").strip(),
    "admin": os.getenv("PREMIUM_EMOJI_ADMIN", "").strip(),
}

OTP_REGEX = os.getenv("OTP_REGEX", r'\b\d{5}\b').strip()


# ================= UI ICONS & COUNTRY CATALOG =================
P_STORE = "<tg-emoji emoji-id='5920332557466997677'>🏪</tg-emoji>"
P_DOC = "<tg-emoji emoji-id='6039630677182254664'>📂</tg-emoji>"
P_ACC = "<tg-emoji emoji-id='5884366771913233289'>👤</tg-emoji>"
P_CART = "🛍️"
P_CASH = "<tg-emoji emoji-id='5904359114531675993'>💰</tg-emoji>"
P_CARD = "💳"
P_FLAG = "<tg-emoji emoji-id='6041923781696426657'>🏳️</tg-emoji>"
P_CAL = "<tg-emoji emoji-id='5891100675042974129'>📅</tg-emoji>"
P_WARN = "⚠️"
P_OFF = "⛔"
P_YES = "<tg-emoji emoji-id='5938252440926163756'>✅</tg-emoji>"
P_NO = "❌"
P_PHONE = "<tg-emoji emoji-id='6039605143601680423'>📞</tg-emoji>"
P_TIME = "<tg-emoji emoji-id='5983150113483134607'>⏰️</tg-emoji>"
P_GIFT = "<tg-emoji emoji-id='6032644646587338669'>🎁</tg-emoji>"
P_SHIELD = "<tg-emoji emoji-id='6030537007350944596'>🛡</tg-emoji>"
P_BANK = "🏦"
P_ID = "🆔"
P_TADA = "<tg-emoji emoji-id='6041731551845159060'>🎉</tg-emoji>"
P_INR = "₹"
P_SHOP = "<tg-emoji emoji-id='5920332557466997677'>🏪</tg-emoji>"
P_HELP = "<tg-emoji emoji-id='6035305550625902723'>💬</tg-emoji>"


# Country name -> (ISO-2 code, flag). Keep names stable because they are used in
# callback payloads, markup settings, and cache keys.
COUNTRY_CODES = {
    "Argentina": ("AR", "🇦🇷"), "Australia": ("AU", "🇦🇺"), "Austria": ("AT", "🇦🇹"),
    "Bangladesh": ("BD", "🇧🇩"), "Belgium": ("BE", "🇧🇪"), "Brazil": ("BR", "🇧🇷"),
    "Canada": ("CA", "🇨🇦"), "Chile": ("CL", "🇨🇱"), "China": ("CN", "🇨🇳"),
    "Colombia": ("CO", "🇨🇴"), "Egypt": ("EG", "🇪🇬"), "France": ("FR", "🇫🇷"),
    "Germany": ("DE", "🇩🇪"), "Hong Kong": ("HK", "🇭🇰"), "India": ("IN", "🇮🇳"),
    "Indonesia": ("ID", "🇮🇩"), "Iran": ("IR", "🇮🇷"), "Iraq": ("IQ", "🇮🇶"),
    "Italy": ("IT", "🇮🇹"), "Japan": ("JP", "🇯🇵"), "Kazakhstan": ("KZ", "🇰🇿"),
    "Kenya": ("KE", "🇰🇪"), "Malaysia": ("MY", "🇲🇾"), "Mexico": ("MX", "🇲🇽"),
    "Morocco": ("MA", "🇲🇦"), "Nepal": ("NP", "🇳🇵"), "Netherlands": ("NL", "🇳🇱"),
    "Nigeria": ("NG", "🇳🇬"), "Pakistan": ("PK", "🇵🇰"), "Peru": ("PE", "🇵🇪"),
    "Philippines": ("PH", "🇵🇭"), "Poland": ("PL", "🇵🇱"), "Portugal": ("PT", "🇵🇹"),
    "Romania": ("RO", "🇷🇴"), "Russia": ("RU", "🇷🇺"), "Saudi Arabia": ("SA", "🇸🇦"),
    "Singapore": ("SG", "🇸🇬"), "South Africa": ("ZA", "🇿🇦"), "South Korea": ("KR", "🇰🇷"),
    "Spain": ("ES", "🇪🇸"), "Sri Lanka": ("LK", "🇱🇰"), "Thailand": ("TH", "🇹🇭"),
    "Turkey": ("TR", "🇹🇷"), "Ukraine": ("UA", "🇺🇦"), "United Arab Emirates": ("AE", "🇦🇪"),
    "United Kingdom": ("GB", "🇬🇧"), "United States": ("US", "🇺🇸"), "Uzbekistan": ("UZ", "🇺🇿"),
    "Vietnam": ("VN", "🇻🇳"),
}

CALLING_CODES = {
    "Argentina": "54", "Australia": "61", "Austria": "43", "Bangladesh": "880", "Belgium": "32",
    "Brazil": "55", "Canada": "1", "Chile": "56", "China": "86", "Colombia": "57", "Egypt": "20",
    "France": "33", "Germany": "49", "Hong Kong": "852", "India": "91", "Indonesia": "62",
    "Iran": "98", "Iraq": "964", "Italy": "39", "Japan": "81", "Kazakhstan": "7", "Kenya": "254",
    "Malaysia": "60", "Mexico": "52", "Morocco": "212", "Nepal": "977", "Netherlands": "31",
    "Nigeria": "234", "Pakistan": "92", "Peru": "51", "Philippines": "63", "Poland": "48",
    "Portugal": "351", "Romania": "40", "Russia": "7", "Saudi Arabia": "966", "Singapore": "65",
    "South Africa": "27", "South Korea": "82", "Spain": "34", "Sri Lanka": "94", "Thailand": "66",
    "Turkey": "90", "Ukraine": "380", "United Arab Emirates": "971", "United Kingdom": "44",
    "United States": "1", "Uzbekistan": "998", "Vietnam": "84",
}

ADDITIONAL_COUNTRY_DATA = {
    "Afghanistan": ("AF", "🇦🇫", "93"), "Albania": ("AL", "🇦🇱", "355"),
    "Algeria": ("DZ", "🇩🇿", "213"), "Angola": ("AO", "🇦🇴", "244"),
    "Armenia": ("AM", "🇦🇲", "374"), "Azerbaijan": ("AZ", "🇦🇿", "994"),
    "Bahamas": ("BS", "🇧🇸", "1"), "Bahrain": ("BH", "🇧🇭", "973"),
    "Belize": ("BZ", "🇧🇿", "501"), "Botswana": ("BW", "🇧🇼", "267"),
    "Cape Verde": ("CV", "🇨🇻", "238"), "Central African Republic": ("CF", "🇨🇫", "236"),
    "Chad": ("TD", "🇹🇩", "235"), "Comoros": ("KM", "🇰🇲", "269"),
    "Congo": ("CG", "🇨🇬", "242"), "Costa Rica": ("CR", "🇨🇷", "506"),
    "Cuba": ("CU", "🇨🇺", "53"), "Czech Republic": ("CZ", "🇨🇿", "420"),
    "Denmark": ("DK", "🇩🇰", "45"), "Djibouti": ("DJ", "🇩🇯", "253"),
    "Dominica": ("DM", "🇩🇲", "1"), "Dominican Republic": ("DO", "🇩🇴", "1"),
    "Ecuador": ("EC", "🇪🇨", "593"), "El Salvador": ("SV", "🇸🇻", "503"),
    "Estonia": ("EE", "🇪🇪", "372"), "Fiji": ("FJ", "🇫🇯", "679"),
    "Finland": ("FI", "🇫🇮", "358"), "Gabon": ("GA", "🇬🇦", "241"),
    "Georgia": ("GE", "🇬🇪", "995"), "Ghana": ("GH", "🇬🇭", "233"),
    "Greece": ("GR", "🇬🇷", "30"), "Greenland": ("GL", "🇬🇱", "299"),
    "Grenada": ("GD", "🇬🇩", "1"), "Guadeloupe": ("GP", "🇬🇵", "590"),
    "Guam": ("GU", "🇬🇺", "1"), "Guatemala": ("GT", "🇬🇹", "502"),
    "Guyana": ("GY", "🇬🇾", "592"), "Haiti": ("HT", "🇭🇹", "509"),
    "Honduras": ("HN", "🇭🇳", "504"), "Hungary": ("HU", "🇭🇺", "36"),
    "Iceland": ("IS", "🇮🇸", "354"), "Ireland": ("IE", "🇮🇪", "353"),
    "Israel": ("IL", "🇮🇱", "972"), "Ivory Coast": ("CI", "🇨🇮", "225"),
    "Jamaica": ("JM", "🇯🇲", "1"), "Jordan": ("JO", "🇯🇴", "962"),
    "Kiribati": ("KI", "🇰🇮", "686"), "Kuwait": ("KW", "🇰🇼", "965"),
    "Kyrgyzstan": ("KG", "🇰🇬", "996"), "Laos": ("LA", "🇱🇦", "856"),
    "Latvia": ("LV", "🇱🇻", "371"), "Lebanon": ("LB", "🇱🇧", "961"),
    "Lesotho": ("LS", "🇱🇸", "266"), "Libya": ("LY", "🇱🇾", "218"),
    "Lithuania": ("LT", "🇱🇹", "370"), "Luxembourg": ("LU", "🇱🇺", "352"),
    "Macau": ("MO", "🇲🇴", "853"), "Madagascar": ("MG", "🇲🇬", "261"),
    "Malawi": ("MW", "🇲🇼", "265"), "Maldives": ("MV", "🇲🇻", "960"),
    "Malta": ("MT", "🇲🇹", "356"), "Mauritania": ("MR", "🇲🇷", "222"),
    "Mauritius": ("MU", "🇲🇺", "230"), "Moldova": ("MD", "🇲🇩", "373"),
    "Mozambique": ("MZ", "🇲🇿", "258"), "Myanmar": ("MM", "🇲🇲", "95"),
    "New Zealand": ("NZ", "🇳🇿", "64"), "Nicaragua": ("NI", "🇳🇮", "505"),
    "Niger": ("NE", "🇳🇪", "227"), "Norway": ("NO", "🇳🇴", "47"),
    "Oman": ("OM", "🇴🇲", "968"), "Palau": ("PW", "🇵🇼", "680"),
    "Palestine": ("PS", "🇵🇸", "970"), "Panama": ("PA", "🇵🇦", "507"),
    "Papua New Guinea": ("PG", "🇵🇬", "675"), "Paraguay": ("PY", "🇵🇾", "595"),
    "Puerto Rico": ("PR", "🇵🇷", "1787"), "Qatar": ("QA", "🇶🇦", "974"),
    "Samoa": ("WS", "🇼🇸", "685"), "Senegal": ("SN", "🇸🇳", "221"),
    "Serbia": ("RS", "🇷🇸", "381"), "Seychelles": ("SC", "🇸🇨", "248"),
    "Sierra Leone": ("SL", "🇸🇱", "232"), "Slovenia": ("SI", "🇸🇮", "386"),
    "Solomon Islands": ("SB", "🇸🇧", "677"), "Somalia": ("SO", "🇸🇴", "252"),
    "South Sudan": ("SS", "🇸🇸", "211"), "Sudan": ("SD", "🇸🇩", "249"),
    "Suriname": ("SR", "🇸🇷", "597"), "Swaziland": ("SZ", "🇸🇿", "268"),
    "Sweden": ("SE", "🇸🇪", "46"), "Switzerland": ("CH", "🇨🇭", "41"),
    "Syria": ("SY", "🇸🇾", "963"), "Taiwan": ("TW", "🇹🇼", "886"),
    "Tajikistan": ("TJ", "🇹🇯", "992"), "Timor-Leste": ("TL", "🇹🇱", "670"),
    "Togo": ("TG", "🇹🇬", "228"), "Tonga": ("TO", "🇹🇴", "676"),
    "Trinidad and Tobago": ("TT", "🇹🇹", "1"), "Tunisia": ("TN", "🇹🇳", "216"),
    "Turkmenistan": ("TM", "🇹🇲", "993"), "Uganda": ("UG", "🇺🇬", "256"),
    "Uruguay": ("UY", "🇺🇾", "598"), "Vanuatu": ("VU", "🇻🇺", "678"),
    "Yemen": ("YE", "🇾🇪", "967"), "Zambia": ("ZM", "🇿🇲", "260"),
}
for _country_name, (_iso, _flag, _calling) in ADDITIONAL_COUNTRY_DATA.items():
    COUNTRY_CODES.setdefault(_country_name, (_iso, _flag))
    CALLING_CODES.setdefault(_country_name, _calling)

# Extra Server 1 country catalog entries. The third value is a stable button/API
# code used by callbacks; if the market rejects it, lookups fall back to the
# country name automatically.
MORE_SERVER1_COUNTRIES = """
Åland Islands|ALA|🇦🇽|358
American Samoa|ASM|🇦🇸|1
Andorra|AND|🇦🇩|376
Anguilla|AIA|🇦🇮|1
Antarctica|ATA|🇦🇶|672
Antigua and Barbuda|ATG|🇦🇬|1
Aruba|ABW|🇦🇼|297
Bahamas|BHS|🇧🇸|1
Barbados|BRB|🇧🇧|1
Belarus|BLR|🇧🇾|375
Benin|BEN|🇧🇯|229
Bermuda|BMU|🇧🇲|1
Bhutan|BTN|🇧🇹|975
Bolivia|BOL|🇧🇴|591
Bosnia and Herzegovina|BIH|🇧🇦|387
Bouvet Island|BVT|🇧🇻|47
British Indian Ocean Territory|IOT|🇮🇴|246
British Virgin Islands|VGB|🇻🇬|1
Brunei|BRN|🇧🇳|673
Bulgaria|BGR|🇧🇬|359
Burkina Faso|BFA|🇧🇫|226
Burundi|BDI|🇧🇮|257
Cambodia|KHM|🇰🇭|855
Cameroon|CMR|🇨🇲|237
Canary Islands|CNR|🇮🇨|34
Caribbean Netherlands|BES|🇧🇶|599
Cayman Islands|CYM|🇰🇾|1
Congo (DRC)|COD|🇨🇩|243
Cook Islands|COK|🇨🇰|682
Côte d’Ivoire|CIV|🇨🇮|225
Croatia|HRV|🇭🇷|385
Curaçao|CUW|🇨🇼|599
Cyprus|CYP|🇨🇾|357
Czechia|CZE|🇨🇿|420
Equatorial Guinea|GNQ|🇬🇶|240
Eritrea|ERI|🇪🇷|291
Eswatini|SWZ|🇸🇿|268
Ethiopia|ETH|🇪🇹|251
Falkland Islands|FLK|🇫🇰|500
Faroe Islands|FRO|🇫🇴|298
French Guiana|GUF|🇬🇫|594
French Polynesia|PYF|🇵🇫|689
French Southern Territories|ATF|🇹🇫|262
Gambia|GMB|🇬🇲|220
Gibraltar|GIB|🇬🇮|350
Guernsey|GGY|🇬🇬|44
Guinea|GIN|🇬🇳|224
Guinea-Bissau|GNB|🇬🇼|245
Heard Island and McDonald Islands|HMD|🇭🇲|672
Isle of Man|IMN|🇮🇲|44
Jersey|JEY|🇯🇪|44
Kosovo|XKX|🇽🇰|383
Liberia|LBR|🇱🇷|231
Liechtenstein|LIE|🇱🇮|423
Mali|MLI|🇲🇱|223
Marshall Islands|MHL|🇲🇭|692
Martinique|MTQ|🇲🇶|596
Mayotte|MYT|🇾🇹|262
Micronesia|FSM|🇫🇲|691
Monaco|MCO|🇲🇨|377
Mongolia|MNG|🇲🇳|976
Montenegro|MNE|🇲🇪|382
Montserrat|MSR|🇲🇸|1
Namibia|NAM|🇳🇦|264
Nauru|NRU|🇳🇷|674
New Caledonia|NCL|🇳🇨|687
Niue|NIU|🇳🇺|683
Norfolk Island|NFK|🇳🇫|672
North Korea|PRK|🇰🇵|850
North Macedonia|MKD|🇲🇰|389
Northern Mariana Islands|MNP|🇲🇵|1
Pitcairn Islands|PCN|🇵🇳|64
Réunion|REU|🇷🇪|262
Rwanda|RWA|🇷🇼|250
Saint Barthélemy|BLM|🇧🇱|590
Saint Helena|SHN|🇸🇭|290
Saint Kitts and Nevis|KNA|🇰🇳|1
Saint Lucia|LCA|🇱🇨|1
Saint Martin|MAF|🇲🇫|590
Saint Pierre and Miquelon|SPM|🇵🇲|508
Saint Vincent and the Grenadines|VCT|🇻🇨|1
San Marino|SMR|🇸🇲|378
São Tomé and Príncipe|STP|🇸🇹|239
Sint Maarten|SXM|🇸🇽|1
Slovakia|SVK|🇸🇰|421
South Georgia and South Sandwich Islands|SGS|🇬🇸|500
Svalbard and Jan Mayen|SJM|🇸🇯|47
Tanzania|TZA|🇹🇿|255
Tokelau|TKL|🇹🇰|690
Turks and Caicos Islands|TCA|🇹🇨|1
Tuvalu|TUV|🇹🇻|688
Vatican City|VAT|🇻🇦|379
Venezuela|VEN|🇻🇪|58
U.S. Virgin Islands|VIR|🇻🇮|1
Wallis and Futuna|WLF|🇼🇫|681
Western Sahara|ESH|🇪🇭|212
Zimbabwe|ZWE|🇿🇼|263
"""
for _line in MORE_SERVER1_COUNTRIES.strip().splitlines():
    _name, _code, _flag, _calling = _line.split("|")
    COUNTRY_CODES.setdefault(_name, (_code, _flag))
    CALLING_CODES.setdefault(_name, _calling)

class ConversationCancelled(Exception):
    pass

# ================= TELETHON CLIENT & DB INSTANTIATION =================
session_name = f"bot_session_{BOT_TOKEN.split(':')[0]}"
bot = TelegramClient(session_name, API_ID, API_HASH)
bot.parse_mode = 'html'

db = sqlite3.connect("otp_bot_final.db", check_same_thread=False, timeout=20)
db.execute("PRAGMA journal_mode=WAL;")
db.execute("PRAGMA busy_timeout=20000;")
db.execute("PRAGMA foreign_keys=ON;")
cur = db.cursor()

# ================= GLOBAL TRACKING DICTIONARIES =================
active_orders = {}
deposit_input = {}
admin_dep_state = {}
user_spam_cooldown = {}
session_buy_state = {}
wd_state = {}
sell_state = {}
user_locks = {}
user_filters = {}
manual_dep_state = {}
deposit_media_messages = {}
promo_state = {}
selling_accounts = {}
cached_lzt_stock = {}
active_filter_keys = {"no_no_any_any_any"}
active_fights = {}
active_giveaways = {}
error_cooldowns = {}
lzt_search_state = {}
lookup_search_state = {}
lookup_action_state = {}
active_lzt_purchases = {}
restore_state = {}
giveaway_ticket_state = {}
_lzt_missing_logged = False
_lzt_session = None
_lzt_rate_lock = asyncio.Lock()
_lzt_last_request_at = 0.0
_lzt_blocked_until = 0.0

# ================= STABLE CORE HELPER FUNCTIONS =================
def p_btn(text, data=None, url=None, style=None, icon_custom_emoji_id=None):
    kwargs = {}
    if style:
        kwargs["style"] = style
    if icon_custom_emoji_id:
        kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id
    if url:
        try:
            return Button.url(text, url, **kwargs)
        except TypeError:
            return Button.url(text, url)
    try:
        return Button.inline(text, data, **kwargs)
    except TypeError:
        return Button.inline(text, data)

def premium_emoji_id(name):
    value = PREMIUM_EMOJI_IDS.get(name, "")
    return int(value) if str(value).isdigit() else None

def premium_button(text, data=None, url=None, style=None, emoji_name=None):
    return p_btn(text, data=data, url=url, style=style, icon_custom_emoji_id=premium_emoji_id(emoji_name or ""))

def apply_custom_emoji_entities(text, markers):
    """Replace marker tokens with fallback emoji and return UTF-16 based entities."""
    entities = []
    rendered = text
    custom_emoji_entity = getattr(tl_types, "MessageEntityCustomEmoji", None)
    for marker, fallback, emoji_name in markers:
        custom_id = premium_emoji_id(emoji_name)
        search_from = 0
        while marker in rendered[search_from:]:
            idx = rendered.index(marker, search_from)
            before = rendered[:idx]
            rendered = rendered[:idx] + fallback + rendered[idx + len(marker):]
            if custom_id and custom_emoji_entity:
                offset = len(before.encode("utf-16-le")) // 2
                length = len(fallback.encode("utf-16-le")) // 2
                entities.append(custom_emoji_entity(offset=offset, length=length, document_id=custom_id))
            search_from = idx + len(fallback)
    return rendered, entities

async def safe_show_rich_message(e, text, buttons=None, entities=None, link_preview=False):
    if not entities:
        return await safe_show_message(e, text, buttons=buttons, link_preview=link_preview)
    if is_callback_event(e) and hasattr(e, "edit"):
        try:
            return await e.edit(text, buttons=buttons, formatting_entities=entities, link_preview=link_preview)
        except TypeError:
            return await safe_show_message(e, text, buttons=buttons, link_preview=link_preview)
        except MessageNotModifiedError:
            return None
    try:
        return await e.respond(text, buttons=buttons, formatting_entities=entities, link_preview=link_preview)
    except TypeError:
        return await safe_show_message(e, text, buttons=buttons, link_preview=link_preview)

def get_user_lock(uid):
    if uid not in user_locks:
        user_locks[uid] = asyncio.Lock()
    return user_locks[uid]

def get_user_filters(uid):
    default = {"spam": "no", "geoblock": "no", "offline": "any", "login_mail": "any", "premium": "any", "sort": "az"}
    if uid not in user_filters:
        user_filters[uid] = default.copy()
    else:
        for key, value in default.items():
            user_filters[uid].setdefault(key, value)
    return user_filters[uid]

def get_filter_key(flt):
    return "_".join(str(flt.get(k, "any")) for k in ("spam", "geoblock", "offline", "login_mail", "premium"))

def as_boolish(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value not in (0, -1)
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")

def lzt_item_matches_filters(item, flt):
    spam_pref = flt.get("spam", "any")
    if spam_pref != "any":
        spam_value = item.get("telegram_spam_block", item.get("spam", -1))
        has_spam = str(spam_value) not in ("-1", "0", "False", "false", "None", "")
        if spam_pref == "no" and has_spam:
            return False
        if spam_pref == "yes" and not has_spam:
            return False

    premium_pref = flt.get("premium", "any")
    if premium_pref != "any":
        has_premium = as_boolish(item.get("telegram_premium", item.get("premium")))
        if premium_pref == "yes" and not has_premium:
            return False
        if premium_pref == "no" and has_premium:
            return False

    geo_pref = flt.get("geoblock", "any")
    if geo_pref != "any":
        geo_value = item.get("telegram_geo_block", item.get("geo_block", item.get("geoblock")))
        has_geo = as_boolish(geo_value)
        if geo_pref == "no" and has_geo:
            return False
        if geo_pref == "yes" and not has_geo:
            return False

    mail_pref = flt.get("login_mail", "any")
    if mail_pref != "any":
        mail_value = item.get("login_mail", item.get("email", item.get("has_email", item.get("telegram_email"))))
        has_mail = as_boolish(mail_value)
        if mail_pref == "yes" and not has_mail:
            return False
        if mail_pref == "no" and has_mail:
            return False

    return True

def filter_lzt_items(items, flt):
    return [item for item in items if lzt_item_matches_filters(item, flt)]

def lzt_price_currency(item):
    if isinstance(item, dict):
        for key in ("currency", "price_currency", "priceCurrency", "currency_code", "currencyCode"):
            value = item.get(key)
            if value:
                return str(value).strip().lower()
        price_data = item.get("price_data") or item.get("priceData")
        if isinstance(price_data, dict):
            for key in ("currency", "currency_code", "currencyCode"):
                value = price_data.get(key)
                if value:
                    return str(value).strip().lower()
    return LZT_PRICE_CURRENCY

def lzt_currency_to_inr_rate(currency):
    currency = str(currency or LZT_PRICE_CURRENCY).strip().lower()
    if currency == "usd":
        return get_usdt_rate()
    rate_defaults = {
        "rub": 1.05,
        "eur": 100.0,
        "gbp": 118.0,
        "cny": 13.0,
        "uah": 2.3,
        "kzt": 0.2,
        "byn": 29.0,
        "try": 2.9,
        "jpy": 0.62,
        "brl": 17.0,
    }
    return get_rate(f"{currency}_inr_rate", rate_defaults.get(currency, 1.05))

def lzt_currency_params(extra=None):
    params = dict(extra or {})
    params.setdefault("currency", LZT_PRICE_CURRENCY)
    return params

def lzt_price_breakdown(item, markup_percent):
    raw_price = item.get("price_with_fee") or item.get("priceWithSellerFee") or item.get("price") or 0
    try:
        market_price = float(raw_price)
    except (TypeError, ValueError):
        market_price = 0.0
    currency = lzt_price_currency(item)
    inr_base = market_price * lzt_currency_to_inr_rate(currency)
    try:
        markup_percent = int(float(markup_percent))
    except (TypeError, ValueError):
        markup_percent = 20
    markup_amount = max(0, int(round(inr_base * (markup_percent / 100))))
    base_price = max(0, int(round(inr_base)))
    final_price = max(1, base_price + markup_amount)
    return {
        "market_price": market_price,
        "currency": currency.upper(),
        "base_inr": base_price,
        "markup_percent": markup_percent,
        "markup_inr": markup_amount,
        "final_inr": final_price,
    }

def lzt_final_inr_price(item, markup_percent):
    return lzt_price_breakdown(item, markup_percent)["final_inr"]

def get_lzt_markup(country_name):
    candidates = [country_name]
    if country_name in COUNTRY_CODES:
        iso = COUNTRY_CODES[country_name][0]
        candidates.extend([iso, iso.upper(), get_country_button_code(country_name)])
    row = None
    for candidate in dict.fromkeys(candidates):
        row = cur.execute("SELECT markup_percent FROM lzt_settings WHERE LOWER(country)=LOWER(?)", (candidate,)).fetchone()
        if row:
            break
    if not row:
        row = cur.execute("SELECT value FROM settings WHERE key='lzt_global_markup'").fetchone()
    try:
        return int(float(row[0])) if row else 20
    except (TypeError, ValueError):
        return 20

def clear_lzt_cache():
    cached_lzt_stock.clear()

def build_country_markup_buttons(page=1, per_page=20):
    countries = sorted(COUNTRY_CODES.keys())
    total_pages = max(1, (len(countries) + per_page - 1) // per_page)
    page = min(max(1, int(page)), total_pages)
    start = (page - 1) * per_page
    buttons, row = [], []
    for name in countries[start:start + per_page]:
        markup = get_lzt_markup(name)
        row.append(p_btn(f"{country_button_label(name, include_phone=False)} {markup}%", f"adm_cmark|{COUNTRY_CODES[name][0]}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    nav = []
    if page > 1:
        nav.append(p_btn("⬅ Prev", f"adm_cmarkpg|{page-1}"))
    if page < total_pages:
        nav.append(p_btn("Next ➡", f"adm_cmarkpg|{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([p_btn("Back", "adm_lztset")])
    return buttons, page, total_pages

def lzt_candidate_timestamp(container):
    if not isinstance(container, dict):
        return 0
    for key in ("date", "time", "created_at", "createdDate", "timestamp"):
        value = container.get(key)
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return 0

def collect_lzt_otp_candidates(value, parent_key="", candidates=None, depth=0):
    """Collect OTP candidates from LZT response without matching phones/dates.

    LZT can return codes as top-level fields, nested data/result dictionaries, or
    as a `codes` list like: {"codes": [{"code": "48492", "date": ...}]}.
    This walker only scans trusted OTP/message fields, so large item payloads do
    not accidentally turn phone numbers, Telegram IDs, or dates into OTPs.
    """
    if candidates is None:
        candidates = []
    if value is None or depth > 8:
        return candidates

    trusted_keys = {"code", "otp", "login_code", "telegram_login_code", "telegramLoginCode"}
    text_keys = {"message", "text", "sms", "telegram_message"}
    container_keys = {"data", "item", "telegram", "response", "result", "codes"}
    key_name = str(parent_key or "")

    if isinstance(value, dict):
        ts = lzt_candidate_timestamp(value)
        for key, nested in value.items():
            key_str = str(key)
            if key_str in trusted_keys or key_str in text_keys:
                before = len(candidates)
                collect_lzt_otp_candidates(nested, key_str, candidates, depth + 1)
                if ts:
                    for pos in range(before, len(candidates)):
                        code_ts, priority, code = candidates[pos]
                        if code_ts == 0:
                            candidates[pos] = (ts, priority, code)
            elif key_str in container_keys:
                collect_lzt_otp_candidates(nested, key_str, candidates, depth + 1)
        return candidates

    if isinstance(value, (list, tuple)):
        if key_name in container_keys or key_name in trusted_keys or key_name in text_keys:
            for index, item in enumerate(value):
                before = len(candidates)
                collect_lzt_otp_candidates(item, key_name, candidates, depth + 1)
                # Preserve API order as a weak freshness signal if no date exists.
                for pos in range(before, len(candidates)):
                    ts, priority, code = candidates[pos]
                    if ts == 0:
                        candidates[pos] = (index + 1, priority, code)
        return candidates

    if key_name not in trusted_keys and key_name not in text_keys and key_name != "codes":
        return candidates

    text_val = str(value)
    if "login detected" in text_val.lower():
        return candidates
    match = re.search(OTP_REGEX, text_val)
    if match:
        priority = 100 if key_name in trusted_keys else 50
        candidates.append((0, priority, match.group(0)))
    return candidates

def extract_lzt_otp(res):
    candidates = collect_lzt_otp_candidates(res)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]

async def get_verified_lzt_otp(item_id, attempts=3, delay=1.5):
    """Fetch Server 1 OTP more than once and always return a found code.

    A code seen twice is marked verified. If the market only returns it once
    before a transient error/rate-limit, the bot still returns that latest code
    instead of hiding it from the buyer.
    """
    seen = []
    last_response = None
    for _ in range(max(1, attempts)):
        res = await lzt_request('GET', f"/{item_id}/telegram-login-code", notify_errors=False, return_error=True)
        last_response = res
        code = extract_lzt_otp(res)
        if code:
            seen.append(code)
            if seen.count(code) >= 2 or attempts == 1:
                return code, True, res
        await asyncio.sleep(delay)
    return (seen[-1], False, last_response) if seen else (None, False, last_response)


def lzt_purchase_has_error(res):
    if not res:
        return True
    if not isinstance(res, dict):
        return False
    for key in ("error", "errors", "error_description"):
        value = res.get(key)
        if value:
            return True
    return False

def lzt_purchase_item_id(res, fallback_item_id):
    if isinstance(res, dict):
        item = res.get("item") or res.get("account") or res.get("telegram")
        if isinstance(item, dict):
            return str(item.get("item_id") or item.get("id") or fallback_item_id)
        for key in ("item_id", "id"):
            if res.get(key):
                return str(res.get(key))
    return str(fallback_item_id)

def normalize_lzt_phone(raw_phone, fallback_item_id):
    phone = str(raw_phone or "").strip()
    if not phone or phone.startswith("LZT_"):
        return f"Hidden-{fallback_item_id}"
    compact = phone.replace(" ", "")
    return f"+{compact.lstrip('+')}" if compact.lstrip("+").isdigit() else phone

async def try_lzt_reset_authorizations(item_id):
    # Auto-reset disabled per admin configuration
    return False

def lzt_market_price(item):
    if not isinstance(item, dict):
        return None
    raw_price = item.get("price_with_fee") or item.get("priceWithSellerFee") or item.get("price")
    try:
        price = float(raw_price)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None

def lzt_item_requires_password(item):
    if not isinstance(item, dict):
        return False
    password_keys = (
        "password", "login_password", "telegram_password", "telegram_login_password",
        "has_password", "hasPassword", "twofa", "two_fa", "2fa"
    )
    for key in password_keys:
        value = item.get(key)
        if value in (None, "", 0, "0", False, "None", "none", "no", "NO"):
            continue
        return True
    return False

def lzt_item_country_name(item, fallback=None):
    if isinstance(item, dict):
        for key in ("country", "telegram_country", "country_name", "countryName"):
            value = item.get(key)
            if value:
                value = str(value).strip()
                for name, (iso, _flag) in COUNTRY_CODES.items():
                    if value.lower() in (name.lower(), iso.lower()):
                        return name
                matches = find_country_matches(value)
                if matches:
                    return matches[0]
        phone = item.get("phone") or item.get("telegram_phone") or item.get("login")
        if phone:
            return get_country_info(str(phone))[0]
    return fallback or "Unknown"

def lzt_updated_market_price_from_error(res):
    text = lzt_error_text(res)
    match = re.search(r"costs now\s+([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except (TypeError, ValueError):
            return None
    return None

def lzt_error_text(res):
    if not isinstance(res, dict):
        return str(res or "")
    parts = []
    for key in ("error", "errors", "error_description", "message", "detail"):
        value = res.get(key)
        if value:
            parts.append(str(value))
    return " | ".join(parts)

def lzt_should_retry_purchase(res):
    text = lzt_error_text(res).lower()
    return "retry_request" in text or "retry request" in text

async def lzt_fast_buy_item(item_id, market_price):
    current_price = market_price
    last_res = None
    for attempt in range(1, max(1, LZT_FAST_BUY_RETRIES) + 1):
        body = {"price": current_price} if current_price is not None else None
        last_res = await lzt_request('POST', f"/{item_id}/fast-buy", params=lzt_currency_params(), data=body, return_error=True, notify_errors=False)
        if last_res and not lzt_purchase_has_error(last_res):
            return last_res

        updated_price = lzt_updated_market_price_from_error(last_res)
        if updated_price and updated_price > 0:
            current_price = updated_price
            await asyncio.sleep(0.5)
            continue

        if not lzt_should_retry_purchase(last_res):
            return last_res
        await asyncio.sleep(min(3, 0.5 + (attempt * 0.1)))
    return last_res

def is_private_event(e):
    chat_id = getattr(e, "chat_id", None)
    sender_id = getattr(e, "sender_id", None)
    if chat_id is None or sender_id is None:
        return True
    return int(chat_id) == int(sender_id)

def is_admin_callback_data(data):
    admin_prefixes = (
        "dep_act|", "kp_adm|", "wd_act|", "adm_", "adm",
        "apset|", "sp|", "price|", "pay_", "toggle_"
    )
    return str(data or "").startswith(admin_prefixes)

def callback_allowed_in_chat(uid, data, e):
    if is_private_event(e):
        return True
    return is_admin(uid) and is_admin_callback_data(data)

def mask_phone_number(phone):
    raw = str(phone or "").strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return "Hidden"
    if len(digits) <= 4:
        return "+" + "*" * len(digits)
    if len(digits) <= 8:
        return "+" + digits[:2] + "**" + digits[-2:]
    return "+" + digits[:4] + "**" + digits[-3:]

async def get_user_log_label(uid):
    try:
        ent = await bot.get_entity(uid)
        username = f"@{ent.username}" if getattr(ent, "username", None) else "No username"
        name = html.escape((getattr(ent, "first_name", None) or str(uid)).strip())
        return f"{name} ({username}) | <code>{uid}</code>"
    except Exception:
        return f"<code>{uid}</code>"

async def send_log_message(text, channel_id=PUBLIC_LOG_CHANNEL_ID, label="Log"):
    if not channel_id:
        return
    try:
        await bot.send_message(channel_id, text)
    except Exception as log_ex:
        logger.warning(f"{label} channel send failed (ID: {channel_id}): {log_ex}")

async def send_dual_log(admin_text, public_text):
    await send_log_message(admin_text, ADMIN_LOG_CHANNEL_ID, "Admin log")
    await send_log_message(public_text, PUBLIC_LOG_CHANNEL_ID, "Public log")

async def log_primary_deposit(uid, amount, method):
    logger.info("Deposit credited: user=%s amount=%s method=%s", uid, amount, method)
    user_label = await get_user_log_label(uid)
    public_text = (
        "🚀 <b>New Deposit Success</b>\n\n"
        f"<b>Amount:</b> ₹{amount}\n"
        f"<b>Payment Method:</b> {html.escape(str(method))}\n\n"
        "Thanks For Deposit"
    )
    admin_text = (
        "🚀 <b>New Deposit Success</b>\n\n"
        f"<b>User:</b> {user_label}\n"
        f"<b>Amount:</b> ₹{amount}\n"
        f"<b>Payment Method:</b> {html.escape(str(method))}\n\n"
        "Thanks For Deposit"
    )
    await send_dual_log(admin_text, public_text)

async def log_primary_purchase(uid, country, price, paid, year, qty, phone=None, server=None):
    logger.info("Purchase completed: user=%s country=%s price=%s paid=%s year=%s qty=%s phone=%s server=%s", uid, country, price, paid, year, qty, phone, server)
    user_label = await get_user_log_label(uid)
    public_text = (
        "📅 <b>New Purchase Success</b>\n\n"
        f"<b>Amount:</b> {qty}\n"
        f"<b>Price:</b> ₹{price}\n"
        f"<b>Country:</b> {html.escape(str(country or 'Unknown'))}\n"
        f"<b>Number:</b> <code>{mask_phone_number(phone)}</code>\n"
        f"<b>Server:</b> {html.escape(str(server or 'Unknown'))}\n\n"
        "Thanks for Purchase @FFI1PBOT 🔄"
    )
    admin_text = (
        "📅 <b>New Purchase Success</b>\n\n"
        f"<b>User:</b> {user_label}\n"
        f"<b>Amount:</b> {qty}\n"
        f"<b>Price:</b> ₹{price}\n"
        f"<b>Country:</b> {html.escape(str(country or 'Unknown'))}\n"
        f"<b>Number:</b> <code>{mask_phone_number(phone)}</code>\n"
        f"<b>Server:</b> {html.escape(str(server or 'Unknown'))}\n\n"
        "Thanks for Purchase"
    )
    await send_dual_log(admin_text, public_text)

async def send_main_menu(e, uid):
    ensure_user(uid)
    bal_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    bal = bal_row[0] if bal_row else 0
    support_handle = (SUPPORT_HANDLE or "Support")
    msg_template = ("{store} TG-Store - Buy and Sell Accounts {store}\n\n"
                    "{account} Your account ID | " + str(uid) + "\n"
                    "{balance} Total balance | " + format_price(uid, bal) + "\n"
                    "{help_icon} Help | " + support_handle)
    msg, entities = apply_custom_emoji_entities(msg_template, [
        ("{store}", P_STORE, "store"),
        ("{account}", P_ACC, "account"),
        ("{balance}", P_CASH, "balance"),
        ("{help_icon}", "✆", "help"),
    ])
    btns = [
        [premium_button("Buy Account", "menu_buy", style="success", emoji_name="buy"), premium_button("Sell Account", "menu_sell", style="success", emoji_name="sell")],
        [premium_button("TopUp Balance", "menu_deposit", style="danger", emoji_name="topup")],
        [premium_button("Account", "menu_account", style="primary", emoji_name="account"), premium_button("History", "menu_history", style="primary", emoji_name="history")],
        [b for b in [premium_button("⫶☰ Sales", url=SALES_URL, style="primary", emoji_name="sales") if SALES_URL else None, premium_button("✆ Help", url=HELP_URL, style="primary", emoji_name="help") if HELP_URL else None] if b is not None],
    ]
    btns = [r for r in btns if r]
    if is_admin(uid):
        btns.append([premium_button("Admin Dashboard", "adm_adminmain", emoji_name="admin")])
    return await safe_show_rich_message(e, msg, buttons=btns, entities=entities)

async def send_terms_or_main_menu(e, uid):
    cur.execute("UPDATE users SET terms_accepted=1 WHERE user_id=?", (uid,))
    db.commit()
    res = await send_main_menu(e, uid)
    await ensure_reply_keyboard(uid)
    return res


def country_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

def find_country_by_slug(slug):
    normalized = slug.strip().lower().replace("_", "-")
    for name in COUNTRY_CODES:
        if country_slug(name) == normalized:
            return name
    matches = find_country_matches(normalized.replace("-", " "))
    return matches[0] if matches else None

def get_country_button_code(name):
    special = {"India": "IND"}
    if name in special:
        return special[name]
    return COUNTRY_CODES.get(name, ("", ""))[0] or name[:3].upper()

def country_button_label(name, price_text=None, include_phone=True):
    iso_code, flag = COUNTRY_CODES.get(name, ("", "🌍"))
    short_name = get_country_button_code(name)
    calling = CALLING_CODES.get(name, "")
    parts = [flag, short_name]
    if include_phone and calling:
        parts.append(f"+{calling}")
    label = " ".join(parts)
    if price_text is not None:
        label = f"{label} | {price_text}"
    return label

def find_country_matches(query):
    q = query.strip().lower().replace("+", "")
    if not q:
        return []
    exact, partial = [], []
    for name, (iso, flag) in COUNTRY_CODES.items():
        calling = CALLING_CODES.get(name, "")
        tokens = {name.lower(), iso.lower(), calling.lower()}
        if q in tokens or (q.isdigit() and calling.startswith(q)):
            exact.append(name)
        elif q in name.lower() or iso.lower().startswith(q) or (q.isdigit() and q in calling):
            partial.append(name)
    return sorted(dict.fromkeys(exact + partial))

async def render_server1_country_page(e, uid, page):
    if not resolve_lzt_token():
        if is_admin(uid):
            await bot.send_message(uid, f"{P_WARN} <b>Server 1 token missing.</b>\nPlease set token first.", buttons=[[p_btn("Set Token", "adm_setlzttoken")]])
        return await safe_answer_cb(e, "Server 1 credentials missing. Please notify admin.", alert=True)
    if not is_server1_online():
        return await safe_answer_cb(e, "Server 1 is under maintenance!", alert=True)

    limit = 20
    flt = get_user_filters(uid)
    fkey = get_filter_key(flt)
    active_filter_keys.add(fkey)
    stock_dict = cached_lzt_stock.get(fkey, cached_lzt_stock.get("no_no_any_any_any", {}))

    sorted_countries = sorted(COUNTRY_CODES.keys())
    sort_mode = flt.get("sort", "az")
    if sort_mode == "stock_high":
        sorted_countries.sort(key=lambda n: (stock_dict.get(n, (0, 0))[0], n), reverse=True)
    elif sort_mode == "stock_low":
        sorted_countries.sort(key=lambda n: (stock_dict.get(n, (0, 0))[0], n))
    elif sort_mode == "price_low":
        sorted_countries.sort(key=lambda n: (stock_dict.get(n, (0, 0))[1] or 10**9, n))
    elif sort_mode == "price_high":
        sorted_countries.sort(key=lambda n: (stock_dict.get(n, (0, 0))[1], n), reverse=True)

    total = len(sorted_countries)
    total_pages = max(1, (total + limit - 1) // limit)
    page = min(max(1, page), total_pages)
    offset = (page - 1) * limit
    page_countries = sorted_countries[offset:offset + limit]
    total_bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]

    me = await bot.get_me()
    all_link = f"https://t.me/{me.username}?start=AllServer1"
    msg = (f"<b>Click country to view price and stock:</b>\n"
           f"––––––––––––————––•\n"
           f"✅ Total balance: {format_price(uid, total_bal)} \n"
           f"✅ Server: Server (1)\n"
           f"✅ Page {page} of {total_pages}\n"
           f'✅ View all <a href="{all_link}">countries</a>\n'
           f"➖➖➖➖➖➖➖➖➖➖")

    sort_labels = {"az": "A-Z", "stock_high": "Stock High-Low", "stock_low": "Stock Low-High", "price_low": "Price Low-High", "price_high": "Price High-Low"}
    btns, row = [[p_btn("⚙️ Filters", "lzt_toggle_filters", style="primary"), p_btn(f"↕️ {sort_labels.get(sort_mode, 'A-Z')}", "lzt_sort_menu", style="primary")]], []
    for name in page_countries:
        iso_code, flag = COUNTRY_CODES[name]
        ccode = CALLING_CODES.get(name, "")
        count, min_p = stock_dict.get(name, (0, 0.0))
        price_part = format_price(uid, min_p) if count else "0"
        label = country_button_label(name, price_part)
        row.append(p_btn(label, f"lzt_chk|{iso_code}|1"))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)

    page_row = []
    window_start = max(1, min(page - 2, total_pages - 4))
    window_end = min(total_pages, window_start + 4)
    for pg in range(window_start, window_end + 1):
        text = f"[{pg}]" if pg != page else f"·{pg}·"
        page_row.append(p_btn(text, f"srv_1_pg|{pg}"))
    if page_row:
        btns.append(page_row)

    btns.append([p_btn("⛶ Show All", "lzt_all_countries", style="danger"), p_btn("ᯤ Search", "lzt_search_country", style="danger")])
    btns.append([p_btn("Back", "menu_buy")])
    await safe_show_message(e, msg, buttons=btns)

def is_bot_online():
    row = cur.execute("SELECT value FROM settings WHERE key='bot_status'").fetchone()
    return row[0] == 'on' if row else True

def is_server1_online():
    row = cur.execute("SELECT value FROM settings WHERE key='server1_status'").fetchone()
    return row[0] == 'on' if row else True

def is_method_on(key, default='on'):
    row = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return (row[0] if row and row[0] else default) == 'on'

def is_admin(uid):
    return uid == ADMIN_ID or uid in ADMIN_IDS or bool(cur.execute("SELECT user_id FROM admins WHERE user_id=?", (uid,)).fetchone())

VALID_PERMS = {"p_add_stock", "p_manage_stock", "p_stats", "p_bal", "p_settings"}

def has_perm(uid, perm):
    if uid == ADMIN_ID or uid in ADMIN_IDS: return True
    if perm not in VALID_PERMS:
        return False
    row = cur.execute(f"SELECT {perm} FROM admins WHERE user_id=?", (uid,)).fetchone()
    return bool(row and row[0] == 1)

def is_user_banned(uid):
    row = cur.execute("SELECT banned FROM users WHERE user_id=?", (uid,)).fetchone()
    return bool(row and row[0] == 1)

def ensure_user(uid, username=None, first_name=None):
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    if username or first_name:
        if username:
            cur.execute("UPDATE users SET username=? WHERE user_id=?", (str(username).lstrip("@"), uid))
        if first_name:
            cur.execute("UPDATE users SET first_name=? WHERE user_id=?", (str(first_name), uid))
    db.commit()

def get_usdt_rate():
    try: return float(cur.execute("SELECT value FROM settings WHERE key='usdt_rate'").fetchone()[0])
    except: return 94.0

def get_rate(key, default):
    try:
        row = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return float(row[0]) if row and row[0] else float(default)
    except:
        return float(default)

def get_currency_pref(uid):
    row = cur.execute("SELECT pref_curr FROM users WHERE user_id=?", (uid,)).fetchone()
    pref = (row[0] if row and row[0] else "INR").upper()
    if pref == "USD":
        pref = "USDT"
    return pref if pref in ("INR", "USDT") else "INR"

def format_inr_amount(inr_amt):
    try:
        amount = float(inr_amt)
    except (TypeError, ValueError):
        amount = 0.0
    return f"₹{amount:.0f}" if amount.is_integer() else f"₹{amount:.2f}"

def format_usdt_amount(inr_amt, suffix=" USDT"):
    try:
        rate = get_usdt_rate()
        usdt = float(inr_amt) / rate if rate > 0 else 0.0
    except (TypeError, ValueError, ZeroDivisionError):
        usdt = 0.0
    return f"{usdt:.2f}{suffix}"

def format_compact_usdt(inr_amt):
    try:
        rate = get_usdt_rate()
        usdt = float(inr_amt) / rate if rate > 0 else 0.0
    except (TypeError, ValueError, ZeroDivisionError):
        usdt = 0.0
    formatted = f"{usdt:.2f}".rstrip("0").rstrip(".")
    if not formatted:
        formatted = "0"
    return f"{formatted} USDT"

def format_usd_amount(inr_amt, suffix=" USDT"):
    return format_usdt_amount(inr_amt, suffix)

def format_compact_usd(inr_amt):
    return format_compact_usdt(inr_amt)

def format_price(uid, inr_amt):
    pref = get_currency_pref(uid)
    if pref == "USDT":
        return format_compact_usdt(inr_amt)
    return format_inr_amount(inr_amt)

def parse_db_datetime(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(str(value), fmt)
        except (TypeError, ValueError):
            continue
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None

def format_purchase_datetime(value):
    parsed = parse_db_datetime(value)
    if not parsed:
        return str(value)
    if parsed.date() == datetime.now(timezone.utc).date():
        return f"Today {parsed.strftime('%H:%M:%S')} UTC"
    return parsed.strftime("%a %b %d %H:%M:%S %Y")

def update_balance(uid, amount, bal_type="balance"):
    if bal_type not in ("balance", "sales_balance"):
        raise ValueError(f"Invalid balance type: {bal_type}")
    cur.execute(f"UPDATE users SET {bal_type} = {bal_type} + ? WHERE user_id=?", (amount, uid))
    db.commit()

def get_support_url():
    res = cur.execute("SELECT value FROM settings WHERE key='support_url'").fetchone()
    url = res[0] if res and res[0] else (HELP_URL or "https://t.me/telegram")
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        if url.startswith("@"):
            url = "https://t.me/" + url[1:]
        elif "t.me/" in url:
            url = "https://" + url.lstrip("/")
        else:
            url = "https://t.me/" + url
    return url

def generate_random_password(length=12):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

def delete_session_files(session_path):
    base = session_path if not session_path.endswith('.session') else session_path[:-8]
    for ext in ['.session', '.session-wal', '.session-shm', '.session-journal']:
        try:
            if os.path.exists(base + ext): os.remove(base + ext)
        except: pass

async def check_channel_joined(uid):
    if is_admin(uid): return True
    if not FORCE_JOIN_ENABLED: return True
    if not CHECK_CHANNELS or CHECK_CHANNELS == [""]: return True
    for ch in CHECK_CHANNELS:
        ch_str = str(ch).strip()
        if not ch_str: continue
        try:
            entity = await bot.get_entity(int(ch_str) if ch_str.lstrip('-').isdigit() else ch_str)
            await bot(GetParticipantRequest(channel=entity, participant=uid))
        except UserNotParticipantError:
            return False
        except Exception as ex:
            logger.debug(f"Channel join check fail-safe bypass: {ex}")
            return True
    return True

def get_flag_by_country_name(name):
    if name in COUNTRY_CODES:
        return COUNTRY_CODES[name][1]
    try:
        row = cur.execute("SELECT flag FROM custom_countries WHERE name=?", (name,)).fetchone()
        if row: return row[0]
    except: pass
    return "🌍"

def get_country_info(phone):
    phone = str(phone).replace(' ', '').replace('+', '')
    if not phone: return "Unknown", "🌍", "0"
    try:
        customs = cur.execute("SELECT code, name, flag FROM custom_countries").fetchall()
        customs.sort(key=lambda x: len(str(x[0])), reverse=True)
        for code, name, flag in customs:
            if phone.startswith(str(code)): return name, flag, str(code)
    except: pass
    known = sorted(CALLING_CODES.items(), key=lambda x: len(x[1]), reverse=True)
    for name, code in known:
        if phone.startswith(code):
            return name, COUNTRY_CODES.get(name, ("", "🌍"))[1], code
    return "Unknown", "🌍", "0"

async def detect_account_year(client):
    try:
        await client.send_message(YEAR_LOOKUP_BOT, '/start')
        me = await client.get_me()
        await asyncio.sleep(1)
        await client.send_message(YEAR_LOOKUP_BOT, str(me.id))
        for _ in range(8):
            await asyncio.sleep(1.5)
            msgs = await client.get_messages(YEAR_LOOKUP_BOT, limit=3)
            for m in msgs:
                if m.text and 'Created:' in m.text: return int(re.search(r'Created:[^\d]*(\d{4})', m.text, re.IGNORECASE).group(1))
    except: pass
    return 2024

async def send_admin_error(error_msg: str, trace: str = ""):
    global error_cooldowns
    try:
        sig = f"{error_msg}_{trace[:100]}"
        now = time.time()
        if sig in error_cooldowns:
            if now - error_cooldowns[sig] < 600:
                return
        error_cooldowns[sig] = now

        clean_trace = trace[:1500]
        alert = (f"🚨 <b>SYSTEM EXCEPTION ENCOUNTERED</b>\n\n"
                 f"<b>Error:</b> {html.escape(error_msg)}\n"
                 f"<b>Trace:</b>\n<pre>{html.escape(clean_trace)}</pre>")
        await bot.send_message(ADMIN_ID, alert)
    except Exception as ex:
        logger.error(f"Error logging admin message: {ex}")

async def safe_answer_cb(e, text=None, alert=False):
    try:
        await e.answer(text, alert=alert)
    except QueryIdInvalidError:
        pass
    except Exception as ex:
        logger.debug(f"Redundant cb exception: {ex}")

def is_callback_event(e):
    return getattr(e, "data", None) is not None

async def safe_show_message(e, text, buttons=None, link_preview=False):
    """Edit callback messages, but respond to normal /start messages.

    Telethon new-message events also expose an edit() method for the user's
    command message; editing that incoming message raises EditMessageRequest
    errors. This helper keeps /start flows on respond() and callback flows on
    edit().
    """
    if is_callback_event(e) and hasattr(e, "edit"):
        try:
            return await e.edit(text, buttons=buttons, link_preview=link_preview)
        except TypeError:
            return await e.edit(text, buttons=buttons)
        except MessageNotModifiedError:
            return None
    try:
        return await e.respond(text, buttons=buttons, link_preview=link_preview)
    except TypeError:
        return await e.respond(text, buttons=buttons)

# ================= 360° USER LOOKUP & DIAGNOSTICS =================
async def get_user_display_name(uid):
    """Returns formatted string with User ID and Username, e.g. 5719136023 (@SeedUchiha)."""
    if not uid: return "Unknown"
    row = cur.execute("SELECT username, first_name FROM users WHERE user_id=?", (uid,)).fetchone()
    username = row[0] if row and row[0] else ""
    first_name = row[1] if row and row[1] else ""
    if not username:
        try:
            entity = await bot.get_entity(int(uid))
            username = getattr(entity, "username", "") or ""
            first_name = getattr(entity, "first_name", "") or ""
            if username or first_name:
                cur.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", (str(username).lstrip("@"), str(first_name), uid))
                db.commit()
        except Exception:
            pass
    
    user_link = f"@{username}" if username else "N/A"
    return f"<code>{uid}</code> ({user_link})"

async def resolve_user_360(query):
    """Smart multi-field user resolver matching ID, @username, phone, order ID, or UTR."""
    query_str = str(query).strip()
    if not query_str:
        return None, "Empty search query"

    # 1. Direct numeric User ID lookup
    if query_str.isdigit():
        uid = int(query_str)
        u = cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if u:
            cols = [col[0] for col in cur.description]
            return dict(zip(cols, u)), None

    # 2. Username lookup (with or without @)
    clean_user = query_str.lstrip("@").strip()
    if clean_user:
        u = cur.execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?)", (clean_user,)).fetchone()
        if u:
            cols = [col[0] for col in cur.description]
            return dict(zip(cols, u)), None

    # 3. Order phone number search
    phone_clean = re.sub(r"[^\d]", "", query_str)
    if phone_clean and len(phone_clean) >= 7:
        ord_row = cur.execute("SELECT user_id FROM orders WHERE phone LIKE ? LIMIT 1", (f"%{phone_clean}%",)).fetchone()
        if ord_row and ord_row[0]:
            u = cur.execute("SELECT * FROM users WHERE user_id=?", (ord_row[0],)).fetchone()
            if u:
                cols = [col[0] for col in cur.description]
                return dict(zip(cols, u)), None

    # 4. Deposit Order ID or UTR search
    dep_row = cur.execute("SELECT user_id FROM upi_orders WHERE order_id=? LIMIT 1", (query_str,)).fetchone()
    if dep_row and dep_row[0]:
        u = cur.execute("SELECT * FROM users WHERE user_id=?", (dep_row[0],)).fetchone()
        if u:
            cols = [col[0] for col in cur.description]
            return dict(zip(cols, u)), None

    # 5. First name substring search
    u = cur.execute("SELECT * FROM users WHERE LOWER(first_name) LIKE LOWER(?) LIMIT 1", (f"%{clean_user}%",)).fetchone()
    if u:
        cols = [col[0] for col in cur.description]
        return dict(zip(cols, u)), None

    return None, f"No user or record found matching '<code>{html.escape(query_str)}</code>'."

async def perform_360_user_lookup(e, admin_uid, target_query):
    """Renders 360-degree user profile card with complete diagnostics and action controls."""
    user_row, err_msg = await resolve_user_360(target_query)
    if not user_row:
        return await safe_show_message(e, f"❌ {err_msg}", buttons=[[p_btn("Try Again", "adm_lookup", style="primary"), p_btn("Admin Dashboard", "adm_adminmain", style="danger")]])
    
    t_uid = user_row["user_id"]
    username = user_row.get("username") or ""
    first_name = user_row.get("first_name") or ""
    if not username:
        try:
            entity = await bot.get_entity(int(t_uid))
            username = getattr(entity, "username", "") or ""
            first_name = getattr(entity, "first_name", "") or ""
            if username or first_name:
                cur.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", (str(username).lstrip("@"), str(first_name), t_uid))
                db.commit()
        except Exception:
            pass

    user_link = f"@{username}" if username else "N/A"
    
    bal = user_row.get("balance", 0)
    usdt_rate = get_usdt_rate()
    bal_usd = bal / usdt_rate if usdt_rate > 0 else 0.0
    
    is_master = t_uid == ADMIN_ID or t_uid in ADMIN_IDS
    is_subadmin = bool(cur.execute("SELECT user_id FROM admins WHERE user_id=?", (t_uid,)).fetchone())
    role_badge = "👑 Master Admin" if is_master else ("🛠 Sub-Admin" if is_subadmin else "👤 Regular User")
    
    is_banned = is_user_banned(t_uid)
    status_str = "🔴 BANNED" if is_banned else "🟢 ACTIVE"
    
    # Financial aggregate queries
    dep_row = cur.execute("SELECT SUM(amount), COUNT(*) FROM deposits WHERE user_id=? AND status='success'", (t_uid,)).fetchone()
    upi_dep = cur.execute("SELECT SUM(amount), COUNT(*) FROM upi_orders WHERE user_id=? AND status='success'", (t_uid,)).fetchone()
    total_dep = (dep_row[0] or 0) + (upi_dep[0] or 0)
    total_dep_cnt = (dep_row[1] or 0) + (upi_dep[1] or 0)
    
    ord_row = cur.execute("SELECT COUNT(*), SUM(price) FROM orders WHERE user_id=?", (t_uid,)).fetchone()
    total_orders_cnt = ord_row[0] or 0
    total_spent = ord_row[1] or 0
    
    ref_row = cur.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (t_uid,)).fetchone()
    total_refs = ref_row[0] if ref_row else 0
    
    ref_by = user_row.get("referred_by")
    ref_by_str = await get_user_display_name(ref_by) if ref_by else "None"
    
    # Recent 5 Orders
    recent_orders = cur.execute("SELECT country, year, price, phone, date FROM orders WHERE user_id=? ORDER BY date DESC LIMIT 5", (t_uid,)).fetchall()
    ord_txt = ""
    for c, y, p, ph, dt in recent_orders:
        ord_txt += f"• 📦 <code>{str(dt)[:16] if dt else '?'}</code> | {c} ({y}) | ₹{p}\n   📱 <code>{ph}</code>\n"
    if not ord_txt: ord_txt = "No orders found.\n"
    
    # Recent 5 Recharges
    recent_deps = cur.execute("SELECT amount, method_name, status, date FROM deposits WHERE user_id=? ORDER BY date DESC LIMIT 5", (t_uid,)).fetchall()
    dep_txt = ""
    for a, m, s, dt in recent_deps:
        st_icon = "🟢" if s == 'success' else ("🔴" if s == 'rejected' else "🟡")
        dep_txt += f"• {st_icon} <code>{str(dt)[:16] if dt else '?'}</code> | {m} ₹{a} | {str(s).upper()}\n"
    if not dep_txt: dep_txt = "No deposits found.\n"
    
    msg = (f"👤 <b>USER 360° PROFILE & DIAGNOSTICS</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"🆔 <b>User ID:</b> <code>{t_uid}</code>\n"
           f"👤 <b>Name:</b> <b>{html.escape(first_name or 'Unknown')}</b> ({user_link})\n"
           f"🔰 <b>Role:</b> {role_badge}\n"
           f"📅 <b>Joined:</b> {user_row.get('joined_date', 'N/A')}\n"
           f"🚫 <b>Status:</b> {status_str}\n"
           f"━━━━━━━━━━━━━━━━━━━━\n\n"
           f"💰 <b>FINANCIAL SUMMARY</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"💳 <b>Active Balance:</b> <b>₹{bal}</b> (~${bal_usd:.2f} USDT)\n"
           f"📥 <b>Total Deposited:</b> <b>₹{total_dep}</b> ({total_dep_cnt} deposits)\n"
           f"📤 <b>Total Spent:</b> <b>₹{total_spent}</b> ({total_orders_cnt} orders)\n"
           f"━━━━━━━━━━━━━━━━━━━━\n\n"
           f"👥 <b>REFERRAL NETWORK</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"🔗 <b>Referred By:</b> {ref_by_str}\n"
           f"👥 <b>Direct Referrals:</b> <b>{total_refs}</b> users\n"
           f"━━━━━━━━━━━━━━━━━━━━\n\n"
           f"📦 <b>RECENT ORDERS (Last 5)</b>\n{ord_txt.strip()}\n\n"
           f"💳 <b>RECENT RECHARGES (Last 5)</b>\n{dep_txt.strip()}")
    
    btns = [
        [p_btn("🔴 Ban User" if not is_banned else "🟢 Unban User", f"lka_ban|{t_uid}", style="danger" if not is_banned else "success"),
         p_btn("💸 Add Balance", f"lka_bal|add|{t_uid}", style="success")],
        [p_btn("💳 Deduct Balance", f"lka_bal|ded|{t_uid}", style="danger"),
         p_btn("💬 Send Message", f"lka_msg|{t_uid}", style="primary")],
        [p_btn("📦 View All Orders", f"lka_ords|{t_uid}|1", style="primary"),
         p_btn("💳 Recharges Log", f"lka_deps|{t_uid}|1", style="primary")],
        [p_btn("👥 Referrals List", f"lka_refs|{t_uid}|1", style="primary"),
         p_btn("🔄 Refresh Profile", f"lka_ref|{t_uid}", style="primary")],
        [p_btn("⬅️ Back to Admin", "adm_adminmain", style="danger")]
    ]
    await safe_show_message(e, msg, buttons=btns)

async def render_user_profile(e, uid):
    """Renders user profile card with complete financial metrics, referral statistics, and color-coded action buttons."""
    ensure_user(uid)
    row = cur.execute("SELECT balance, sales_balance, total_deposited, joined_date, referred_by, username, first_name FROM users WHERE user_id=?", (uid,)).fetchone()
    if not row:
        bal, s_bal, dep, date_str, ref_by, uname, f_name = 0, 0, 0, "N/A", None, "", ""
    else:
        bal, s_bal, dep, date_str, ref_by, uname, f_name = row
    
    if not uname:
        try:
            sender = getattr(e, "sender", None)
            if sender:
                uname = getattr(sender, "username", "") or ""
                f_name = getattr(sender, "first_name", "") or ""
            if not uname:
                entity = await bot.get_entity(int(uid))
                uname = getattr(entity, "username", "") or ""
                f_name = getattr(entity, "first_name", "") or ""
            if uname or f_name:
                cur.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", (str(uname).lstrip("@"), str(f_name), uid))
                db.commit()
        except Exception:
            pass

    user_link = f"@{uname}" if uname else "N/A"
    me = await bot.get_me()
    bot_username = me.username if me else "Acccheckbot"
    
    ord_summary = cur.execute("SELECT COUNT(*), SUM(price) FROM orders WHERE user_id=?", (uid,)).fetchone()
    total_accs = ord_summary[0] if ord_summary else 0
    total_spent = ord_summary[1] if ord_summary and ord_summary[1] else 0
    
    ref_count = cur.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,)).fetchone()[0]
    ref_by_disp = await get_user_display_name(ref_by) if ref_by else "None"
    
    is_master = uid == ADMIN_ID or uid in ADMIN_IDS
    is_subadmin = bool(cur.execute("SELECT user_id FROM admins WHERE user_id=?", (uid,)).fetchone())
    role_badge = "👑 Master Admin" if is_master else ("🛠 Sub-Admin" if is_subadmin else "👤 Verified Member")
    
    usdt_rate = get_usdt_rate()
    bal_usdt = bal / usdt_rate if usdt_rate > 0 else 0.0
    
    ref_pct = cur.execute("SELECT value FROM settings WHERE key='ref_percent'").fetchone()
    ref_bonus_rate = ref_pct[0] if ref_pct else "3"
    
    msg = (f"👤 <b>USER PROFILE & ACCOUNT CONTROL</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
           f"👤 <b>Name:</b> <b>{html.escape(f_name or 'Member')}</b> ({user_link})\n"
           f"🔰 <b>Role:</b> {role_badge}\n"
           f"📅 <b>Joined:</b> {str(date_str)[:10] if date_str else 'N/A'}\n"
           f"━━━━━━━━━━━━━━━━━━━━\n\n"
           f"💰 <b>FINANCIAL METRICS</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"💳 <b>Main Balance:</b> <b>{format_price(uid, bal)}</b> (~${bal_usdt:.2f} USDT)\n"
           f"🤝 <b>Sales Balance:</b> <b>{format_price(uid, s_bal)}</b>\n"
           f"📥 <b>Total Deposited:</b> <b>{format_price(uid, dep)}</b>\n"
           f"🛒 <b>Total Spent:</b> <b>{format_price(uid, total_spent)}</b> ({total_accs} Accounts)\n"
           f"━━━━━━━━━━━━━━━━━━━━\n\n"
           f"👥 <b>REFERRAL PROGRAM ({ref_bonus_rate}% Commission)</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"🔗 <b>Referred By:</b> {ref_by_disp}\n"
           f"👥 <b>Your Referrals:</b> <b>{ref_count}</b> Users\n"
           f"🔗 <b>Referral Link:</b>\n"
           f"<code>https://t.me/{bot_username}?start=ref_{uid}</code>\n"
           f"━━━━━━━━━━━━━━━━━━━━")
    
    c_pref = get_currency_pref(uid)
    c_btn_text = "💱 Switch to USDT ($)" if c_pref == "INR" else "💱 Switch to INR (₹)"
    
    btns = [
        [p_btn("💳 Deposit Balance", "menu_deposit", style="success"), p_btn("🤝 Withdraw Sales", "wd_sales", style="primary")],
        [p_btn(c_btn_text, "tgl_curr", style="primary"), p_btn("🎁 Claim Promo Code", "claim_promo", style="success")],
        [p_btn("📦 My Uploads", "menu_uploads", style="primary"), p_btn("📜 Order History", "menu_history", style="primary")],
        [p_btn("⬅️ Main Menu", "menu_main", style="danger")]
    ]
    await safe_show_message(e, msg, buttons=btns)

# ================= RANDOMIZED API ROTATION POOL =================
def get_random_api_credentials():
    try:
        rows = cur.execute("SELECT api_id, api_hash FROM api_credentials WHERE active=1 ORDER BY RANDOM() LIMIT 1").fetchall()
        if rows:
            api_id, api_hash = rows[0]
            return int(api_id), str(api_hash)
    except Exception:
        pass

    if API_ID and API_HASH:
        return int(API_ID), str(API_HASH)

    try:
        row_id = cur.execute("SELECT value FROM settings WHERE key='api_id'").fetchone()
        row_hash = cur.execute("SELECT value FROM settings WHERE key='api_hash'").fetchone()
        if row_id and row_id[0] and row_hash and row_hash[0]:
            return int(row_id[0]), str(row_hash[0])
    except Exception:
        pass

    return int(API_ID), str(API_HASH)

def hex_to_telethon_string_session(auth_hex, dc_id=2):
    dc_ips = {
        1: "149.154.175.53",
        2: "149.154.167.51",
        3: "149.154.175.100",
        4: "149.154.167.91",
        5: "91.108.56.130"
    }
    ip = dc_ips.get(int(dc_id or 2), "149.154.167.51")
    port = 443
    key_bytes = bytes.fromhex(str(auth_hex or "")[:512])
    ip_bytes = socket.inet_aton(ip)
    data = struct.pack(">B4sH256s", int(dc_id or 2), ip_bytes, port, key_bytes)
    encoded = "1" + base64.urlsafe_b64encode(data).decode("ascii")
    return StringSession(encoded)

logout_search_state = {}
session_cache_map = {}

async def inspect_and_add_server2_session(uid, message):
    """Validate a sent/forwarded .session file and add it to Server 2 stock."""
    if not is_admin(uid) or not has_perm(uid, 'p_add_stock'):
        return None
    file_obj = getattr(message, "file", None)
    file_name = getattr(file_obj, "name", "") or ""
    if not file_name.endswith(".session"):
        return None

    os.makedirs("sessions", exist_ok=True)
    tmp_base = f"upload_{uid}_{int(time.time())}_{random.randint(1000, 9999)}"
    tmp_path = await bot.download_media(message, f"{tmp_base}.session")
    if not tmp_path:
        return "❌ Could not download the session file."

    clean_path = tmp_path[:-8] if tmp_path.endswith(".session") else tmp_path
    client = None
    try:
        dyn_id, dyn_hash = get_random_api_credentials()
        client = TelegramClient(clean_path, dyn_id, dyn_hash)
        await client.connect()
        if not await client.is_user_authorized():
            return "❌ Session is not authorized, so it was not added."

        me = await client.get_me()
        phone = str(getattr(me, "phone", "") or "").replace("+", "").replace(" ", "")
        if not phone:
            return "❌ Could not detect phone number from this session."

        c_name, c_icon, _ = get_country_info(phone)
        year = await detect_account_year(client)
        pwd = await client(GetPasswordRequest())
        has_2fa = bool(getattr(pwd, "has_password", False))
        twofa_pass = "Unknown" if has_2fa else "None"
        if FIXED_2FA_PASSWORD and not has_2fa:
            ok_2fa, _err_2fa = await force_fixed_2fa(client)
            if ok_2fa:
                twofa_pass = FIXED_2FA_PASSWORD

        auto_row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year=?", (c_name, str(year))).fetchone()
        if not auto_row:
            auto_row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year='Common'", (c_name,)).fetchone()
        if auto_row:
            price = int(auto_row[0])
        else:
            existing_price = cur.execute("SELECT price FROM stock WHERE country_name=? ORDER BY added_date DESC LIMIT 1", (c_name,)).fetchone()
            price = int(existing_price[0]) if existing_price else 0
        if price <= 0:
            return f"⚠️ Session checked for +{phone}, but no auto/existing price was found. Set an auto price first or use Add Stock (Single)."

        perm_base = f"sessions/{phone}"
        await client.disconnect()
        client = None
        for ext in ['.session', '.session-wal', '.session-shm', '.session-journal']:
            src = clean_path + ext
            if os.path.exists(src):
                shutil.move(src, perm_base + ext)
        cur.execute(
            "INSERT OR REPLACE INTO stock (phone, session_file, country_name, country_icon, account_year, category, price, available, twofa, seller_id) VALUES (?,?,?,?,?,?,?,?,?,NULL)",
            (phone, perm_base + ".session", c_name, c_icon, year, 'Good', price, 1, twofa_pass)
        )
        db.commit()
        return f"✅ <b>Session uploaded to Server 2!</b>\nPhone: <code>+{phone}</code>\nCountry: {c_icon} {c_name}\nYear: <b>{year}</b>\nPrice: <b>₹{price}</b>"
    except Exception as ex:
        await send_admin_error("Direct session upload failed", str(ex))
        return "❌ Session check failed. The file was not added."
    finally:
        try:
            if client:
                await client.disconnect()
        except:
            pass
        if os.path.exists(tmp_path):
            delete_session_files(tmp_path)

# ================= API REQUESTS & MARKUP LOGIC =================
async def wait_lzt_rate_limit():
    """Throttle all LZT requests so one VPS/IP never exceeds market limits."""
    global _lzt_last_request_at
    wait_for = 0.0
    async with _lzt_rate_lock:
        now = time.monotonic()
        scheduled_time = max(now, _lzt_blocked_until, _lzt_last_request_at + LZT_MIN_REQUEST_INTERVAL)
        wait_for = scheduled_time - now
        _lzt_last_request_at = scheduled_time
    if wait_for > 0:
        await asyncio.sleep(wait_for)

def parse_lzt_retry_after(headers):
    if not headers:
        return None
    raw_value = None
    try:
        raw_value = headers.get("Retry-After")
    except Exception:
        raw_value = None
    if not raw_value:
        return None
    try:
        return max(0.0, float(raw_value))
    except (TypeError, ValueError):
        pass
    try:
        retry_at = datetime.strptime(str(raw_value), "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    except Exception:
        return None

async def apply_lzt_rate_limit_cooldown(retry_after=None):
    global _lzt_blocked_until
    wait_for = max(float(retry_after or 0), LZT_RATE_LIMIT_COOLDOWN)
    _lzt_blocked_until = max(_lzt_blocked_until, time.monotonic() + wait_for)
    logger.warning("LZT API rate limited; pausing market requests for %.1fs", wait_for)
    return wait_for

async def get_lzt_session():
    global _lzt_session
    current_loop = asyncio.get_running_loop()
    session_loop = getattr(_lzt_session, "_loop", None) if _lzt_session is not None else None
    if _lzt_session is None or _lzt_session.closed or session_loop is not current_loop:
        if _lzt_session is not None and not _lzt_session.closed:
            await close_lzt_session()
        connector_kwargs = {
            "limit": 5,
            "ttl_dns_cache": 300,
            "keepalive_timeout": 30,
            "enable_cleanup_closed": True,
        }
        if LZT_FORCE_IPV4:
            connector_kwargs["family"] = socket.AF_INET
        connector = aiohttp.TCPConnector(**connector_kwargs)
        _lzt_session = aiohttp.ClientSession(connector=connector, trust_env=True)
    return _lzt_session

async def close_lzt_session():
    global _lzt_session
    if _lzt_session is not None and not _lzt_session.closed:
        await _lzt_session.close()
    _lzt_session = None

def clean_lzt_params(params):
    if not params:
        return None
    clean_params = {}
    for key, value in params.items():
        if key is None or value is None:
            continue
        if isinstance(value, (list, tuple)):
            clean_list = [str(item) for item in value if item is not None]
            if clean_list:
                clean_params[str(key)] = clean_list
        else:
            clean_params[str(key)] = str(value)
    return clean_params or None

def lzt_masked_url(endpoint, params=None):
    query = urllib.parse.urlencode(params or {}, doseq=True)
    return f"{endpoint}?{query}" if query else endpoint

def lzt_response_summary(res):
    if not isinstance(res, dict):
        return type(res).__name__
    parts = []
    if "items" in res and isinstance(res.get("items"), list):
        parts.append(f"items={len(res.get('items') or [])}")
    for key in ("totalItems", "total", "count", "item_id", "id", "http_status"):
        if key in res:
            parts.append(f"{key}={res.get(key)}")
    if not parts and "item" in res:
        parts.append("item=yes")
    if not parts and any(k in res for k in ("error", "errors", "message")):
        parts.append("error=yes")
    return ", ".join(parts) if parts else "ok"

def lzt_sync_request(method, url, headers, params=None, data=None, timeout_total=None, return_error=False, proxy=None):
    method = str(method or "GET").upper()
    timeout_total = float(timeout_total or LZT_REQUEST_TIMEOUT)
    request_url = url
    if params:
        request_url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    body = None
    if method != "GET" and data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(request_url, data=body, headers=headers, method=method)
    opener = None
    if proxy:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    try:
        open_call = opener.open if opener else urllib.request.urlopen
        with open_call(req, timeout=timeout_total) as response:
            text = response.read().decode("utf-8", errors="replace")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as ex:
        text = ex.read().decode("utf-8", errors="replace")
        if return_error:
            try:
                err = json.loads(text) if text else {}
            except Exception:
                err = {"error": text}
            if not isinstance(err, dict):
                err = {"error": str(err)}
            err["http_status"] = ex.code
            return err
        raise

async def lzt_fallback_request(method, url, headers, params=None, data=None, timeout_total=None, return_error=False):
    await wait_lzt_rate_limit()
    try:
        return await asyncio.to_thread(
            lzt_sync_request, method, url, headers, params, data, timeout_total, return_error, LZT_PROXY or None
        )
    except urllib.error.HTTPError as ex:
        if ex.code == 429:
            wait_for = await apply_lzt_rate_limit_cooldown(parse_lzt_retry_after(ex.headers))
            if return_error:
                return {"error": "rate limited", "http_status": 429, "retry_after": wait_for}
            return None
        raise

async def lzt_request(method, endpoint, params=None, data=None, return_error=False, timeout_total=None, max_retries=None, notify_errors=True):
    global _lzt_missing_logged
    token_resolved = resolve_lzt_token()
    if not token_resolved:
        if not _lzt_missing_logged:
            _lzt_missing_logged = True
            logger.error("LZT API request blocked: token is missing for %s %s", method, endpoint)
            try:
                await send_admin_error("LZT token missing", f"Server 1 cannot submit {method} {endpoint} because no token is configured.")
            except Exception:
                pass
        return None
    token = token_resolved.replace("Bearer ", "").strip()
    method = str(method or "GET").upper()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "TgsellBot/1.0 (+https://t.me)"
    }
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    url = f"{LZT_BASE_URL}{endpoint}"

    params = clean_lzt_params(params)

    is_stock_request = method == 'GET' and endpoint == '/telegram'
    timeout_total = timeout_total if timeout_total is not None else (LZT_STOCK_TIMEOUT if is_stock_request else LZT_REQUEST_TIMEOUT)
    max_retries = max(1, int(max_retries if max_retries is not None else (LZT_STOCK_RETRIES if is_stock_request else LZT_MAX_RETRIES)))
    timeout = aiohttp.ClientTimeout(total=float(timeout_total), connect=min(2.0, float(timeout_total)), sock_connect=min(2.0, float(timeout_total)), sock_read=float(timeout_total))
    last_detail = ""
    masked_url = lzt_masked_url(endpoint, params)
    if LZT_REQUEST_DEBUG:
        logger.info("LZT API submit: %s %s via aiohttp timeout=%ss retries=%s", method, masked_url, timeout_total, max_retries)

    try:
        session = await get_lzt_session()
        for attempt in range(1, max_retries + 1):
            try:
                request_kwargs = {"headers": headers, "params": params, "timeout": timeout}
                if LZT_PROXY:
                    request_kwargs["proxy"] = LZT_PROXY
                if method == 'POST':
                    request_kwargs["json"] = data
                    request_ctx = session.post(url, **request_kwargs)
                elif method == 'GET':
                    request_ctx = session.get(url, **request_kwargs)
                else:
                    return None

                await wait_lzt_rate_limit()
                async with request_ctx as r:
                    try:
                        text = await r.text()
                    except (aiohttp.ClientPayloadError, asyncio.TimeoutError) as ex:
                        last_detail = f"{type(ex).__name__}: {ex!r}"
                        if attempt < max_retries:
                            await asyncio.sleep(0.15 * attempt)
                            continue
                        break
                    if r.status >= 500 and attempt < max_retries:
                        await asyncio.sleep(0.25 * attempt)
                        continue
                    if r.status == 429:
                        retry_after = parse_lzt_retry_after(r.headers)
                        wait_for = await apply_lzt_rate_limit_cooldown(retry_after)
                        if LZT_REQUEST_DEBUG:
                            logger.warning("LZT API HTTP 429: %s %s retry_after=%s body=%s", method, masked_url, wait_for, text[:500])
                        if attempt < max_retries:
                            await asyncio.sleep(wait_for)
                            continue
                        if return_error:
                            try:
                                err = await r.json(content_type=None)
                            except Exception:
                                err = {"error": text or "rate limited"}
                            if not isinstance(err, dict):
                                err = {"error": str(err)}
                            err["http_status"] = r.status
                            err["retry_after"] = wait_for
                            return err
                        return None
                    if r.status >= 400:
                        if LZT_REQUEST_DEBUG:
                            logger.warning("LZT API HTTP error: %s %s status=%s body=%s", method, masked_url, r.status, text[:500])
                        if notify_errors:
                            await send_admin_error(f"Market HTTP {r.status} {method} {endpoint}", text[:2000])
                        if return_error:
                            try:
                                err = await r.json(content_type=None)
                            except Exception:
                                err = {"error": text}
                            if not isinstance(err, dict):
                                err = {"error": str(err)}
                            err["http_status"] = r.status
                            return err
                        return None
                    try:
                        parsed = await r.json(content_type=None)
                        if LZT_REQUEST_DEBUG:
                            logger.info("LZT API success: %s %s status=%s %s", method, masked_url, r.status, lzt_response_summary(parsed))
                        return parsed
                    except Exception as ex:
                        last_detail = f"{type(ex).__name__}: {ex!r}"
                        if notify_errors:
                            await send_admin_error(f"Market {method} {endpoint} JSON Parse Fail", f"{last_detail}\n\n{text[:2000]}")
                        return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_detail = f"{type(e).__name__}: {e!r}"
                if isinstance(e, (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError, aiohttp.ClientOSError)):
                    await close_lzt_session()
                    session = await get_lzt_session()
                if attempt < max_retries:
                    await asyncio.sleep(0.15 * attempt)
                    continue
        detail = last_detail or f"Timeout after {timeout_total}s"
        if LZT_HTTP_FALLBACK:
            try:
                if LZT_REQUEST_DEBUG:
                    logger.info("LZT API fallback submit: %s %s via urllib timeout=%ss", method, masked_url, timeout_total)
                fallback_res = await lzt_fallback_request(method, url, headers, params=params, data=data, timeout_total=timeout_total, return_error=return_error)
                if isinstance(fallback_res, dict) and fallback_res.get("http_status") == 429:
                    await apply_lzt_rate_limit_cooldown(fallback_res.get("retry_after"))
                if LZT_REQUEST_DEBUG:
                    logger.info("LZT API fallback success: %s %s %s", method, masked_url, lzt_response_summary(fallback_res))
                return fallback_res
            except Exception as fallback_ex:
                detail = f"{detail} | fallback {type(fallback_ex).__name__}: {fallback_ex!r}"
        if LZT_REQUEST_DEBUG:
            logger.warning("LZT API failed: %s %s %s", method, masked_url, detail)
        if notify_errors:
            await send_admin_error(f"Market Client/Timeout Error: {method} {endpoint}", detail)
        if return_error:
            return {"error": detail, "exception": detail.split(':', 1)[0]}
        return None
    except Exception as e:
        detail = f"{type(e).__name__}: {e!r}"
        if LZT_HTTP_FALLBACK:
            try:
                if LZT_REQUEST_DEBUG:
                    logger.info("LZT API fallback submit after general fail: %s %s via urllib timeout=%ss", method, masked_url, timeout_total)
                fallback_res = await lzt_fallback_request(method, url, headers, params=params, data=data, timeout_total=timeout_total, return_error=return_error)
                if isinstance(fallback_res, dict) and fallback_res.get("http_status") == 429:
                    await apply_lzt_rate_limit_cooldown(fallback_res.get("retry_after"))
                if LZT_REQUEST_DEBUG:
                    logger.info("LZT API fallback success: %s %s %s", method, masked_url, lzt_response_summary(fallback_res))
                return fallback_res
            except Exception as fallback_ex:
                detail = f"{detail} | fallback {type(fallback_ex).__name__}: {fallback_ex!r}"
        if LZT_REQUEST_DEBUG:
            logger.warning("LZT API failed: %s %s %s", method, masked_url, detail)
        if notify_errors:
            await send_admin_error(f"Market Request General Fail: {method} {endpoint}", detail)
        if return_error:
            return {"error": detail, "exception": type(e).__name__}
        return None

async def fetch_lzt_country_data_with_filters(country_name, spam, geoblock, offline, login_mail, premium):
    iso_code = COUNTRY_CODES.get(country_name, ("US", "🇺🇸"))[0]
    params = {
        "country[]": iso_code,
        "spam": spam if spam != "any" else None,
        "nsb": 1,
        "pmin": 0.01,
        "pmax": 1000,
        "page": 1,
        "per_page": 40,
        "password": "no",
        "currency": LZT_PRICE_CURRENCY
    }
    if offline != "any":
        params["daybreak"] = int(offline)
    if premium != "any":
        params["premium"] = premium

    res = await lzt_request('GET', '/telegram', params=params, timeout_total=LZT_STOCK_TIMEOUT, max_retries=LZT_STOCK_RETRIES, notify_errors=False)
    if isinstance(res, dict) and 'items' in res and not res.get('items') and iso_code:
        params["country[]"] = country_name
        res = await lzt_request('GET', '/telegram', params=params, timeout_total=LZT_STOCK_TIMEOUT, max_retries=1, notify_errors=False)

    if not res or 'items' not in res:
        return None
    if len(res.get('items') or []) == 0:
        return (country_name, 0, 0.0)

    flt = {"spam": spam, "geoblock": geoblock, "offline": offline, "login_mail": login_mail, "premium": premium}
    filtered_items = filter_lzt_items(res['items'], flt)
    if not filtered_items:
        return (country_name, 0, 0.0)
    count = res.get('totalItems', len(filtered_items)) if len(filtered_items) == len(res['items']) else len(filtered_items)
    parsed_items = sorted(filtered_items, key=lambda x: float(x.get('price') or x.get('priceWithSellerFee') or x.get('price_with_fee') or 99999))
    item0 = parsed_items[0]

    markup = get_lzt_markup(country_name)
    final_price = lzt_final_inr_price(item0, markup)
    return (country_name, count, final_price)

async def cache_lzt_stock_loop():
    global cached_lzt_stock
    sem = asyncio.Semaphore(max(1, LZT_CACHE_CONCURRENCY))

    async def fetch_and_cache(country_name, fkey):
        async with sem:
            try:
                parts = fkey.split("_")
                spam, geoblock, offline, login_mail, premium = parts[0], parts[1], parts[2], parts[3], parts[4]
                data = await fetch_lzt_country_data_with_filters(country_name, spam, geoblock, offline, login_mail, premium)

                if fkey not in cached_lzt_stock:
                    cached_lzt_stock[fkey] = {}

                if data is not None:
                    cached_lzt_stock[fkey][country_name] = (data[1], data[2])
            except Exception as ex:
                if fkey not in cached_lzt_stock:
                    cached_lzt_stock[fkey] = {}

    while True:
        try:
            keys_to_update = list(active_filter_keys)
            tasks = []
            for fkey in keys_to_update:
                for country in COUNTRY_CODES.keys():
                    tasks.append(fetch_and_cache(country, fkey))
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Background LZT cache index failed: {e}")
        await asyncio.sleep(max(30, LZT_CACHE_REFRESH_SECONDS))

def resolve_lzt_token():
    env_token = (LZT_TOKEN or "").strip()
    if env_token:
        return env_token
    try:
        row = cur.execute("SELECT value FROM settings WHERE key='lzt_token'").fetchone()
        if row and str(row[0]).strip():
            return str(row[0]).strip()
    except Exception:
        pass
    return ""

async def process_referral_bonus(uid, amount):
    row = cur.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,)).fetchone()
    ref = row[0] if row else None
    if ref:
        pct_row = cur.execute("SELECT value FROM settings WHERE key='ref_percent'").fetchone()
        pct = float(pct_row[0]) if pct_row else 3.0
        if pct > 0:
            bonus = int(amount * (pct / 100))
            if bonus > 0:
                update_balance(ref, bonus)
                try: await bot.send_message(ref, f"{P_GIFT} <b>Referral Bonus!</b>\nYour referral <code>{uid}</code> deposited ₹{amount}.\n{P_YES} You earned <b>{P_YES}{bonus}</b>!")
                except: pass

# ================= DATABASE SETUP & MIGRATIONS =================
def setup_db():
    os.makedirs("sessions", exist_ok=True)
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, sales_balance INTEGER DEFAULT 0, referred_by INTEGER, total_deposited INTEGER DEFAULT 0, joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, banned INTEGER DEFAULT 0, discount INTEGER DEFAULT 0, terms_accepted INTEGER DEFAULT 0, pref_curr TEXT DEFAULT 'INR');
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS stock (phone TEXT PRIMARY KEY, session_file TEXT, country_name TEXT, country_icon TEXT DEFAULT '🌍', account_year INTEGER, category TEXT DEFAULT 'Good', price INTEGER, available INTEGER DEFAULT 1, twofa TEXT DEFAULT 'None', added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, seller_id INTEGER DEFAULT NULL);
    CREATE TABLE IF NOT EXISTS auto_prices (country TEXT, year TEXT, price INTEGER, PRIMARY KEY (country, year));
    CREATE TABLE IF NOT EXISTS deposits (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, method_name TEXT, status TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS upi_orders (order_id TEXT PRIMARY KEY, user_id INTEGER, amount INTEGER, status TEXT, qr_msg_id INTEGER, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, country TEXT, year INTEGER, price INTEGER, phone TEXT, otp TEXT, server TEXT DEFAULT 'Local', date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS custom_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, caption TEXT, qr_file_id TEXT);
    CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, p_add_stock INTEGER DEFAULT 0, p_manage_stock INTEGER DEFAULT 0, p_stats INTEGER DEFAULT 0, p_bal INTEGER DEFAULT 0, p_settings INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS api_credentials (id INTEGER PRIMARY KEY AUTOINCREMENT, api_id INTEGER NOT NULL, api_hash TEXT NOT NULL, label TEXT DEFAULT 'API', active INTEGER DEFAULT 1, added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS custom_countries (code TEXT PRIMARY KEY, name TEXT, flag TEXT);
    CREATE TABLE IF NOT EXISTS lzt_settings (country TEXT PRIMARY KEY, markup_percent INTEGER DEFAULT 20);
    CREATE TABLE IF NOT EXISTS sell_prices (country_code TEXT, year TEXT, price_good INTEGER DEFAULT 20, price_spam INTEGER DEFAULT 5, PRIMARY KEY(country_code, year));
    CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, method TEXT, details TEXT, status TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS blacklisted_phones (phone TEXT PRIMARY KEY, removed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, value INTEGER, max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS promo_logs (code TEXT, user_id INTEGER, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS giveaways (id TEXT PRIMARY KEY, prize_name TEXT, ticket_price INTEGER, min_participants INTEGER, winners_count INTEGER, status TEXT DEFAULT 'open', created_by INTEGER, message_id INTEGER DEFAULT NULL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS giveaway_tickets (giveaway_id TEXT, user_id INTEGER, tickets INTEGER DEFAULT 0, PRIMARY KEY(giveaway_id, user_id));
    CREATE TABLE IF NOT EXISTS pending_orders (phone TEXT PRIMARY KEY, user_id INTEGER, price INTEGER, created REAL);
    CREATE TABLE IF NOT EXISTS sell_price_list (id INTEGER PRIMARY KEY AUTOINCREMENT, country_code_or_name TEXT, dial_code TEXT, iso_code TEXT, flag_emoji TEXT, price REAL, currency TEXT DEFAULT 'USD', active INTEGER DEFAULT 1);
    """)

    def ensure_column(table, column, definition):
        existing = [row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    ensure_column("users", "pref_curr", "TEXT DEFAULT 'INR'")
    ensure_column("users", "username", "TEXT DEFAULT ''")
    ensure_column("users", "first_name", "TEXT DEFAULT ''")
    ensure_column("orders", "server", "TEXT DEFAULT 'Server 2'")

    if API_ID and API_HASH:
        cur.execute("INSERT OR IGNORE INTO api_credentials (api_id, api_hash, label, active) VALUES (?,?, 'Primary .env API', 1)", (API_ID, API_HASH))
        db.commit()

    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('lzt_global_markup', '20')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_status', 'on')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('server1_status', 'on')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('upi_status', 'on')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cwallet_status', 'on')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('usdt_rate', '94.0')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rub_inr_rate', '1.05')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('eur_inr_rate', '100.0')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gbp_inr_rate', '118.0')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cny_inr_rate', '13.0')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('uah_inr_rate', '2.3')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('kzt_inr_rate', '0.2')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('byn_inr_rate', '29.0')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('try_inr_rate', '2.9')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('jpy_inr_rate', '0.62')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('brl_inr_rate', '17.0')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ref_percent', '3')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_url', '" + (HELP_URL or "https://t.me/telegram") + "')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('min_upi_dep', '10')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('min_cw_dep', '10')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('fight_game_status', 'on')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('api_id', '')")
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('api_hash', '')")
    cur.execute("UPDATE users SET pref_curr='USDT' WHERE UPPER(COALESCE(pref_curr, ''))='USD'")
    cur.execute("""
        DELETE FROM custom_payments
        WHERE LOWER(name)='cwallet'
          AND id NOT IN (SELECT MIN(id) FROM custom_payments WHERE LOWER(name)='cwallet')
    """)
    cur.execute("INSERT OR REPLACE INTO admins (user_id, p_add_stock, p_manage_stock, p_stats, p_bal, p_settings) VALUES (5719136023, 1, 1, 1, 1, 1)")
    cur.execute("INSERT OR REPLACE INTO admins (user_id, p_add_stock, p_manage_stock, p_stats, p_bal, p_settings) VALUES (7151224687, 1, 1, 1, 1, 1)")
    db.commit()

# ================= VIEW ALL COUNTRIES LIST BUILDER =================
async def send_all_countries_list(uid):
    fkey = get_filter_key(get_user_filters(uid))
    stock_dict = cached_lzt_stock.get(fkey, cached_lzt_stock.get("no_no_any_any_any", {}))
    me = await bot.get_me()
    bot_username = me.username or ""

    rows = []
    for name, (iso, flag) in COUNTRY_CODES.items():
        ccode = CALLING_CODES.get(name, "")
        if not ccode:
            continue
        count, min_p = stock_dict.get(name, (0, 0.0))
        slug = country_slug(name)
        rows.append((count, name, iso, flag, ccode, min_p, slug))

    rows.sort(key=lambda item: (-item[0], item[1]))
    lines = ["All Server 1 countries [tap a country link to open]"]
    for count, name, iso, flag, ccode, min_p, slug in rows:
        label = f"{flag} +{ccode} {get_country_button_code(name)} ({iso}) {format_price(uid, min_p)} → {count}"
        if bot_username:
            lines.append(f'<a href="https://t.me/{bot_username}?start=server1-{slug}">{html.escape(label)}</a>')
        else:
            lines.append(html.escape(label))

    chunks, current = [], []
    for line in lines:
        projected = "\n".join(current + [line])
        if len(projected) > 3500 and current:
            chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current))

    for idx, chunk in enumerate(chunks, start=1):
        title = f"<b>Server 1 countries P{idx}/{len(chunks)}</b>"
        text = f"{title}\n<blockquote expandable>{chunk}</blockquote>"
        await bot.send_message(uid, text, link_preview=False)


def extract_otp_from_message_text(message_text):
    if not message_text or "Login detected" in message_text:
        return None
    match = re.search(OTP_REGEX, message_text)
    return match.group(0) if match else None

async def get_latest_telegram_login_otp(client, start_time, limit=12):
    msgs = await client.get_messages(777000, limit=limit)
    candidates = []
    for msg in msgs:
        msg_time = msg.date.timestamp() if getattr(msg, "date", None) else 0
        if msg_time < start_time:
            continue
        code = extract_otp_from_message_text(getattr(msg, "message", None))
        if code:
            candidates.append((msg_time, code))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]

# ================= BACKGROUND TASKS =================
# =====================================================================
#  MERGED ADDITIONS
#  1) recover_pending_orders   - refund unfinished Server-2 orders after a restart
#  2) force_fixed_2fa          - optional fixed 2FA password setter for own stock
#  3) Reply keyboard + router  - persistent bottom menu (Button.text)
#  4) Sell price list          - "We buy from you" rate card + admin editor
#  5) Stats / Refer / Support / Promo shortcuts for the reply keyboard
# =====================================================================

# ---------------------------------------------------------------- 1) PENDING ORDER RECOVERY
async def recover_pending_orders():
    """After a restart: refund Server-2 orders whose OTP was never delivered and restore the stock."""
    try:
        rows = cur.execute("SELECT phone, user_id, price FROM pending_orders").fetchall()
    except Exception as ex:
        logger.error(f"recover_pending_orders read error: {ex}")
        return
    for phone, p_uid, price in rows:
        try:
            refunded = False
            async with get_user_lock(p_uid):
                in_stock = cur.execute("SELECT 1 FROM stock WHERE phone=?", (phone,)).fetchone()
                cur.execute("DELETE FROM pending_orders WHERE phone=?", (phone,))
                if in_stock:
                    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (price, p_uid))
                    cur.execute("UPDATE stock SET available=1 WHERE phone=?", (phone,))
                    refunded = True
                db.commit()
            if refunded:
                logger.info(f"Recovered pending order {phone} for {p_uid}, refunded {price}")
                try:
                    await bot.send_message(
                        p_uid,
                        f"{P_WARN} <b>Order cancelled because the bot restarted.</b>\n"
                        f"₹{price} has been refunded to your balance.")
                except Exception:
                    pass
        except Exception as ex:
            logger.error(f"recover_pending_orders error for {phone}: {ex}")


# ---------------------------------------------------------------- 2) OPTIONAL FIXED 2FA
async def force_fixed_2fa(client, old_password=None, new_password=None):
    """Set the 2FA password of an account we own to FIXED_2FA_PASSWORD. Returns (ok, error_text)."""
    new_password = new_password or FIXED_2FA_PASSWORD
    if not new_password:
        return False, "FIXED_2FA_PASSWORD is not set"
    try:
        pwd = await client(GetPasswordRequest())
        if pwd.has_password:
            if not old_password or old_password in ("None", "Unknown"):
                return False, "current 2FA password unknown"
            if old_password == new_password:
                return True, None
            await client.edit_2fa(current_password=old_password, new_password=new_password, hint="")
        else:
            await client.edit_2fa(new_password=new_password, hint="")
        return True, None
    except Exception as ex:
        return False, str(ex)[:120]


# ---------------------------------------------------------------- 3) REPLY KEYBOARD + ROUTER
reply_kb_sent = set()
spl_state = {}

# label -> inline callback (runs the existing handler) or "@name" (local handler below)
MENU_LABELS = {
    "🛒 Buy Accounts": "menu_buy",
    "💰 Deposit": "menu_deposit",
    "📤 Sell Account": "menu_sell",
    "💸 Sell Prices": "@sell_prices",
    "👤 Profile": "menu_account",
    "📊 Stats": "@stats",
    "🎁 Refer & Earn": "@refer",
    "🎟️ Promo / Giveaway": "@promo",
    "🆘 Support": "@support",
}


def _norm_label(s):
    return str(s or "").replace("\ufe0f", "").strip()


MENU_LABEL_LOOKUP = {_norm_label(k): v for k, v in MENU_LABELS.items()}

PENDING_TEXT_STATE_DICTS = (
    "sell_state", "wd_state", "logout_search_state", "lookup_search_state", "lookup_action_state",
    "lzt_search_state", "manual_dep_state", "promo_state", "admin_dep_state",
    "giveaway_ticket_state", "session_buy_state", "spl_state",
)


def _clear_pending_text_states(uid):
    """A menu tap cancels any half-finished text prompt so old state never swallows the next message."""
    for name in PENDING_TEXT_STATE_DICTS:
        d = globals().get(name)
        if isinstance(d, dict):
            d.pop(uid, None)


def build_reply_keyboard():
    t = lambda label: Button.text(label, resize=True)
    return [
        [t("🛒 Buy Accounts"), t("💰 Deposit")],
        [t("📤 Sell Account"), t("💸 Sell Prices")],
        [t("👤 Profile"), t("📊 Stats")],
        [t("🎁 Refer & Earn"), t("🎟️ Promo / Giveaway")],
        [t("🆘 Support")],
    ]


async def ensure_reply_keyboard(uid, force=False):
    if not force and uid in reply_kb_sent:
        return
    reply_kb_sent.add(uid)
    try:
        await bot.send_message(uid, "⌨️ <b>Quick menu enabled.</b> Use the buttons below anytime.",
                               buttons=build_reply_keyboard())
    except Exception as ex:
        logger.warning(f"reply keyboard send failed for {uid}: {ex}")


class MessageCallbackShim:
    """Lets the inline-button handlers (written for CallbackQuery events) run from a reply-keyboard tap."""

    def __init__(self, ev, data):
        self._ev = ev
        self.data = data.encode()
        self.sender_id = ev.sender_id
        self.chat_id = ev.chat_id

    def __getattr__(self, name):
        return getattr(self._ev, name)

    async def edit(self, *args, **kwargs):
        return await self._ev.respond(*args, **kwargs)

    async def answer(self, message=None, alert=False, **kwargs):
        if message and alert:
            try:
                await self._ev.respond(message)
            except Exception:
                pass
        return None


async def _route_menu_tap(e, uid, key):
    ensure_user(uid)
    if is_user_banned(uid):
        return await e.respond("❌ Your account has been banned.")
    if not is_bot_online() and not is_admin(uid):
        return await e.respond(f"{P_OFF} Bot is under maintenance.")
    if not await check_channel_joined(uid):
        btns = [[p_btn(f"📢 Join Channel {i+1}", url=link)] for i, link in enumerate(JOIN_URLS)]
        btns.append([p_btn("✅ Verify Joined", "verify_join")])
        return await e.respond(f"{P_WARN} <b>You must join our channels first!</b>", buttons=btns)
    _clear_pending_text_states(uid)
    if key.startswith("@"):
        handler = REPLY_LOCAL_HANDLERS[key]
        return await handler(e, uid)
    return await handle_callbacks(MessageCallbackShim(e, key))


# Registered BEFORE handle_text_inputs, so a menu tap is never mistaken for a typed phone number / code.
@bot.on(events.NewMessage())
async def handle_reply_keyboard(e):
    text = getattr(e, "text", None)
    if not text or text.startswith("/"):
        return
    key = MENU_LABEL_LOOKUP.get(_norm_label(text))
    if not key:
        return
    uid = e.sender_id
    if uid and is_private_event(e):
        try:
            await _route_menu_tap(e, uid, key)
        except Exception as ex:
            logger.error(f"reply-keyboard route error ({text}): {ex}", exc_info=True)
            try:
                await e.respond("⚠️ Something went wrong. Please try again.")
            except Exception:
                pass
    raise events.StopPropagation


# ---------------------------------------------------------------- 4) SELL PRICE LIST
def spl_get_setting(key, default=""):
    try:
        row = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row and row[0] is not None else default
    except Exception:
        return default


def spl_set_setting(key, value):
    cur.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value))
    db.commit()


_CUR_NORMALISE = {"$": "USD", "USD": "USD", "USDT": "USD", "₹": "INR", "INR": "INR", "RS": "INR"}
_CUR_SYMBOL = {"USD": "$", "INR": "₹"}


def spl_fmt_price(price, currency):
    sym = _CUR_SYMBOL.get(str(currency or "").upper(), str(currency or ""))
    txt = f"{float(price):.2f}".rstrip("0").rstrip(".")
    return f"{txt}{sym}"


def get_sell_price_rows():
    """[(dial, iso, flag, price, currency)] - the admin's rate card; falls back to the payout tiers."""
    rows = cur.execute(
        "SELECT dial_code, iso_code, flag_emoji, price, currency FROM sell_price_list "
        "WHERE active=1 ORDER BY CAST(dial_code AS INTEGER), iso_code").fetchall()
    if rows:
        return rows
    out = []
    try:
        for code, best in cur.execute(
                "SELECT country_code, MAX(price_good) FROM sell_prices GROUP BY country_code").fetchall():
            try:
                name, flag, _ = get_country_info(str(code))
            except Exception:
                name, flag = "Unknown", "🌍"
            iso = str(COUNTRY_CODES.get(name, ("",))[0] or "??").upper()
            out.append((str(code).lstrip("+"), iso, flag, float(best or 0), "INR"))
    except Exception:
        pass
    out.sort(key=lambda r: int(r[0]) if str(r[0]).isdigit() else 9999)
    return out


def build_sell_price_messages():
    rows = get_sell_price_rows()
    if not rows:
        return []
    head = "<b>We buy from you →</b>\n"
    guide = spl_get_setting("sell_guide_url", "").strip()
    if guide:
        head += f"📖 <a href=\"{html.escape(guide, quote=True)}\">How to sell (guide)</a>\n"
    head += "\n"
    lines = [f"[{html.escape(str(r[2]))}]+{html.escape(str(r[0]))}-{html.escape(str(r[1]))}: {spl_fmt_price(r[3], r[4])}"
             for r in rows]
    msgs, cur_txt = [], head
    for ln in lines:
        if len(cur_txt) + len(ln) + 1 > 3500:
            msgs.append(cur_txt)
            cur_txt = "<b>We buy from you → (continued)</b>\n\n"
        cur_txt += ln + "\n"
    msgs.append(cur_txt)
    return msgs


async def send_sell_price_list(e, uid):
    msgs = build_sell_price_messages()
    if not msgs:
        return await e.respond("ℹ️ Sell prices are not set yet. Please check back later.")
    for n, m in enumerate(msgs):
        last = n == len(msgs) - 1
        await e.respond(m, buttons=[[p_btn("📤 Sell Account", "menu_sell", style="success")]] if last else None,
                        link_preview=False)


# ---- admin editor (inline) --------------------------------------------------
SPL_PAGE = 15


async def render_spl_admin(e, page=1):
    total = cur.execute("SELECT COUNT(*) FROM sell_price_list").fetchone()[0]
    pages = max(1, (total + SPL_PAGE - 1) // SPL_PAGE)
    page = min(max(1, page), pages)
    rows = cur.execute(
        "SELECT id, dial_code, iso_code, flag_emoji, price, currency, active FROM sell_price_list "
        "ORDER BY CAST(dial_code AS INTEGER), iso_code LIMIT ? OFFSET ?",
        (SPL_PAGE, (page - 1) * SPL_PAGE)).fetchall()
    guide = spl_get_setting("sell_guide_url", "") or "not set"
    msg = (f"💸 <b>Sell Price List</b> (page {page}/{pages}, {total} total)\n"
           f"📖 Guide link: <code>{html.escape(guide)}</code>\n\n"
           "Tap a row to enable/disable it, 🗑 to delete.\n"
           "<i>If the list is empty, users see the payout tiers from Sell Settings instead.</i>")
    btns = []
    for rid, dial, iso, flag, price, curr, active in rows:
        label = f"{'✅' if active else '🚫'} {flag}+{dial} {iso} {spl_fmt_price(price, curr)}"
        btns.append([p_btn(label, f"adm_spl_t|{rid}"), p_btn("🗑", f"adm_spl_d|{rid}", style="danger")])
    nav = []
    if page > 1:
        nav.append(p_btn("◀️ Prev", f"adm_spl_pg|{page-1}"))
    if page < pages:
        nav.append(p_btn("Next ▶️", f"adm_spl_pg|{page+1}"))
    if nav:
        btns.append(nav)
    btns.append([p_btn("➕ Add / Update", "adm_spl_add", style="success"),
                 p_btn("📥 Import tiers", "adm_spl_seed", style="primary")])
    btns.append([p_btn("📖 Set Guide Link", "adm_spl_guide", style="primary")])
    btns.append([p_btn("Back", "adm_adminmain", style="danger")])
    return await e.edit(msg, buttons=btns, link_preview=False)


async def handle_spl_admin(e, uid, data):
    action = data[4:]  # strip "adm_"
    if action == "spl":
        spl_state.pop(uid, None)
        return await render_spl_admin(e, 1)
    if action.startswith("spl_pg|"):
        return await render_spl_admin(e, int(action.split("|")[1]))
    if action == "spl_add":
        spl_state[uid] = {"step": "add"}
        return await e.edit(
            "➕ <b>Add / update a sell price</b>\n\n"
            "Send ONE line: <code>DIAL ISO FLAG PRICE CURRENCY</code>\n"
            "Example: <code>998 UZ 🇺🇿 0.45 $</code>\n"
            "Example: <code>91 IN 🇮🇳 20 ₹</code>\n\n"
            "Currency: <code>$</code> or <code>₹</code> (USD / INR).",
            buttons=[[p_btn("Cancel", "adm_spl", style="danger")]])
    if action == "spl_guide":
        spl_state[uid] = {"step": "guide"}
        return await e.edit("📖 Send the guide / video link (https://...), or send <code>-</code> to remove it.",
                            buttons=[[p_btn("Cancel", "adm_spl", style="danger")]])
    if action == "spl_seed":
        added = 0
        for code, best in cur.execute(
                "SELECT country_code, MAX(price_good) FROM sell_prices GROUP BY country_code").fetchall():
            dial = str(code).lstrip("+")
            try:
                name, flag, _ = get_country_info(dial)
            except Exception:
                name, flag = "Unknown", "🌍"
            iso = str(COUNTRY_CODES.get(name, ("",))[0] or "??").upper()
            if cur.execute("SELECT 1 FROM sell_price_list WHERE dial_code=? AND iso_code=?", (dial, iso)).fetchone():
                continue
            cur.execute(
                "INSERT INTO sell_price_list (country_code_or_name, dial_code, iso_code, flag_emoji, price, currency, active) "
                "VALUES (?,?,?,?,?,?,1)", (name, dial, iso, flag, float(best or 0), "INR"))
            added += 1
        db.commit()
        await safe_answer_cb(e, f"Imported {added} row(s).", alert=False)
        return await render_spl_admin(e, 1)
    if action.startswith("spl_t|"):
        cur.execute("UPDATE sell_price_list SET active = 1 - active WHERE id=?", (int(action.split("|")[1]),))
        db.commit()
        return await render_spl_admin(e, 1)
    if action.startswith("spl_d|"):
        cur.execute("DELETE FROM sell_price_list WHERE id=?", (int(action.split("|")[1]),))
        db.commit()
        return await render_spl_admin(e, 1)


async def handle_spl_text(e, uid, text):
    """Returns True when the message was consumed by the price-list editor."""
    st = spl_state.get(uid)
    if not st:
        return False
    back = [[p_btn("Back to Price List", "adm_spl", style="primary")]]
    if st["step"] == "guide":
        val = text.strip()
        if val == "-":
            spl_set_setting("sell_guide_url", "")
            spl_state.pop(uid, None)
            await e.reply("✅ Guide link removed.", buttons=back)
        elif val.lower().startswith(("http://", "https://")):
            spl_set_setting("sell_guide_url", val)
            spl_state.pop(uid, None)
            await e.reply("✅ Guide link saved.", buttons=back)
        else:
            await e.reply("❌ Send a link starting with https:// (or <code>-</code> to remove).")
        return True
    if st["step"] == "add":
        parts = text.split()
        if len(parts) != 5:
            await e.reply("❌ Format: <code>DIAL ISO FLAG PRICE CURRENCY</code>\nExample: <code>998 UZ 🇺🇿 0.45 $</code>")
            return True
        dial, iso, flag, price_s, curr_s = parts
        dial = dial.lstrip("+")
        curr = _CUR_NORMALISE.get(curr_s.upper())
        try:
            price = float(price_s)
        except ValueError:
            price = -1
        if not (dial.isdigit() and 1 <= len(dial) <= 4) or not (2 <= len(iso) <= 3 and iso.isalpha()) \
                or price <= 0 or not curr:
            await e.reply("❌ Invalid values. Example: <code>998 UZ 🇺🇿 0.45 $</code>")
            return True
        iso = iso.upper()
        try:
            name = get_country_info(dial)[0]
        except Exception:
            name = iso
        row = cur.execute("SELECT id FROM sell_price_list WHERE dial_code=? AND iso_code=?", (dial, iso)).fetchone()
        if row:
            cur.execute("UPDATE sell_price_list SET flag_emoji=?, price=?, currency=?, active=1, country_code_or_name=? WHERE id=?",
                        (flag, price, curr, name, row[0]))
        else:
            cur.execute(
                "INSERT INTO sell_price_list (country_code_or_name, dial_code, iso_code, flag_emoji, price, currency, active) "
                "VALUES (?,?,?,?,?,?,1)", (name, dial, iso, flag, price, curr))
        db.commit()
        spl_state.pop(uid, None)
        await e.reply(f"✅ Saved: [{html.escape(flag)}]+{dial}-{iso}: {spl_fmt_price(price, curr)}", buttons=back)
        return True
    return False


# ---------------------------------------------------------------- 5) LOCAL SHORTCUTS
async def send_user_stats(e, uid):
    ensure_user(uid)
    bal, s_bal, dep = cur.execute(
        "SELECT balance, sales_balance, total_deposited FROM users WHERE user_id=?", (uid,)).fetchone()
    cnt, spent = cur.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE user_id=?", (uid,)).fetchone()
    refs = cur.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,)).fetchone()[0]
    uploads = cur.execute("SELECT COUNT(*) FROM stock WHERE seller_id=?", (uid,)).fetchone()[0]
    msg = ("📊 <b>Your Stats</b>\n"
           "━━━━━━━━━━━━━━━━━━━━\n"
           f"💰 Balance: <b>{format_price(uid, bal)}</b>\n"
           f"💼 Sales balance: <b>{format_price(uid, s_bal)}</b>\n"
           f"➕ Total deposited: <b>{format_price(uid, dep)}</b>\n"
           f"🛒 Accounts bought: <b>{cnt}</b>\n"
           f"💸 Total spent: <b>{format_price(uid, spent)}</b>\n"
           f"📦 Accounts you uploaded (in stock): <b>{uploads}</b>\n"
           f"👥 Referrals: <b>{refs}</b>")
    await e.respond(msg, buttons=[[p_btn("📜 History", "menu_history", style="primary"),
                                   p_btn("👤 Profile", "menu_account", style="primary")]])


async def send_refer_earn(e, uid):
    ensure_user(uid)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{uid}"
    refs = cur.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,)).fetchone()[0]
    pct = spl_get_setting("ref_percent", "0")
    msg = ("🎁 <b>Refer &amp; Earn</b>\n"
           "━━━━━━━━━━━━━━━━━━━━\n"
           f"Share your link and earn <b>{html.escape(str(pct))}%</b> of your referrals' deposits.\n\n"
           f"🔗 <code>{link}</code>\n\n"
           f"👥 Your referrals: <b>{refs}</b>")
    await e.respond(msg, link_preview=False)


async def send_promo_giveaway(e, uid):
    msg = (f"{P_GIFT} <b>Promo &amp; Giveaways</b>\n\n"
           "• Tap <b>Claim Promo Code</b> and send your code to get balance.\n"
           "• Giveaways are announced in our channel — join from the announcement post.")
    await e.respond(msg, buttons=[[p_btn("🎁 Claim Promo Code", "claim_promo", style="success")],
                                  [p_btn("Main Menu", "menu_main", style="primary")]])


async def send_support(e, uid):
    url = get_support_url()
    await e.respond("🆘 <b>Need help?</b>\nTap below to contact support.",
                    buttons=[[p_btn("💬 Contact Support", url=url, style="primary")]])


REPLY_LOCAL_HANDLERS = {
    "@sell_prices": send_sell_price_list,
    "@stats": send_user_stats,
    "@refer": send_refer_earn,
    "@promo": send_promo_giveaway,
    "@support": send_support,
}


async def auto_otp_task(phone):
    if phone not in active_orders: return
    order = active_orders[phone]
    is_lzt = str(phone).startswith("LZT_")
    start_time, uid, msg_id = order['start_time'], order['uid'], order['msg_id']

    if is_lzt:
        item_id = phone.split("_")[1]
        while time.time() - start_time < AUTO_CANCEL_SECONDS:
            if phone not in active_orders: return
            try:
                code, verified, res = await get_verified_lzt_otp(item_id, attempts=2, delay=1)
                if code and not order.get('otp_sent'):
                    order['otp_sent'] = True
                    async with get_user_lock(uid):
                        cur.execute("UPDATE orders SET otp=? WHERE phone=? AND user_id=? AND server='Server 1'", (code, order.get('phone_num') or normalize_lzt_phone(None, item_id), uid))
                        db.commit()

                    display_phone = order.get('phone_num') or normalize_lzt_phone(None, item_id)
                    msg_text = (f"{P_YES} <b>Latest OTP Fetched (Server 1)!</b>\n\n"
                                f"{P_PHONE} <b>Phone:</b> <code>{display_phone}</code>\n"
                                f"{P_TIME} <b>OTP:</b> <code>{code}</code>\n"
                                f"{P_SHIELD} <b>Server 1 double-check:</b> {'Verified' if verified else 'Best latest code'}")
                    btns = [
                        [p_btn("🔄 Read Again / Get OTP", f"lzt_get_otp|{phone}", style="success"), p_btn("🚪 Logout & Finish", f"logout_finish|{phone}", style="danger")],
                        [p_btn("📜 Order History", "menu_history", style="primary"), p_btn("💳 Deposit Balance", "menu_deposit", style="success")],
                        [p_btn("⬅️ Main Menu", "menu_main", style="primary")]
                    ]
                    try: await bot.edit_message(uid, msg_id, msg_text, buttons=btns)
                    except: pass
                    return
            except: pass
            await asyncio.sleep(10)
    else:
        client = order['client']
        seller_id = order.get('seller_id')
        while time.time() - start_time < AUTO_CANCEL_SECONDS:
            if phone not in active_orders: return
            try:
                code = await get_latest_telegram_login_otp(client, start_time)
                if code and not order['paid']:
                    order['paid'] = True
                    price = order['price']
                    async with get_user_lock(uid):
                        cur.execute("INSERT INTO orders (user_id, country, year, price, phone, otp) VALUES (?,?,?,?,?,?)", (uid, order['country'], order['year'], price, phone, code))
                        cur.execute("DELETE FROM stock WHERE phone=?", (phone,))
                        cur.execute("DELETE FROM pending_orders WHERE phone=?", (phone,))
                        db.commit()

                    if seller_id:
                        seller_cut = int(price * 0.90)
                        update_balance(seller_id, seller_cut, "sales_balance")
                        try: await bot.send_message(seller_id, f"{P_GIFT} <b>Account Sold!</b>\nYour uploaded number +{phone} was just sold. {P_CASH}{seller_cut} has been added to your Sales Balance!")
                        except: pass

                    twofa_text = f"{P_SHIELD} <b>2FA:</b> <code>{order['twofa']}</code>" if order['twofa'] != "None" else f"🔓 <b>2FA:</b> <code>Disabled</code>"
                    display_phone = f"+{phone.lstrip('+')}"
                    msg_text = f"{P_YES} <b>Latest OTP Fetched!</b>\n\n{P_PHONE} <b>Phone:</b> <code>{display_phone}</code>\n{P_FLAG} <b>Country:</b> {order['c_icon']} {order['country']}\n{P_TIME} <b>OTP:</b> <code>{code}</code>\n{twofa_text}"
                    btns = [
                        [p_btn("🔄 Read Again / Get OTP", f"get_otp_again|{phone}", style="success"), p_btn("🚪 Logout & Finish", f"logout_finish|{phone}", style="danger")],
                        [p_btn("📜 Order History", "menu_history", style="primary"), p_btn("💳 Deposit Balance", "menu_deposit", style="success")],
                        [p_btn("⬅️ Main Menu", "menu_main", style="primary")]
                    ]
                    try: await bot.edit_message(uid, msg_id, msg_text, buttons=btns)
                    except: pass
                    return
            except: pass
            await asyncio.sleep(6)

    if phone in active_orders and not active_orders[phone]['paid']:
        order = active_orders.pop(phone)
        if not is_lzt:
            try: await order['client'].disconnect()
            except: pass
            async with get_user_lock(uid):
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (order['price'], uid))
                cur.execute("UPDATE stock SET available=1 WHERE phone=?", (phone,))
                cur.execute("DELETE FROM pending_orders WHERE phone=?", (phone,))
                db.commit()
        else:
            async with get_user_lock(uid):
                update_balance(uid, order['price'])
        try: await bot.edit_message(uid, msg_id, f"{P_TIME} <b>Order Expired!</b>\nThe limit ran out. Your money (₹{order['price']}) has been refunded.")
        except: pass

async def sell_hold_task(phone):
    await asyncio.sleep(600)
    if phone not in selling_accounts: return

    st = selling_accounts[phone]
    client = st['client']
    uid = st['uid']

    if st.get('cancelled'): return

    try:
        auths = await client(GetAuthorizationsRequest())
        if len(auths.authorizations) > 1:
            msg = f"{P_NO} <b>Sell Rejected!</b>\nNumber: {phone}\nReason: You did not delete your other active sessions.\nClick below to retrieve your account."
            try: await bot.edit_message(uid, st['msg_id'], msg, buttons=[[p_btn("Get Login Info", f"sell_get|{phone}")]])
            except: pass
        else:
            base_val = st['p_s'] if st['is_spam'] else st['p_n']
            cur.execute("INSERT OR REPLACE INTO stock (phone, session_file, country_name, country_icon, account_year, category, price, available, twofa, seller_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (phone, f"sessions/{phone}.session", st['c_name'], st['c_icon'], st['year'], 'Good', base_val, 1, st['new_pass'], uid))
            db.commit()

            admin_cut = int(base_val * 0.10)
            user_payout = base_val - admin_cut

            me = await bot.get_me()
            promo_link = f"https://t.me/{me.username}?start=buy_{phone}"

            msg = f"{P_YES} <b>Upload Completed!</b>\nNumber: {phone} passed all checks and is live on Server 2.\n💰 List Price: {P_CASH}{base_val}\n🔗 Promo Link: <code>{promo_link}</code>\n\n<i>You will receive {P_CASH}{user_payout} in your Sales Balance when it sells.</i>"
            try: await bot.edit_message(uid, st['msg_id'], msg)
            except: await bot.send_message(uid, msg)

            await client.disconnect()
            selling_accounts.pop(phone, None)
    except Exception as e:
        try: await bot.send_message(uid, f"{P_NO} Error finalizing sale for {phone}: {e}")
        except: pass
        selling_accounts.pop(phone, None)
        try: client.disconnect()
        except: pass

# ================= AUTOMATIC PAYMENT TASKS =================
async def check_upi_expiry_loop(order_id, uid, qr_msg_id):
    await asyncio.sleep(300)
    row = cur.execute("SELECT status FROM upi_orders WHERE order_id=?", (order_id,)).fetchone()
    if row and row[0] == "pending":
        cur.execute("UPDATE upi_orders SET status='expired' WHERE order_id=?", (order_id,))
        db.commit()
        try:
            await bot.delete_messages(uid, [qr_msg_id])
            await bot.send_message(uid, f"{P_TIME} <b>Payment Session Expired!</b>\nTransaction window closed. Request a new QR to deposit.")
        except:
            pass


async def query_upi_payment_success(order_id):
    verify_url = f"https://redoxng.in/api/verify.php?orderId={order_id}&mid={UPI_MID}"
    async with aiohttp.ClientSession() as session:
        async with session.get(verify_url, timeout=15) as resp:
            data = await resp.json()
            if not isinstance(data, dict):
                return False
            status_str = str(data.get("status", "")).upper()
            txn_status = str(data.get("data", {}).get("status", "")).upper() if isinstance(data.get("data"), dict) else ""
            return status_str in ("TXN_SUCCESS", "SUCCESS", "COMPLETED") or txn_status in ("TXN_SUCCESS", "SUCCESS", "COMPLETED")

async def complete_upi_order(order_id, uid, amount, qr_msg_id, edit_event=None):
    async with get_user_lock(uid):
        current_status = cur.execute("SELECT status FROM upi_orders WHERE order_id=?", (order_id,)).fetchone()[0]
        if current_status != "pending":
            return current_status == "success"
        user_old_bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
        cur.execute("UPDATE upi_orders SET status='success' WHERE order_id=?", (order_id,))
        update_balance(uid, amount)
        cur.execute("UPDATE users SET total_deposited = total_deposited + ? WHERE user_id=?", (amount, uid))
        db.commit()

    user_new_bal = user_old_bal + amount
    succ_msg = (f"{P_YES} <b>PAYMENT VERIFICATION SUCCESSFUL</b>\n\n"
                f"<tg-emoji emoji-id='5890848474563352982'>🪙</tg-emoji> Added: <b>₹{amount}</b>\n"
                f"<tg-emoji emoji-id='6048407885233263063'>♾</tg-emoji> Old Balance: {format_price(uid, user_old_bal)}\n"
                f" <tg-emoji emoji-id='6035305550625902723'>💬</tg-emoji> New Balance: {format_price(uid, user_new_bal)}")
    try:
        await bot.delete_messages(uid, [qr_msg_id])
    except Exception:
        pass
    await log_primary_deposit(uid, amount, "UPI (Automated)")
    await process_referral_bonus(uid, amount)
    try:
        await bot.send_message(uid, succ_msg)
    except Exception:
        pass
    if edit_event:
        try:
            await edit_event.edit(f"✅ Payment auto-verified. ₹{amount} added to your wallet.", buttons=[[p_btn("Back to Menu", "menu_main")]])
        except Exception:
            pass
    return True

async def auto_verify_upi_loop(order_id, uid, qr_msg_id):
    for _ in range(30):
        row = cur.execute("SELECT user_id, amount, status, qr_msg_id FROM upi_orders WHERE order_id=?", (order_id,)).fetchone()
        if not row or row[2] != "pending":
            return
        try:
            if await query_upi_payment_success(order_id):
                await complete_upi_order(order_id, uid, row[1], qr_msg_id)
                return
        except Exception as err:
            logger.info("UPI auto verify pending for %s: %s", order_id, err)
        await asyncio.sleep(10)

    row = cur.execute("SELECT status FROM upi_orders WHERE order_id=?", (order_id,)).fetchone()
    if row and row[0] == "pending":
        cur.execute("UPDATE upi_orders SET status='expired' WHERE order_id=?", (order_id,))
        db.commit()
        try:
            await bot.delete_messages(uid, [qr_msg_id])
            await bot.send_message(uid, f"{P_TIME} <b>Payment Session Expired!</b>\nTransaction window closed. Request a new QR to deposit.")
        except Exception:
            pass

# ================= DEPOSIT HELPERS =================
async def cleanup_deposit_media(uid):
    msg_ids = deposit_media_messages.pop(uid, [])
    if not isinstance(msg_ids, list):
        msg_ids = [msg_ids]
    for msg_id in msg_ids:
        try:
            await bot.delete_messages(uid, [msg_id])
        except Exception:
            pass
    return msg_ids

def callback_message_id(e):
    for attr in ("message_id", "msg_id", "id"):
        value = getattr(e, attr, None)
        if value:
            return value
    query = getattr(e, "query", None)
    for attr in ("msg_id", "message_id"):
        value = getattr(query, attr, None)
        if value:
            return value
    return None

def build_deposit_menu_buttons():
    btns = []
    if is_method_on("upi_status"):
        btns.append([p_btn("🟢 UPI ", "dep_upi", style="success")])
    if is_method_on("cwallet_status"):
        btns.append([p_btn("🟡 Cwallet", "depm_Cwallet", style="danger")])
    for c in cur.execute("SELECT MIN(name) FROM custom_payments WHERE LOWER(name)!='cwallet' GROUP BY LOWER(name) ORDER BY MIN(id)").fetchall():
        btns.append([p_btn(f"🟡 {c[0]}", f"depm_{c[0]}",style="danger")])
    btns.append([p_btn("Back", "menu_main")])
    return btns

async def init_upi_keypad(e):
    uid = e.sender_id
    deposit_input[uid] = ""
    min_row = cur.execute("SELECT value FROM settings WHERE key='min_upi_dep'").fetchone()
    min_dep = int(min_row[0]) if min_row else 10
    msg = (f"{P_BANK} <b>UPI Auto Deposit</b>\n\n"
           f"Enter amount using keypad.\n"
           f"Min: {P_CASH}{min_dep} | Max: {P_CASH}50000\n\n"
           f"Current: <code>0</code>")
    btns = [
        [p_btn("1", "kp_1"), p_btn("2", "kp_2"), p_btn("3", "kp_3")],
        [p_btn("4", "kp_4"), p_btn("5", "kp_5"), p_btn("6", "kp_6")],
        [p_btn("7", "kp_7"), p_btn("8", "kp_8"), p_btn("9", "kp_9")],
        [p_btn("⌫", "kp_del"), p_btn("0", "kp_0"), p_btn("✅ Continue", "kp_ok")],
        [p_btn("Cancel", "menu_deposit")]
    ]
    await e.edit(msg, buttons=btns)

async def keypad_logic(e):
    uid = e.sender_id
    action = e.data.decode().replace("kp_", "")
    cur_val = deposit_input.get(uid, "")
    min_row = cur.execute("SELECT value FROM settings WHERE key='min_upi_dep'").fetchone()
    min_dep = int(min_row[0]) if min_row else 10

    if action.isdigit():
        if len(cur_val) < 6:
            cur_val += action
    elif action == "del":
        cur_val = cur_val[:-1]
    elif action == "ok":
        if not cur_val.isdigit():
            return await e.answer("Enter valid amount", alert=True)
        amt = int(cur_val)
        if amt < min_dep or amt > 50000:
            return await e.answer(f"Amount must be between ₹{min_dep} and ₹50000", alert=True)

        order_id = f"UPI{uid}{int(time.time())}"
        gen_url = f"https://redoxng.in/api/genqr.php?upi={UPI_ID}&amount={amt}&name=FreshTG&orderId={order_id}"
        await e.edit(f"{P_TIME} Generating secure QR code...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(gen_url, timeout=15) as resp:
                    data = await resp.json()
                    if not data.get("success"):
                        raise Exception(f"Redox QR error: {data.get('message', 'Unknown api failure')}")
                    qr_image_url = data.get("url") or data.get("qr_image") or data.get("data", {}).get("qr_image") or data.get("data", {}).get("url")
        except Exception as err:
            await send_admin_error("Redox QR Generation Failed", f"{err}")
            return await e.edit(f"{P_NO} System was unable to process QR creation. Please try again later.", buttons=[[p_btn("Back", "menu_main")]])

        cur.execute("INSERT INTO upi_orders (order_id, user_id, amount, status, qr_msg_id) VALUES (?,?,?,?,?)", (order_id, uid, amt, "pending", 0))
        db.commit()

        msg = (f"{P_CARD} <b>Secure UPI Checkout (5-Minute Expiry)</b>\n\n"
               f"{P_CASH} Amount: <b>₹{amt}</b>\n"
               f"{P_ID} Order ID: <code>{order_id}</code>\n\n"
               f"1) Scan the QR below with your payment application.\n"
               f"2) Process exact transaction values.\n"
               f"3) Bot will verify automatically and credit your wallet.\n\n"
               f"<i>QR will be removed after checkout or timeout.</i>")

        deposit_input.pop(uid, None)
        qr_msg = await bot.send_file(uid, qr_image_url, caption=msg, parse_mode='html')

        cur.execute("UPDATE upi_orders SET qr_msg_id=? WHERE order_id=?", (qr_msg.id, order_id))
        db.commit()

        await e.edit(f"{P_YES} QR generated. Payment will be verified automatically within 5 minutes.", buttons=[[p_btn("Back", "menu_main")]])
        asyncio.create_task(auto_verify_upi_loop(order_id, uid, qr_msg.id))
        return

    deposit_input[uid] = cur_val
    amount_text = cur_val if cur_val else "0"
    msg = (f"{P_BANK} <b>UPI Auto Deposit</b>\n\n"
           f"Enter amount using keypad.\n"
           f"Min: {P_CASH}{min_dep} | Max: {P_CASH}50000\n\n"
           f"Current: <code>{amount_text}</code>")
    btns = [
        [p_btn("1", "kp_1"), p_btn("2", "kp_2"), p_btn("3", "kp_3")],
        [p_btn("4", "kp_4"), p_btn("5", "kp_5"), p_btn("6", "kp_6")],
        [p_btn("7", "kp_7"), p_btn("8", "kp_8"), p_btn("9", "kp_9")],
        [p_btn("⌫", "kp_del"), p_btn("0", "kp_0"), p_btn("✅ Continue", "kp_ok")],
        [p_btn("Cancel", "menu_deposit")]
    ]
    await e.edit(msg, buttons=btns)

async def verify_upi_payment(e, order_id):
    uid = e.sender_id
    row = cur.execute("SELECT user_id, amount, status, qr_msg_id FROM upi_orders WHERE order_id=?", (order_id,)).fetchone()
    if not row or row[0] != uid:
        return await safe_answer_cb(e, "Invalid checkout reference.", alert=True)
    if row[2] == "success":
        return await safe_answer_cb(e, "Transaction verified already.", alert=True)
    if row[2] == "expired":
        return await safe_answer_cb(e, "This checkout context expired.", alert=True)

    try:
        is_success = await query_upi_payment_success(order_id)
    except Exception as err:
        await send_admin_error("Redox Transaction Check Error", f"{err}")
        return await safe_answer_cb(e, "Network verification gateway busy. Auto-check is still running.", alert=True)

    if is_success:
        await complete_upi_order(order_id, uid, row[1], row[3], edit_event=e)
        return

    await safe_answer_cb(e, "Payment not found yet. Auto-check is running; no need to press again.", alert=True)

async def manual_deposit_init(e, method_name):
    uid = e.sender_id
    await cleanup_deposit_media(uid)
    min_row = cur.execute("SELECT value FROM settings WHERE key='min_cw_dep'").fetchone()
    min_dep = int(min_row[0]) if min_row else 10

    manual_dep_state[uid] = {"method": method_name, "step": "wait_amount"}

    msg = (f"📥 <b>{html.escape(method_name)} Deposit Initiation</b>\n\n"
           f"Please reply with the exact amount you wish to deposit in INR (Min {P_CASH}{min_dep}):")
    await e.edit(msg, buttons=[[p_btn("Cancel", "menu_deposit")]])


async def render_giveaway(event, gid):
    row = cur.execute("SELECT prize_name, ticket_price, min_participants, winners_count, status FROM giveaways WHERE id=?", (gid,)).fetchone()
    if not row:
        return await safe_show_message(event, "❌ Giveaway not found.", buttons=[[p_btn("Main Menu", "menu_main")]])
    prize, ticket_price, min_participants, winners_count, status = row
    stats = cur.execute("SELECT COUNT(*), COALESCE(SUM(tickets),0) FROM giveaway_tickets WHERE giveaway_id=?", (gid,)).fetchone()
    users_count, tickets_count = stats if stats else (0, 0)
    text = (f"🎁 <b>Giveaway: {html.escape(prize)}</b>\n\n"
            f"🎟 Ticket price: <b>₹{ticket_price}</b>\n"
            f"👥 Participants: <b>{users_count}/{min_participants}</b>\n"
            f"🎫 Total tickets: <b>{tickets_count}</b>\n"
            f"🏆 Winners: <b>{winners_count}</b>\n"
            f"📌 Status: <b>{status.upper()}</b>\n\n"
            f"Buy more tickets to increase your winning chance.")
    btns = []
    if status == "open":
        btns.append([p_btn("🎟 Buy 1 Ticket", f"g_buy|{gid}|1"), p_btn("🎟 Buy 5", f"g_buy|{gid}|5")])
        btns.append([p_btn("🎟 Buy 10", f"g_buy|{gid}|10"), p_btn("✍️ Custom Tickets", f"g_custom|{gid}")])
    btns.append([p_btn("Main Menu", "menu_main")])
    return await safe_show_message(event, text, buttons=btns)

async def maybe_finish_giveaway(gid):
    row = cur.execute("SELECT prize_name, ticket_price, min_participants, winners_count, status, created_by FROM giveaways WHERE id=?", (gid,)).fetchone()
    if not row or row[4] != "open":
        return
    prize, ticket_price, min_participants, winners_count, status, created_by = row
    participants = cur.execute("SELECT user_id, tickets FROM giveaway_tickets WHERE giveaway_id=? AND tickets>0", (gid,)).fetchall()
    if len(participants) < min_participants:
        return
    weighted = []
    for user_id, tickets in participants:
        weighted.extend([user_id] * max(1, int(tickets)))
    winners = []
    while weighted and len(winners) < min(winners_count, len(participants)):
        winner = random.choice(weighted)
        if winner not in winners:
            winners.append(winner)
        weighted = [x for x in weighted if x != winner]
    cur.execute("UPDATE giveaways SET status='closed' WHERE id=?", (gid,))
    db.commit()
    winner_lines = []
    for wid in winners:
        try:
            ent = await bot.get_entity(wid)
            uname = f"@{ent.username}" if getattr(ent, 'username', None) else "No username"
            name = html.escape(ent.first_name or str(wid))
        except Exception:
            uname, name = "No username", str(wid)
        winner_lines.append(f"🏆 <code>{wid}</code> {name} {uname} tg://user?id={wid}")
    announce = (f"🎉 <b>Giveaway Ended!</b>\n\nPrize: <b>{html.escape(prize)}</b>\n"
                f"Participants: <b>{len(participants)}</b>\nTickets: <b>{sum(t for _, t in participants)}</b>\n\n"
                f"<b>Winner(s):</b>\n" + "\n".join(winner_lines) + "\n\nAdmin will deliver prize manually.")
    for user_id, _ in participants:
        try:
            await bot.send_message(user_id, announce)
        except Exception:
            pass
    try:
        await bot.send_message(created_by or ADMIN_ID, announce)
    except Exception:
        pass

# ================= DYNAMIC ADMIN REVIEW KEYPAD =================
async def render_admin_review_keypad(event, target_uid, order_id, d_type, current_val=""):
    display_text = current_val if current_val else "0"
    method_label = "UPI Automatic" if d_type == "upi" else "Manual"
    if d_type == "man":
        row = cur.execute("SELECT method_name FROM deposits WHERE id=?", (str(order_id).replace("M", ""),)).fetchone()
        if row and row[0]:
            method_label = row[0]
    msg = (f"✏️ <b>Console Keypad Review Mode</b>\n\n"
           f"Payment Type: <b>{html.escape(method_label)}</b>\n"
           f"User ID: <code>{target_uid}</code>\n"
           f"Transaction ID: <code>{order_id}</code>\n"
           f"Pending Credit Value: <b>₹{display_text}</b>\n\n"
           f"Update final deposit values to credit:")

    cb_pref = f"kp_adm|{target_uid}|{order_id}|{d_type}|"
    btns = [
        [
            p_btn("1", f"{cb_pref}1|{current_val}"),
            p_btn("2", f"{cb_pref}2|{current_val}"),
            p_btn("3", f"{cb_pref}3|{current_val}")
        ],
        [
            p_btn("4", f"{cb_pref}4|{current_val}"),
            p_btn("5", f"{cb_pref}5|{current_val}"),
            p_btn("6", f"{cb_pref}6|{current_val}")
        ],
        [
            p_btn("7", f"{cb_pref}7|{current_val}"),
            p_btn("8", f"{cb_pref}8|{current_val}"),
            p_btn("9", f"{cb_pref}9|{current_val}")
        ],
        [
            p_btn("⌫", f"{cb_pref}del|{current_val}", style="primary"),
            p_btn("0", f"{cb_pref}0|{current_val}"),
            p_btn("✅ Confirm", f"{cb_pref}confirm|{current_val}", style="success"),
        ],
        [p_btn("❌ Reject / Cancel", f"dep_act|{d_type}|rej|{order_id}|{target_uid}|0", style="danger")]
    ]
    await event.edit(msg, buttons=btns)

# ================= DYNAMIC SUB-ADMIN PERMISSIONS RENDERER =================
async def edit_admin_menu(event, admin_id):
    row = cur.execute("SELECT p_add_stock, p_manage_stock, p_stats, p_bal, p_settings FROM admins WHERE user_id=?", (admin_id,)).fetchone()
    if not row:
        cur.execute("INSERT INTO admins (user_id) VALUES (?)", (admin_id,))
        db.commit()
        row = (0, 0, 0, 0, 0)

    p_add, p_manage, p_stats, p_bal, p_settings = row

    msg = (f"👤 <b>Manage Admin Permissions</b>\n\n"
           f"Admin ID: <code>{admin_id}</code>\n\n"
           f"➕ Add Stock: {'✅ Enabled' if p_add else '❌ Disabled'}\n"
           f"⚙️ Manage Stock: {'✅ Enabled' if p_manage else '❌ Disabled'}\n"
           f"📊 View Stats: {'✅ Enabled' if p_stats else '❌ Disabled'}\n"
           f"💰 Manage Balances: {'✅ Enabled' if p_bal else '❌ Disabled'}\n"
           f"🛠️ Settings Access: {'✅ Enabled' if p_settings else '❌ Disabled'}")

    btns = [
        [p_btn("Toggle Add Stock", f"adm_perm|{admin_id}|p_add_stock|{p_add}", style="primary")],
        [p_btn("Toggle Manage Stock", f"adm_perm|{admin_id}|p_manage_stock|{p_manage}", style="primary")],
        [p_btn("Toggle Stats", f"adm_perm|{admin_id}|p_stats|{p_stats}", style="primary")],
        [p_btn("Toggle Balance", f"adm_perm|{admin_id}|p_bal|{p_bal}", style="primary")],
        [p_btn("Toggle Settings", f"adm_perm|{admin_id}|p_settings|{p_settings}", style="primary")],
        [p_btn("🗑️ Delete Admin", f"adm_perm|{admin_id}|delete|0", style="danger")],
        [p_btn("Back to Dashboard", "adm_adminmain", style="danger")]
    ]

    if hasattr(event, 'edit'):
        await event.edit(msg, buttons=btns)
    else:
        await bot.send_message(ADMIN_ID, msg, buttons=btns)


async def render_lzt_product(e, uid, item_id, country=None):
    res = await lzt_request('GET', f"/{item_id}", params=lzt_currency_params())
    if not res or 'item' not in res:
        return await safe_show_message(e, "❌ Unable to load Server 1 product. It may be sold or unavailable.", buttons=[[p_btn("Server 1", "srv_1_pg|1")]])
    item = res['item']
    country = country or lzt_item_country_name(item, "Unknown")
    price_info = lzt_price_breakdown(item, get_lzt_markup(country))
    final_price = price_info["final_inr"]
    spam = item.get("telegram_spam_block", -1)
    premium = item.get("telegram_premium", 0)
    contacts = item.get("telegram_contacts_count", 0)
    chats = item.get("telegram_chats_count", 0)
    channels = item.get("telegram_channels_count", 0)
    conv = item.get("telegram_conversations_count", 0)
    bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
    diff = final_price - bal
    password_required = lzt_item_requires_password(item)
    msg = (f"{P_STORE} <b>Confirm Server 1 Purchase</b>\n\n"
           f"{P_CASH} <b>Price:</b> {format_price(uid, final_price)}\n"
           f"{P_CARD} <b>Your Balance:</b> {format_price(uid, bal)}\n"
           f"<tg-emoji emoji-id='5778613750688911681'>🪙</tg-emoji> <b>Country:</b> {html.escape(country)}\n"
           f"<tg-emoji emoji-id='6035191085452497972'>👤</tg-emoji> <b>ID:</b> <code>{item_id}</code>\n\n"
           f" <tg-emoji emoji-id='6037175527846975726'>🎁</tg-emoji> Premium: <b>{'YES' if premium else 'NO'}</b>\n"
           f"<tg-emoji emoji-id='6037254263187443802'>💬</tg-emoji> SpamBlock: <b>{'NO' if spam == -1 else 'YES'}</b>\n"
           f" <tg-emoji emoji-id='5767388406984216738'>💬</tg-emoji> Chats: <b>{chats}</b>\n"
           f"<tg-emoji emoji-id='6039422865189638057'>📣</tg-emoji> Channels: <b>{channels}</b>\n"
           f"<tg-emoji emoji-id='6032594876506312598'>👥</tg-emoji> Contacts: <b>{contacts}</b>\n"
           f" <tg-emoji emoji-id='5776233299424843260'>🌐</tg-emoji> Conversations: <b>{conv}</b>\n\n"
           f"<tg-emoji emoji-id='5920332557466997677'>🏪</tg-emoji> <b>Mass Buy:</b> tries this ID first, then same-price IDs until one succeeds or all fail.")
    btns = []
    iso_code = COUNTRY_CODES.get(country, ("US", "🇺🇸"))[0]
    if password_required:
        btns.append([p_btn("🔐 Password Account - Cannot Buy", "noop")])
    elif diff > 0:
        btns.append([p_btn("Need Recharge", "menu_deposit")])
    else:
        btns.append([p_btn("✅ Purchase", f"lzt_buy|{item_id}|{final_price}|{country}")])
        btns.append([p_btn("🛒 Mass Buy Same Price", f"lzt_mass_buy|{item_id}|{final_price}|{country}")])
    btns.extend([
        [p_btn("⬅ Back to Stocks", f"lzt_chk|{iso_code}|1")],
        [p_btn("Back to Menu", "menu_main")]
    ])
    return await safe_show_message(e, msg, buttons=btns)


async def get_lzt_candidate_items(country, target_final_price, preferred_item_id=None, max_pages=2):
    # Use safe default market filters and exact displayed INR price for mass-buy candidates.
    iso_code = COUNTRY_CODES.get(country, ("US", "🇺🇸"))[0]
    seen = set()
    candidates = []

    async def add_candidate(item):
        if not isinstance(item, dict):
            return
        item_id = str(item.get('item_id') or item.get('id') or '')
        if not item_id or item_id in seen:
            return
        seen.add(item_id)
        candidates.append(item)

    if preferred_item_id:
        res = await lzt_request('GET', f"/{preferred_item_id}", params=lzt_currency_params())
        if isinstance(res, dict) and isinstance(res.get('item'), dict):
            await add_candidate(res['item'])

    params_base = {
        "country[]": iso_code,
        "nsb": 1,
        "pmin": 0.01,
        "pmax": 1000,
        "per_page": 40,
        "password": "no",
        "currency": LZT_PRICE_CURRENCY,
    }
    for page in range(1, max_pages + 1):
        params = dict(params_base, page=page)
        res = await lzt_request('GET', '/telegram', params=params, timeout_total=LZT_STOCK_TIMEOUT, max_retries=LZT_STOCK_RETRIES, notify_errors=False)
        if isinstance(res, dict) and 'items' in res and not res.get('items') and params["country[]"] != country:
            params["country[]"] = country
            res = await lzt_request('GET', '/telegram', params=params, timeout_total=LZT_STOCK_TIMEOUT, max_retries=1, notify_errors=False)
        for item in (res or {}).get('items', [])[:40]:
            if lzt_final_inr_price(item, get_lzt_markup(country)) == int(target_final_price):
                await add_candidate(item)
    return candidates

async def finish_lzt_purchase_success(uid, item_id, country, final_price):
    res = await lzt_request('GET', f"/{item_id}", params=lzt_currency_params())
    phone_num = f"LZT_{item_id}"
    if res and 'item' in res:
        item = res['item']
        phone_num = item.get('phone') or item.get('telegram_phone') or item.get('login') or f"LZT_{item_id}"
    display_phone = normalize_lzt_phone(phone_num, item_id)
    phone = f"LZT_{item_id}"
    cur.execute(
        "INSERT INTO orders (user_id, country, year, price, phone, otp, server) VALUES (?,?,?,?,?,?,?)",
        (uid, country, 2024, final_price, display_phone, None, "Server 1")
    )
    db.commit()
    await log_primary_purchase(uid, country, final_price, final_price, 2024, 1, display_phone, "Server 1")
    await try_lzt_reset_authorizations(item_id)
    return phone, display_phone

# ================= CORE EVENT CALLBACKS =================
@bot.on(events.CallbackQuery)
async def handle_callbacks(e):
    global cached_lzt_stock, active_filter_keys
    uid = e.sender_id
    data = e.data.decode()
    if not callback_allowed_in_chat(uid, data, e):
        return await safe_answer_cb(e, "User menus work in private chat only. Admin review buttons are allowed for admins in log chats.", alert=True)
    if not is_bot_online() and not is_admin(uid): return await e.answer("Maintenance.", alert=True)
    ensure_user(uid)
    if is_user_banned(uid): return await e.answer("BANNED", alert=True)

    try:
        if data == "noop":
            return await safe_answer_cb(e, "Not available.", alert=True)

        # Permission Handling Callback
        if data.startswith("adm_perm|") and uid == ADMIN_ID:
            _, admin_id, perm, val = data.split("|")
            admin_id, val = int(admin_id), int(val)
            if perm == "delete":
                cur.execute("DELETE FROM admins WHERE user_id=?", (admin_id,))
                db.commit()
                await e.answer("Admin deleted successfully", alert=True)
                class FakeEvent:
                    async def edit(self, text, buttons): await e.edit(text, buttons=buttons)
                await handle_callbacks(FakeEvent())
                return
            else:
                new_val = 1 if val == 0 else 0
                cur.execute(f"UPDATE admins SET {perm}=? WHERE user_id=?", (new_val, admin_id))
                db.commit()
                await e.answer("Permission toggled", alert=False)
                class FakeEvent:
                    async def edit(self, text, buttons): await e.edit(text, buttons=buttons)
                await edit_admin_menu(FakeEvent(), admin_id)
                return

        # Giveaway Join Callback
        elif data.startswith("join_gwy|"):
            _, gwy_id, amt_str = data.split("|")
            amt = int(amt_str)

            if gwy_id not in active_giveaways:
                return await safe_answer_cb(e, "❌ This giveaway pool has already expired or ended.", alert=True)

            pool = active_giveaways[gwy_id]
            if uid in pool["participants"]:
                return await safe_answer_cb(e, "❌ You have already participated in this pool!", alert=True)

            pool["participants"].append(uid)
            count = len(pool["participants"])

            current_users = []
            for u in pool["participants"]:
                try:
                    user_ent = await bot.get_entity(u)
                    current_users.append(html.escape(user_ent.first_name or "Participant"))
                except:
                    current_users.append(f"User_{u}")

            list_text = "\n".join([f"• {u}" for u in current_users])

            if count >= 10:
                winner_id = random.choice(pool["participants"])
                winner_ent = await bot.get_entity(winner_id)
                winner_name = html.escape(winner_ent.first_name or "Participant")

                update_balance(winner_id, amt)
                active_giveaways.pop(gwy_id, None)

                complete_text = (f"{P_TADA} <b>GIVEAWAY POOL COMPLETED!</b>\n\n"
                                 f"🎁 Prize Value: <b>₹{amt}</b>\n"
                                 f"👥 Participants: {count}/10\n\n"
                                 f"🏆 <b>Winner Chosen:</b> {winner_name} (₹{amt} added directly to balance!)")
                await e.edit(complete_text, buttons=None)
                return

            updated_text = (f"{P_GIFT} <b>ACTIVE GIVEAWAY DISBURSEMENT STARTED!</b>\n\n"
                            f"Pool Prize: <b>₹{amt}</b>\n"
                            f"Active slots: <b>{count} / 10 Joined</b>\n\n"
                            f"<b>Joined users:</b>\n{list_text}\n\n"
                            f"Click join below to participate:")

            btns = [[p_btn(f"🙋 Join Giveaway ({count}/10)", f"join_gwy|{gwy_id}|{amt}")]]
            await e.edit(updated_text, buttons=btns)
            return

        elif data.startswith("gwy_cf|"):
            if not is_admin(uid): return await e.answer("Admins only.", alert=True)
            amt = int(data.split("|")[1])
            gwy_id = f"GWY_{int(time.time())}"

            active_giveaways[gwy_id] = {
                "amount": amt,
                "participants": []
            }

            start_text = (f"{P_GIFT} <b>ACTIVE GIVEAWAY DISBURSEMENT STARTED!</b>\n\n"
                          f"Pool Prize: <b>₹{amt}</b>\n"
                          f"Active slots: <b>0 / 10 Joined</b>\n\n"
                          f"Click join below to participate:")
            btns = [[p_btn("🙋 Join Giveaway (0/10)", f"join_gwy|{gwy_id}|{amt}")]]
            await e.edit(start_text, buttons=btns)
            return

        elif data == "gwy_cancel":
            if not is_admin(uid): return await e.answer("Admins only.", alert=True)
            await e.edit("❌ Giveaway disbursement cancelled.")
            return

        # Group Join Fight Button Callback
        elif data.startswith("join_fight|"):
            _, fight_id, initiator_id, amount_str = data.split("|")
            initiator_id = int(initiator_id)
            amount = int(amount_str)

            fight = active_fights.pop(fight_id, None)
            if not fight:
                return await safe_answer_cb(e, "❌ This battle has expired or was already finished.", alert=True)

            if uid == fight["initiator_id"]:
                active_fights[fight_id] = fight
                return await safe_answer_cb(e, "❌ You cannot join your own fight!", alert=True)

            ensure_user(uid)
            challenger_bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
            if challenger_bal < amount:
                active_fights[fight_id] = fight
                return await safe_answer_cb(e, f"❌ Insufficient balance! (Need ₹{amount}, Current: ₹{challenger_bal})", alert=True)

            async with get_user_lock(uid):
                challenger_bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
                if challenger_bal < amount:
                    active_fights[fight_id] = fight
                    return await safe_answer_cb(e, f"❌ Insufficient balance! (Need ₹{amount}, Current: ₹{challenger_bal})", alert=True)
                cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (amount, uid, amount))
                if cur.rowcount == 0:
                    active_fights[fight_id] = fight
                    return await safe_answer_cb(e, "❌ Balance changed. Try again.", alert=True)
                if not fight.get("initiator_paid"):
                    init_bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (fight["initiator_id"],)).fetchone()[0]
                    if init_bal < amount:
                        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
                        db.commit()
                        return await e.edit("❌ Fight cancelled. Initiator no longer has enough balance.")
                    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (amount, fight["initiator_id"], amount))
                    if cur.rowcount == 0:
                        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
                        db.commit()
                        return await e.edit("❌ Fight cancelled. Initiator balance deduction failed.")
                    fight["initiator_paid"] = True
                    fight["reward"] = amount * 2
                db.commit()

            challenger_entity = await bot.get_entity(uid)
            challenger_name = html.escape(challenger_entity.first_name or "Challenger")

            combatants = [
                {"id": fight["initiator_id"], "name": fight["initiator_name"]},
                {"id": uid, "name": challenger_name}
            ]
            winner = random.choice(combatants)

            reward = fight["reward"]
            update_balance(winner["id"], reward)

            success_text = (f"{P_TADA} <b>BATTLE COMPLETED!</b>\n\n"
                            f"🤺 Initiator: {fight['initiator_name']}\n"
                            f"🛡 Challenger: {challenger_name}\n"
                            f"💰 Total Pool: <b>₹{reward}</b>\n\n"
                            f"🏆 <b>Winner:</b> {winner['name']} (₹{reward} added to balance!)")

            await e.edit(success_text)
            return


        elif data.startswith("g_open|"):
            gid = data.split("|", 1)[1]
            await render_giveaway(e, gid)
            return

        elif data.startswith("g_custom|"):
            gid = data.split("|", 1)[1]
            row = cur.execute("SELECT ticket_price, status FROM giveaways WHERE id=?", (gid,)).fetchone()
            if not row or row[1] != "open":
                return await safe_answer_cb(e, "❌ Giveaway is closed or missing.", alert=True)
            giveaway_ticket_state[uid] = gid
            await e.edit(f"🎟 <b>Custom Tickets</b>\n\n1 ticket costs ₹{row[0]}. Reply with how many tickets you want to buy.", buttons=[[p_btn("Back", f"g_open|{gid}")]])
            return

        elif data.startswith("g_buy|"):
            _, gid, qty_str = data.split("|")
            qty = int(qty_str)
            if qty <= 0 or qty > 10000:
                return await safe_answer_cb(e, "❌ Invalid ticket quantity.", alert=True)
            row = cur.execute("SELECT prize_name, ticket_price, status FROM giveaways WHERE id=?", (gid,)).fetchone()
            if not row or row[2] != "open":
                return await safe_answer_cb(e, "❌ Giveaway is closed or missing.", alert=True)
            prize, ticket_price, _ = row
            total_cost = ticket_price * qty
            async with get_user_lock(uid):
                bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
                if bal < total_cost:
                    return await safe_answer_cb(e, f"❌ Need ₹{total_cost}. Current balance ₹{bal}.", alert=True)
                cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (total_cost, uid, total_cost))
                if cur.rowcount == 0:
                    return await safe_answer_cb(e, "❌ Balance changed. Try again.", alert=True)
                cur.execute("INSERT INTO giveaway_tickets (giveaway_id, user_id, tickets) VALUES (?,?,?) ON CONFLICT(giveaway_id,user_id) DO UPDATE SET tickets=tickets+excluded.tickets", (gid, uid, qty))
                db.commit()
            await safe_answer_cb(e, f"✅ Bought {qty} ticket(s) for ₹{total_cost}.", alert=True)
            await render_giveaway(e, gid)
            await maybe_finish_giveaway(gid)
            return

        elif data == "verify_join":
            if not await check_channel_joined(uid): return await e.answer("⚠️ Join channels first!", alert=True)
            await send_terms_or_main_menu(e, uid)
        elif data == "menu_main" or data == "cancel_action":
            wd_state.pop(uid, None); sell_state.pop(uid, None); deposit_input.pop(uid, None); manual_dep_state.pop(uid, None); lzt_search_state.pop(uid, None); restore_state.pop(uid, None); giveaway_ticket_state.pop(uid, None)
            await cleanup_deposit_media(uid)
            await send_main_menu(e, uid)
        elif data == "tc_accept":
            cur.execute("UPDATE users SET terms_accepted=1 WHERE user_id=?", (uid,))
            db.commit()
            await send_main_menu(e, uid)
        elif data == "tc_reject":
            await e.edit("❌ You must accept the terms.")

        # --- BUY MENU ---
        elif data == "menu_buy":
            total_bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
            msg = ("● <b>Buy Best Telegram Accounts:</b>\n"
                   "––––––—————––––——–––•\n"
                   "• Choose Server Based Need\n"
                   "• Server 1 [Cheap Quality ]\n"
                   "• Server 2 [ High Quality ] \n"
                   f"• Total balance = <code>{format_price(uid, total_bal)}</code>")
            btns = [
                [p_btn("Server (1)", "srv_1_pg|1", style="primary")],
                [p_btn("Server (2)", "srv_2_pg|1", style="primary")],
                [p_btn("● Back ●", "menu_main")]
            ]
            await e.edit(msg, buttons=btns)

        # --- SERVER 1 (AUTOMATED GLOBAL MARKET) ---
        elif data.startswith("srv_1_pg|"):
            page = int(data.split("|")[1])
            await render_server1_country_page(e, uid, page)

        elif data == "lzt_all_countries":
            await e.answer("Sending Server 1 country list...", alert=False)
            await send_all_countries_list(uid)

        elif data == "lzt_search_country":
            lzt_search_state[uid] = True
            await e.edit(
                "<tg-emoji emoji-id='6032850693348399258'>🔎</tg-emoji> <b>Search Server 1 Country</b>\n\n"
                "Send a country key now. Examples: <code>+91</code>, <code>Ind</code>, <code>US</code>",
                buttons=[[p_btn("Back", "srv_1_pg|1")]]
            )

        elif data == "lzt_refresh_cache":
            await e.answer("Recalculating and synchronizing server stocks... Please wait.", alert=True)
            flt = get_user_filters(uid)
            fkey = get_filter_key(flt)
            active_filter_keys.add(fkey)

            sem = asyncio.Semaphore(max(1, LZT_CACHE_CONCURRENCY))
            async def quick_fetch(country_name):
                async with sem:
                    try:
                        d = await fetch_lzt_country_data_with_filters(
                            country_name, flt["spam"], flt["geoblock"], flt["offline"], flt["login_mail"], flt["premium"]
                        )
                        if fkey not in cached_lzt_stock:
                            cached_lzt_stock[fkey] = {}
                        if d is not None:
                            cached_lzt_stock[fkey][country_name] = (d[1], d[2])
                    except:
                        if fkey not in cached_lzt_stock:
                            cached_lzt_stock[fkey] = {}
            tasks = [quick_fetch(c) for c in COUNTRY_CODES.keys()]
            await asyncio.gather(*tasks)

            class FakeEv:
                data = b"srv_1_pg|1"
                sender_id = uid
                async def edit(self, text, buttons): await e.edit(text, buttons=buttons)
                async def answer(self, text, alert=False): pass
            await handle_callbacks(FakeEv())

        elif data == "lzt_toggle_filters":
            flt = get_user_filters(uid)
            msg = (f"⚙️ <b>Server 1 Search Filter Configurations</b>\n\n"
                   f"Select search properties to apply on catalog lookups:")

            spam_st = "🟢 NO SPAM" if flt["spam"] == "no" else ("🔴 ALLOW SPAM" if flt["spam"] == "yes" else "🔵 ANY")
            geo_st = "🟢 NO GEO-BLOCK" if flt["geoblock"] == "no" else ("🔴 BLOCKED" if flt["geoblock"] == "yes" else "🔵 ANY")
            mail_st = "🟢 MAIL INCLUDED" if flt["login_mail"] == "yes" else ("🔴 NO MAIL" if flt["login_mail"] == "no" else "🔵 ANY")
            offline_st = f"🔵 ≥{flt['offline']} Days" if flt['offline'] != "any" else "🔵 ANY"
            prem_st = "🟢 PREMIUM ONLY" if flt["premium"] == "yes" else ("🔴 NON-PREMIUM ONLY" if flt["premium"] == "no" else "🔵 ANY")

            btns = [
                [p_btn(f"Spam filter: {spam_st}", "flt_chg|spam")],
                [p_btn(f"Geo-block filter: {geo_st}", "flt_chg|geoblock")],
                [p_btn(f"Login Mail: {mail_st}", "flt_chg|login_mail")],
                [p_btn(f"Premium filter: {prem_st}", "flt_chg|premium")],
                [p_btn(f"Offline filter: {offline_st}", "flt_chg|offline")],
                [p_btn("✅ Apply Filters and Back", "srv_1_pg|1"), p_btn("🔄 Refresh", "lzt_refresh_cache")]
            ]
            await e.edit(msg, buttons=btns)


        elif data == "lzt_sort_menu":
            flt = get_user_filters(uid)
            current = flt.get("sort", "az")
            labels = {"az": "A-Z", "price_low": "Price Low To High", "price_high": "Price High To Low", "stock_low": "Stock Low To High", "stock_high": "Stock High To Low"}
            def mark(mode):
                return "✅ " if current == mode else ""
            btns = [
                [p_btn(f"{mark('az')}A-Z", "lzt_sort|az")],
                [p_btn(f"{mark('price_low')}Price Low To High", "lzt_sort|price_low")],
                [p_btn(f"{mark('price_high')}Price High To Low", "lzt_sort|price_high")],
                [p_btn(f"{mark('stock_low')}Stock Low To High", "lzt_sort|stock_low")],
                [p_btn(f"{mark('stock_high')}Stock High To Low", "lzt_sort|stock_high")],
                [p_btn("Back", "srv_1_pg|1")]
            ]
            await e.edit("↕️ <b>Choose Server 1 Sorting</b>\n\nThis changes the country list order only.", buttons=btns)

        elif data.startswith("lzt_sort|"):
            mode = data.split("|", 1)[1]
            if mode not in ("az", "price_low", "price_high", "stock_low", "stock_high"):
                return await safe_answer_cb(e, "Invalid sorting option.", alert=True)
            get_user_filters(uid)["sort"] = mode
            await render_server1_country_page(e, uid, 1)

        elif data.startswith("flt_chg|"):
            attrib = data.split("|")[1]
            flt = get_user_filters(uid)

            if attrib == "spam":
                flt["spam"] = "yes" if flt["spam"] == "no" else ("any" if flt["spam"] == "yes" else "no")
            elif attrib == "geoblock":
                flt["geoblock"] = "yes" if flt["geoblock"] == "no" else ("any" if flt["geoblock"] == "yes" else "no")
            elif attrib == "login_mail":
                flt["login_mail"] = "no" if flt["login_mail"] == "yes" else ("any" if flt["login_mail"] == "no" else "yes")
            elif attrib == "premium":
                flt["premium"] = "no" if flt["premium"] == "yes" else ("any" if flt["premium"] == "no" else "yes")
            elif attrib == "offline":
                flt["offline"] = "7" if flt["offline"] == "1" else ("14" if flt["offline"] == "7" else ("30" if flt["offline"] == "14" else ("any" if flt["offline"] == "30" else "1")))
            elif attrib == "sort":
                order = ["az", "stock_high", "stock_low", "price_low", "price_high"]
                flt["sort"] = order[(order.index(flt.get("sort", "az")) + 1) % len(order)] if flt.get("sort", "az") in order else "az"

            fkey = get_filter_key(flt)
            active_filter_keys.add(fkey)

            flt = get_user_filters(uid)
            msg = (f"⚙️ <b>Server 1 Search Filter Configurations</b>\n\n"
                   f"Select search properties to apply on catalog lookups:")

            spam_st = "🟢 NO SPAM" if flt["spam"] == "no" else ("🔴 ALLOW SPAM" if flt["spam"] == "yes" else "🔵 ANY")
            geo_st = "🟢 NO GEO-BLOCK" if flt["geoblock"] == "no" else ("🔴 BLOCKED" if flt["geoblock"] == "yes" else "🔵 ANY")
            mail_st = "🟢 MAIL INCLUDED" if flt["login_mail"] == "yes" else ("🔴 NO MAIL" if flt["login_mail"] == "no" else "🔵 ANY")
            offline_st = f"🔵 ≥{flt['offline']} Days" if flt['offline'] != "any" else "🔵 ANY"
            prem_st = "🟢 PREMIUM ONLY" if flt["premium"] == "yes" else ("🔴 NON-PREMIUM ONLY" if flt["premium"] == "no" else "🔵 ANY")

            btns = [
                [p_btn(f"Spam filter: {spam_st}", "flt_chg|spam")],
                [p_btn(f"Geo-block filter: {geo_st}", "flt_chg|geoblock")],
                [p_btn(f"Login Mail: {mail_st}", "flt_chg|login_mail")],
                [p_btn(f"Premium filter: {prem_st}", "flt_chg|premium")],
                [p_btn(f"Offline filter: {offline_st}", "flt_chg|offline")],
                [p_btn("✅ Apply Filters and Back", "srv_1_pg|1"), p_btn("🔄 Refresh", "lzt_refresh_cache")]
            ]
            await e.edit(msg, buttons=btns)

        elif data.startswith("lzt_chk|"):
            parts = data.split("|")
            iso_code = parts[1]
            page = int(parts[2]) if len(parts) > 2 else 1

            await e.answer("Loading interactive catalog...", alert=False)

            country = next((k for k, v in COUNTRY_CODES.items() if v[0] == iso_code), "United States")
            flag = COUNTRY_CODES.get(country, ("US", "🇺🇸"))[1]

            flt = get_user_filters(uid)
            params = {
                "country[]": iso_code,
                "spam": flt["spam"] if flt["spam"] != "any" else None,
                "nsb": 1,
                "pmin": 0.01,
                "pmax": 1000,
                "page": page,
                "per_page": 40,
                "password": "no",
                "currency": LZT_PRICE_CURRENCY
            }
            if flt["offline"] != "any":
                params["daybreak"] = int(flt["offline"])
            if flt["premium"] != "any":
                params["premium"] = flt["premium"]

            res = await lzt_request('GET', '/telegram', params=params, timeout_total=LZT_STOCK_TIMEOUT, max_retries=LZT_STOCK_RETRIES, notify_errors=False)
            if isinstance(res, dict) and 'items' in res and len(res['items']) == 0 and params["country[]"] != country:
                params["country[]"] = country
                res = await lzt_request('GET', '/telegram', params=params, timeout_total=LZT_STOCK_TIMEOUT, max_retries=1, notify_errors=False)

            if not res or 'items' not in res or len(res['items']) == 0:
                empty_msg = (f"❌ <b>Stock Empty!</b>\n\n"
                             f"There are currently no active listings for <b>{country} {flag}</b> on Server 1.\n"
                             f"Please choose another country or check back soon.")
                btns = [
                    [p_btn("🔄 Refresh Catalog Info", f"lzt_chk|{iso_code}|1")],
                    [p_btn("Change Country", "srv_1_pg|1")]
                ]
                await e.edit(empty_msg, buttons=btns)
                return

            matched_items = filter_lzt_items(res.get('items', []), flt)
            if not matched_items:
                empty_msg = (f"❌ <b>Stock Empty!</b>\n\n"
                             f"No listings matched your active filters for <b>{country} {flag}</b>.\n"
                             f"Try changing filters or choose another country.")
                btns = [
                    [p_btn("⚙️ Change Filters", "lzt_toggle_filters")],
                    [p_btn("🔄 Refresh Catalog Info", f"lzt_chk|{iso_code}|1")],
                    [p_btn("Change Country", "srv_1_pg|1")]
                ]
                await e.edit(empty_msg, buttons=btns)
                return
            items = sorted(matched_items, key=lambda x: float(x.get('price_with_fee') or x.get('priceWithSellerFee') or x.get('price') or 99999))[:40]
            total_items = res.get('totalItems', len(items)) if len(matched_items) == len(res.get('items', [])) else len(matched_items)
            total_pages = max(1, (total_items + 39) // 40)

            markup = get_lzt_markup(country)
            starting_price = lzt_final_inr_price(items[0], markup) if items else 0

            msg = (f"📦 Found: {total_items} | Page {page}/{total_pages}\n"
                   f"💰 Starting Price: {format_price(uid, starting_price)}\n"
                   f"🔽 Filters: {country} {flag} | ⚡ Cheap | 📊 Cheapest | "
                   f"Spam: {flt['spam']} | Geo: {flt['geoblock']} | Mail: {flt['login_mail']} | "
                   f"Premium: {flt['premium']} | Offline: {flt['offline']}\n\n"
                   f"Tap an account to view details & buy:\n")

            grid_buttons = [[p_btn("⚙️ Change Filters", "lzt_toggle_filters")]]
            grid_row = []

            for index, item in enumerate(items, start=1):
                final_price = lzt_final_inr_price(item, markup)
                global_index = (page - 1) * 40 + index

                item_id = int(item.get('item_id'))
                btn_lbl = f"[{country_button_label(country, include_phone=False)} #{global_index}] - {format_price(uid, final_price)}"
                grid_row.append(p_btn(btn_lbl, f"lzt_view|{item_id}|{country}|{final_price}"))
                if len(grid_row) == 2:
                    grid_buttons.append(grid_row)
                    grid_row = []
            if grid_row:
                grid_buttons.append(grid_row)

            nav = []
            if page > 1: nav.append(p_btn("⬅️ Prev Page", f"lzt_chk|{iso_code}|{page-1}"))
            if total_items > (page * 40): nav.append(p_btn("Next Page ➡️", f"lzt_chk|{iso_code}|{page+1}"))
            if nav: grid_buttons.append(nav)

            grid_buttons.append([p_btn("Change Country", "srv_1_pg|1")])
            await e.edit(msg, buttons=grid_buttons)

        elif data.startswith("lzt_view|"):
            _, item_id, country, _price_hint = data.split("|")
            await render_lzt_product(e, uid, item_id, country)


        elif data.startswith("lzt_mass_buy|"):
            _, first_item_id, price_str, country = data.split("|", 3)
            if uid in active_lzt_purchases:
                return await safe_answer_cb(e, "⏳ Please wait. Your previous Server 1 purchase is still processing.", alert=True)
            active_lzt_purchases[uid] = time.time()
            iso_code = COUNTRY_CODES.get(country, ("US", "🇺🇸"))[0]
            target_price = int(float(price_str))
            reserve_done = False
            tried = 0
            skipped = 0
            last_error = "No matching accounts found."
            try:
                async with get_user_lock(uid):
                    bal_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
                    current_bal = bal_row[0] if bal_row else 0
                    if current_bal < target_price:
                        return await safe_answer_cb(e, f"❌ Insufficient Balance! Need {P_INR}{target_price}", alert=True)
                    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (target_price, uid, target_price))
                    if cur.rowcount == 0:
                        return await safe_answer_cb(e, f"❌ Insufficient Balance! Need {P_INR}{target_price}", alert=True)
                    db.commit()
                    reserve_done = True

                await e.edit(
                    f"{P_TIME} <b>Mass Buy Started (Server 1)</b>\n\n"
                    f"Target price: {format_price(uid, target_price)}\n"
                    f"How it works: bot tries selected ID first, then other same-price IDs from this country until one purchase succeeds or all fail. Your balance is reserved now and refunded if all fail."
                )

                candidates = await get_lzt_candidate_items(country, target_price, preferred_item_id=first_item_id, max_pages=3)
                if not candidates:
                    last_error = "No same-price Server 1 accounts were found."

                for item in candidates:
                    candidate_id = str(item.get('item_id') or item.get('id') or '')
                    if not candidate_id:
                        skipped += 1
                        continue
                    latest_res = await lzt_request('GET', f"/{candidate_id}", params=lzt_currency_params())
                    latest_item = latest_res.get('item') if isinstance(latest_res, dict) else item
                    if not latest_item or lzt_item_requires_password(latest_item):
                        skipped += 1
                        last_error = "Skipped password-required account."
                        continue
                    candidate_price = lzt_final_inr_price(latest_item, get_lzt_markup(country))
                    if candidate_price != target_price:
                        skipped += 1
                        last_error = "Skipped account because price changed."
                        continue
                    market_price = lzt_market_price(latest_item)
                    if market_price is None:
                        skipped += 1
                        last_error = "Skipped account because market price was unavailable."
                        continue

                    tried += 1
                    try:
                        await e.edit(
                            f"{P_TIME} <b>Mass Buy Running...</b>\n\n"
                            f"Trying ID: <code>{candidate_id}</code>\n"
                            f"Tried: <b>{tried}</b> | Skipped: <b>{skipped}</b>\n"
                            f"Target price: {format_price(uid, target_price)}"
                        )
                    except MessageNotModifiedError:
                        pass

                    buy_res = await lzt_fast_buy_item(candidate_id, market_price)
                    if buy_res and not lzt_purchase_has_error(buy_res):
                        purchased_id = lzt_purchase_item_id(buy_res, candidate_id)
                        phone, display_phone = await finish_lzt_purchase_success(uid, purchased_id, country, target_price)
                        reserve_done = False
                        msg = (f"{P_YES} <b>Mass Buy Success (Server 1)!</b>\n\n"
                               f"{P_PHONE} <b>Phone:</b> <code>{display_phone}</code>\n"
                               f"<tg-emoji emoji-id='5776233299424843260'>🌐</tg-emoji> <b>Country:</b> {country}\n"
                               f"<tg-emoji emoji-id='6028435952299413210'>ℹ</tg-emoji> <b>Purchased ID:</b> <code>{purchased_id}</code>\n"
                               f" <tg-emoji emoji-id='6030657343744644592'>🔁</tg-emoji> <b>Attempts:</b> {tried} tried, {skipped} skipped\n\n"
                               f"<i>Click Get OTP when you need the latest login code.</i>")
                        btns = [
                            [p_btn("🔄 Get OTP", f"lzt_get_otp|{phone}", style="success")],
                            [p_btn("🚪 Logout & Finish", f"logout_finish|{phone}", style="danger")],
                            [p_btn("⬅ Back", f"lzt_chk|{iso_code}|1"), p_btn("Back to Menu", "menu_main", style="primary")]
                        ]
                        sent_msg = await e.edit(msg, buttons=btns)
                        active_orders[phone] = {
                            'uid': uid, 'start_time': time.time(), 'paid': True, 'otp_sent': False,
                            'price': target_price, 'country': country, 'year': 2024,
                            'msg_id': sent_msg.id, 'phone_num': display_phone
                        }
                        asyncio.create_task(auto_otp_task(phone))
                        return

                    last_error = lzt_error_text(buy_res) or "Purchase failed for this ID."

                if reserve_done:
                    async with get_user_lock(uid):
                        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (target_price, uid))
                        db.commit()
                    reserve_done = False
                return await e.edit(
                    f"{P_NO} <b>Mass Buy Failed</b>\n\n"
                    f"Tried: <b>{tried}</b> | Skipped: <b>{skipped}</b>\n"
                    f"Reason: <code>{html.escape(str(last_error)[:500])}</code>\n\n"
                    f"Your reserved balance was refunded.",
                    buttons=[[p_btn("Back", f"lzt_chk|{iso_code}|1")], [p_btn("Change Country", "srv_1_pg|1")]]
                )
            finally:
                if reserve_done:
                    async with get_user_lock(uid):
                        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (target_price, uid))
                        db.commit()
                active_lzt_purchases.pop(uid, None)

        elif data.startswith("lzt_buy|"):
            _, item_id, price_str, country = data.split("|")
            if uid in active_lzt_purchases:
                return await safe_answer_cb(e, "⏳ Please wait. Your previous Server 1 purchase is still processing.", alert=True)
            active_lzt_purchases[uid] = time.time()
            final_price = float(price_str)
            iso_code = COUNTRY_CODES.get(country, ("US", "🇺🇸"))[0]
            try:
                latest_res = await lzt_request('GET', f"/{item_id}", params=lzt_currency_params())
                latest_item = latest_res.get('item') if isinstance(latest_res, dict) else None
                market_price = lzt_market_price(latest_item)
                if not latest_item or market_price is None:
                    return await e.edit(f"{P_WARN} <b>Unable to load latest Server 1 price.</b>\nPlease refresh the stock and try again.", buttons=[[p_btn("Back", f"lzt_chk|{iso_code}|1")]])
                if lzt_item_requires_password(latest_item):
                    return await e.edit(
                        f"{P_WARN} <b>Cannot buy this Server 1 account.</b>\nThis listing requires a seller login password, so the bot skipped it before charging your wallet.",
                        buttons=[[p_btn("Back", f"lzt_chk|{iso_code}|1")], [p_btn("Change Country", "srv_1_pg|1")]]
                    )
                final_price = lzt_final_inr_price(latest_item, get_lzt_markup(country))

                async with get_user_lock(uid):
                    bal_row = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
                    current_bal = bal_row[0] if bal_row else 0
                    if current_bal < final_price:
                        return await safe_answer_cb(e, f"❌ Insufficient Balance! Need {P_INR}{final_price}", alert=True)
                    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (final_price, uid, final_price))
                    if cur.rowcount == 0:
                        return await safe_answer_cb(e, f"❌ Insufficient Balance! Need {P_INR}{final_price}", alert=True)
                    db.commit()

                await e.edit(f"{P_TIME} <b>Purchasing from Server 1...</b>\n\nPlease wait for this purchase to finish before buying another account.")

                buy_res = await lzt_fast_buy_item(item_id, market_price)

                if lzt_purchase_has_error(buy_res):
                    try:
                        alt_res_data = await lzt_request('GET', f"/telegram?country%5B%5D={iso_code}&spam=no&nsb=1&pmin=0.01&pmax=1000&page=1&per_page=10&password=no&currency=rub")
                        if alt_res_data and 'items' in alt_res_data and isinstance(alt_res_data['items'], list):
                            for alt_item in alt_res_data['items']:
                                alt_id = str(alt_item.get('item_id'))
                                if alt_id == str(item_id): continue
                                alt_price = lzt_market_price(alt_item)
                                if alt_price is None: continue
                                alt_buy = await lzt_fast_buy_item(alt_id, alt_price)
                                if alt_buy and not lzt_purchase_has_error(alt_buy):
                                    item_id = lzt_purchase_item_id(alt_buy, alt_id)
                                    buy_res = alt_buy
                                    break
                    except Exception as ex_alt:
                        logger.warning(f"Fallback buy search error: {ex_alt}")

                if lzt_purchase_has_error(buy_res):
                    async with get_user_lock(uid):
                        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (final_price, uid))
                        db.commit()
                    err_text = lzt_error_text(buy_res)
                    if "password" in err_text.lower():
                        return await e.edit(f"{P_WARN} <b>Purchase skipped and refunded.</b>\nServer 1 says this account requires a seller login password, so it cannot be bought safely by the bot.", buttons=[[p_btn("Back", f"lzt_chk|{iso_code}|1")], [p_btn("Change Country", "srv_1_pg|1")]])
                    if "balance" in err_text.lower() or "средств" in err_text.lower() or "not enough" in err_text.lower():
                        return await e.edit(f"{P_WARN} <b>Server 1 Maintenance.</b>\nBalance refunded. Market balance is not enough; please notify admin or use Server 2.", buttons=[[p_btn("Back", "menu_buy")]])
                    if "timeout" in err_text.lower():
                        return await e.edit(f"{P_WARN} <b>Server 1 is slow right now.</b>\nMoney refunded. Please try again in a minute.", buttons=[[p_btn("Back", f"lzt_chk|{iso_code}|1")]])
                    return await e.edit(f"{P_NO} <b>Purchase Failed!</b> Account was sold or invalid on market. Money refunded.", buttons=[[p_btn("Try Again", f"lzt_chk|{iso_code}|1", style="primary"), p_btn("Back to Menu", "menu_main", style="danger")]])

                item_id = lzt_purchase_item_id(buy_res, item_id)
                res = await lzt_request('GET', f"/{item_id}", params=lzt_currency_params())
                phone_num = f"LZT_{item_id}"
                if res and 'item' in res:
                    item = res['item']
                    phone_num = item.get('phone') or item.get('telegram_phone') or item.get('login') or f"LZT_{item_id}"

                display_phone = normalize_lzt_phone(phone_num, item_id)
                phone = f"LZT_{item_id}"

                async with get_user_lock(uid):
                    cur.execute(
                        "INSERT INTO orders (user_id, country, year, price, phone, otp, server) VALUES (?,?,?,?,?,?,?)",
                        (uid, country, 2024, final_price, display_phone, None, "Server 1")
                    )
                    db.commit()
                await log_primary_purchase(uid, country, final_price, final_price, 2024, 1, display_phone, "Server 1")

                msg = (f"{P_YES} <b>Account Purchased (Server 1)!</b>\n\n"
                       f"{P_PHONE} <b>Phone:</b> <code>{display_phone}</code>\n"
                       f"🏳️ <b>Country:</b> {country}\n\n"
                       f"<i>Click Get OTP when you need the latest login code.</i>")

                btns = [
                    [p_btn("🔄 Read Again / Get OTP", f"lzt_get_otp|{phone}", style="success"), p_btn("🚪 Logout & Finish", f"logout_finish|{phone}", style="danger")],
                    [p_btn("📜 Order History", "menu_history", style="primary"), p_btn("💳 Deposit Balance", "menu_deposit", style="success")],
                    [p_btn("⬅️ Main Menu", "menu_main", style="primary")]
                ]
                sent_msg = await e.edit(msg, buttons=btns)
                active_orders[phone] = {
                    'uid': uid,
                    'start_time': time.time(),
                    'paid': True,
                    'otp_sent': False,
                    'price': final_price,
                    'country': country,
                    'year': 2024,
                    'msg_id': sent_msg.id,
                    'phone_num': display_phone
                }
                asyncio.create_task(auto_otp_task(phone))
            except Exception as ex:
                async with get_user_lock(uid):
                    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (final_price, uid))
                    db.commit()
                await send_admin_error("Server 1 Buy Exception", str(ex))
                await e.edit(f"{P_NO} <b>Purchase failed.</b> Balance refunded.", buttons=[[p_btn("Back", f"lzt_chk|{iso_code}|1")]])
            finally:
                active_lzt_purchases.pop(uid, None)

        elif data.startswith("lzt_get_otp|"):
            phone = data.split("|")[1]
            if phone not in active_orders: return await safe_answer_cb(e, "Session Expired.", alert=True)
            order = active_orders[phone]
            if order.get('uid') != uid and not is_admin(uid):
                return await safe_answer_cb(e, "❌ Unauthorized order access.", alert=True)
            item_id = phone.split("_")[1]
            country = order['country']
            iso_code = COUNTRY_CODES.get(country, ("US", "🇺🇸"))[0]

            await e.answer("Fetching OTP from Server 1...", alert=False)
            code, verified, res = await get_verified_lzt_otp(item_id, attempts=3, delay=1.5)

            display_phone = order.get('phone_num') or normalize_lzt_phone(None, item_id)

            if code:
                async with get_user_lock(uid):
                    cur.execute("UPDATE orders SET otp=? WHERE phone=? AND user_id=? AND server='Server 1'", (code, display_phone, uid))
                    db.commit()
                msg = (f"{P_YES} <b>Latest OTP Fetched!</b>\n\n"
                       f"{P_PHONE} <b>Phone:</b> <code>{display_phone}</code>\n"
                       f"🏳️ <b>Country:</b> {country}\n"
                       f"{P_TIME} <b>OTP:</b> <code>{code}</code>\n\n"
                       f"{P_SHIELD} <b>Server 1 double-check:</b> {'Verified' if verified else 'Best latest code'}\n\n"
                       f"<i>Use this code to login.</i>")
                btns = [
                    [p_btn("🔄 Read Again / Get OTP", f"lzt_get_otp|{phone}", style="success"), p_btn("🚪 Logout & Finish", f"logout_finish|{phone}", style="danger")],
                    [p_btn("📜 Order History", "menu_history", style="primary"), p_btn("💳 Deposit Balance", "menu_deposit", style="success")],
                    [p_btn("⬅️ Main Menu", "menu_main", style="primary")]
                ]
                try: await e.edit(msg, buttons=btns)
                except MessageNotModifiedError: pass
            else:
                await e.answer("⏳ OTP not available yet. Wait and retry.", alert=True)

        elif data.startswith("lzt_logout|") or data.startswith("logout_finish_confirm|"):
            phone = data.split("|")[1]
            if phone in active_orders:
                order = active_orders.pop(phone)
                cur.execute("DELETE FROM pending_orders WHERE phone=?", (phone,))
                db.commit()
                if order.get('uid') != uid and not is_admin(uid):
                    return await safe_answer_cb(e, "❌ Unauthorized session access.", alert=True)
                if "_" not in phone:
                    client = order.get('client')
                    if client:
                        try: await client.log_out()
                        except: pass
                        try: await client.disconnect()
                        except: pass
                    sess = order.get('sess')
                    if sess:
                        delete_session_files(sess)

            clean_disp = f"Hidden-{phone.split('_')[1]}" if "_" in phone else f"+{phone.lstrip('+')}"
            msg = (f"✅ <b>Bot Session Terminated Successfully!</b>\n\n"
                   f"{P_PHONE} <b>Account:</b> <code>{clean_disp}</code>\n"
                   f"🔒 Your account session is now fully completed and disconnected from the bot.\n\n"
                   f"💡 <i>Tip: For maximum security, open Telegram App → Settings → Devices → Terminate all other sessions.</i>")
            await e.edit(msg, buttons=[[p_btn("Back to Main Menu", "menu_main", style="primary")]])

        elif data.startswith("sm_kill|") or data.startswith("sm_kill_all|"):
            parts = data.split("|")
            action_type = parts[0]
            sm_id = parts[1]

            if sm_id not in session_cache_map:
                return await safe_answer_cb(e, "❌ Session expired. Please send your Hex Key again.", alert=True)

            cache = session_cache_map[sm_id]
            if cache['uid'] != uid and not is_admin(uid):
                return await safe_answer_cb(e, "❌ Unauthorized session access.", alert=True)

            auth_hex = cache.get('auth_hex')
            dc_id = cache.get('dc_id', 2)
            sess_str = cache.get('sess_str')

            client = None
            try:
                if auth_hex:
                    session_obj = hex_to_telethon_string_session(auth_hex, dc_id)
                    client = TelegramClient(session_obj, API_ID, API_HASH)
                else:
                    client = TelegramClient(StringSession(sess_str), API_ID, API_HASH)

                await client.connect()
                if not await client.is_user_authorized():
                    await client.disconnect()
                    return await safe_answer_cb(e, "❌ Session already logged out.", alert=True)

                if action_type == "sm_kill_all":
                    authorizations = await client(functions.account.GetAuthorizationsRequest())
                    auths = authorizations.authorizations if authorizations else []
                    terminated_cnt = 0
                    for auth in auths:
                        if not getattr(auth, 'current', False):
                            try:
                                await client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                                terminated_cnt += 1
                            except Exception: pass
                    await client.disconnect()
                    return await e.edit(f"✅ <b>All Other Devices Terminated!</b>\n\nDisconnected <b>{terminated_cnt}</b> other device(s). Your account is now secured.", buttons=[[p_btn("Main Menu", "menu_main", style="primary")]])

                else:
                    target_hash = parts[2]
                    if target_hash == "current":
                        await client.log_out()
                        try: await client.disconnect()
                        except: pass
                        return await e.edit("✅ <b>Bot Session Logged Out Successfully!</b>\n\nThe bot has logged out of your account.", buttons=[[p_btn("Main Menu", "menu_main", style="primary")]])
                    else:
                        await client(functions.account.ResetAuthorizationRequest(hash=int(target_hash)))
                        await client.disconnect()
                        return await e.edit("✅ <b>Target Device Terminated Successfully!</b>", buttons=[[p_btn("Main Menu", "menu_main", style="primary")]])

            except Exception as ex:
                if client:
                    try: await client.disconnect()
                    except: pass
                return await safe_answer_cb(e, f"❌ Termination failed: {ex}", alert=True)

        elif data.startswith("view_devices|"):
            phone = data.split("|")[1]
            if phone in active_orders:
                order = active_orders[phone]
                if order.get('uid') != uid and not is_admin(uid):
                    return await safe_answer_cb(e, "❌ Unauthorized session access.", alert=True)
                client = order.get('client')
                if client:
                    await e.answer("📱 Fetching active devices...", alert=False)
                    try:
                        authorizations = await client(functions.account.GetAuthorizationsRequest())
                        auths = authorizations.authorizations if authorizations else []
                        if auths:
                            sm_id = f"sm_{uid}_{int(time.time())}"
                            session_cache_map[sm_id] = {
                                'uid': uid,
                                'phone': phone,
                                'client': client,
                                'auths': auths
                            }
                            lines = [
                                f"📱 <b>TELEGRAM SESSION MANAGER</b>",
                                f"━━━━━━━━━━━━━━━━━━━━",
                                f"👤 <b>Account:</b> <code>+{phone.lstrip('+')}</code>",
                                f"📲 <b>Active Authorizations:</b> <b>{len(auths)}</b>",
                                "",
                                "🔻 <b>ACTIVE DEVICES LIST:</b>",
                            ]
                            btns = []
                            for idx, auth in enumerate(auths, 1):
                                is_current = getattr(auth, 'current', False)
                                dev_model = getattr(auth, 'device_model', 'Unknown Device')
                                platform = getattr(auth, 'platform', 'Telegram')
                                app_name = getattr(auth, 'app_name', 'App')
                                app_version = getattr(auth, 'app_version', '1.0')
                                ip = getattr(auth, 'ip', 'N/A')
                                country = getattr(auth, 'country', 'N/A')
                                auth_hash = getattr(auth, 'hash', 0)

                                status_tag = "✨ Current (Bot)" if is_current else "⚠️ Other Device"
                                lines.append(f"<b>{idx}.</b> 📱 <b>{html.escape(dev_model)}</b> | {html.escape(platform)}")
                                lines.append(f"   └ App: {html.escape(app_name)} {html.escape(app_version)}")
                                lines.append(f"   └ Location: 🌍 {html.escape(country)} ({ip})")
                                lines.append(f"   └ Status: {status_tag}")
                                lines.append("")

                                if is_current:
                                    btns.append([p_btn(f"🔴 Logout Device {idx} (Bot Session)", f"sm_kill|{sm_id}|current", style="danger")])
                                else:
                                    btns.append([p_btn(f"🚫 Terminate Device {idx} ({dev_model[:18]})", f"sm_kill|{sm_id}|{auth_hash}")])

                            if len(auths) > 1:
                                btns.append([p_btn(f"🔴 Terminate ALL Other Devices ({len(auths)-1})", f"sm_kill_all|{sm_id}", style="danger")])

                            btns.append([p_btn("🚪 Back to Logout Control", f"logout_finish|{phone}", style="primary")])
                            return await e.edit("\n".join(lines), buttons=btns)
                    except Exception as ex:
                        return await safe_answer_cb(e, f"❌ Failed to fetch devices: {ex}", alert=True)

            return await handle_logout_command(e)
        elif data.startswith("srv_2_pg|"):
            page = int(data.split("|")[1])
            limit, offset = 10, (page - 1) * 10
            total_row = cur.execute("SELECT COUNT(DISTINCT country_name) FROM stock WHERE available=1").fetchone()
            total = total_row[0] if total_row else 0

            rows = cur.execute("SELECT country_icon, country_name, COUNT(*) FROM stock WHERE available=1 GROUP BY country_name ORDER BY country_name ASC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            if not rows and page == 1: return await e.edit("❌ <b>Server 2 Empty.</b>", buttons=[[p_btn("Back", "menu_buy")]])

            total_bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
            msg = (f"<b>Click country to view price and stock:</b>\n"
                   f"─────────────────────\n"
                   f"✅ Total balance: {format_price(uid, total_bal)}\n"
                   f"✅ Server: Server (2)\n"
                   f"✅ Page {page} of {((total + limit - 1) // limit)}\n")

            btns = [[p_btn("🛒 Buy Session", "s2_buy_session")]]
            btns.extend([[p_btn(f"{i} {n} ({c})", f"s2_yr|{n[:20]}")] for (i, n, c) in rows])
            nav = []
            if page > 1: nav.append(p_btn("Prev", f"srv_2_pg|{page-1}"))
            if offset + limit < total: nav.append(p_btn("Next", f"srv_2_pg|{page+1}"))
            if nav: btns.append(nav)
            btns.append([p_btn("Back to Servers", "menu_buy")])
            await e.edit(msg, buttons=btns)

        elif data == "s2_buy_session":
            rows = cur.execute(
                "SELECT country_icon, country_name, COUNT(*) FROM stock WHERE available=1 GROUP BY country_name ORDER BY country_name ASC LIMIT 50"
            ).fetchall()
            if not rows:
                return await e.edit("❌ <b>Server 2 Empty.</b>", buttons=[[p_btn("Back", "menu_buy")]])
            msg = (f"{P_STORE} <b>Server 2 Buy Session</b>\n\n"
                   "Choose a country, then choose year and send how many accounts you need to buy.\n"
                   "After confirmation, the bot sends the session file(s) and logs out its own client.")
            btns = [[p_btn(f"{i} {n} ({c})", f"s2_yr|{n[:20]}")] for (i, n, c) in rows]
            btns.append([p_btn("Back", "srv_2_pg|1")])
            await e.edit(msg, buttons=btns)

        elif data.startswith("s2_yr|"):
            country = data.split("|")[1]
            rows = cur.execute("SELECT account_year, price, COUNT(*) FROM stock WHERE available=1 AND country_name LIKE ? GROUP BY account_year, price ORDER BY account_year DESC", (f"{country}%",)).fetchall()
            if not rows: return await e.answer("❌ Out of stock.", alert=True)
            msg = f"{P_CAL} <b>Select Year</b>\n🏳️ Country: <b>{country}</b>\n\n"
            btns = [[p_btn(f"{y} | {format_price(uid, p)} | {c}", f"s2_cf|{country}|{y}|{p}")] for (y, p, c) in rows]
            btns.append([p_btn("Back", "srv_2_pg|1")])
            await e.edit(msg, buttons=btns)

        elif data.startswith("s2_cf|"):
            parts = data.split("|")
            country, year, base_price = parts[1], parts[2], parts[3]
            stock_count = cur.execute(
                "SELECT COUNT(*) FROM stock WHERE available=1 AND country_name LIKE ? AND account_year=? AND price=?",
                (f"{country}%", int(year), int(base_price))
            ).fetchone()[0]
            session_buy_state[uid] = {"country": country, "year": int(year), "price": int(base_price), "stock": stock_count}
            return await e.edit(
                f"{P_CART} <b>How many sessions do you want?</b>\n\n"
                f"🏳️ <b>Country:</b> {country}\n"
                f"{P_CAL} <b>Year:</b> {year}\n"
                f"{P_CASH} <b>Each:</b> {format_price(uid, int(base_price))}\n"
                f"📦 <b>Available:</b> {stock_count}\n\n"
                "Send quantity as a number.",
                buttons=[[p_btn("Cancel", "s2_qty_cancel")]]
            )

        elif data.startswith("s2_qty_confirm|"):
            _, country, year_str, price_str, qty_str = data.split("|")
            final_price, qty = int(price_str), int(qty_str)
            total_price = final_price * qty
            bought = []
            clients_to_logout = []
            async with get_user_lock(uid):
                bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
                rows = cur.execute(
                    "SELECT phone, session_file, country_icon, account_year, twofa, seller_id FROM stock WHERE country_name LIKE ? AND account_year=? AND price=? AND available=1 LIMIT ?",
                    (f"{country}%", int(year_str), final_price, qty)
                ).fetchall()
                if len(rows) < qty:
                    return await e.edit("❌ <b>Not enough stock now.</b>", buttons=[[p_btn("Back", f"s2_yr|{country}")]])
                if bal < total_price:
                    return await e.edit(f"❌ <b>Insufficient balance.</b>\nNeed {format_price(uid, total_price)}.", buttons=[[p_btn("Recharge", "menu_deposit"), p_btn("Cancel", "srv_2_pg|1")]])
                cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (total_price, uid, total_price))
                if cur.rowcount == 0:
                    return await e.edit("❌ <b>Balance changed. Try again.</b>", buttons=[[p_btn("Back", f"s2_yr|{country}")]])
                for row in rows:
                    cur.execute("UPDATE stock SET available=0 WHERE phone=?", (row[0],))
                db.commit()

            await e.edit(f"🔄 <b>Preparing {qty} Server 2 session(s)...</b>")
            try:
                for phone, sess, c_icon, actual_year, twofa_pass, seller_id in rows:
                    clean_sess = sess[:-8] if sess.endswith(".session") else sess
                    dyn_id, dyn_hash = get_api_credentials()
                    client = TelegramClient(clean_sess, dyn_id, dyn_hash)
                    await client.connect()
                    if not await client.is_user_authorized():
                        raise Exception(f"Invalid session +{phone}")
                    await bot.send_file(uid, sess, caption=f"{P_YES} <b>Server 2 session delivered</b>\nPhone: <code>+{str(phone).lstrip('+')}</code>\n2FA: <code>{twofa_pass}</code>")
                    clients_to_logout.append((client, sess))
                    bought.append((phone, seller_id, actual_year, c_icon, twofa_pass))
                    cur.execute("INSERT INTO orders (user_id, country, year, price, phone, otp, server) VALUES (?,?,?,?,?,?,?)", (uid, country, actual_year, final_price, phone, None, "Server 2"))
                    cur.execute("DELETE FROM stock WHERE phone=?", (phone,))
                db.commit()
                for phone, seller_id, actual_year, c_icon, twofa_pass in bought:
                    if seller_id:
                        seller_cut = int(final_price * 0.90)
                        update_balance(seller_id, seller_cut, "sales_balance")
                        try: await bot.send_message(seller_id, f"{P_GIFT} <b>Account Sold!</b>\nYour uploaded number +{phone} was sold. {P_CASH}{seller_cut} added to Sales Balance.")
                        except: pass
                await log_primary_purchase(uid, country, final_price, total_price, int(year_str), qty, bought[0][0] if bought else None, "Server 2")
                await e.edit(f"{P_YES} <b>Purchase complete!</b>\nDelivered: <b>{len(bought)}</b>\nTotal: {format_price(uid, total_price)}", buttons=[[p_btn("Buy More", "s2_buy_session"), p_btn("Menu", "menu_main")]])
            except Exception as ex:
                async with get_user_lock(uid):
                    update_balance(uid, total_price)
                    for phone, *_ in rows:
                        cur.execute("UPDATE stock SET available=1 WHERE phone=?", (phone,))
                    db.commit()
                await send_admin_error("Server 2 bulk buy failed", str(ex))
                await e.edit("❌ <b>Purchase failed.</b> Balance refunded.", buttons=[[p_btn("Back", "s2_buy_session")]])
            finally:
                for client, sess in clients_to_logout:
                    try: await client.log_out()
                    except: pass
                    try: await client.disconnect()
                    except: pass
                    delete_session_files(sess)

        elif data == "s2_qty_cancel":
            session_buy_state.pop(uid, None)
            await e.edit("❌ <b>Server 2 purchase cancelled.</b>", buttons=[[p_btn("Back", "srv_2_pg|1")]])

        elif data.startswith("s2_cf_old|"):
            parts = data.split("|")
            country, year, base_price = parts[1], parts[2], parts[3]
            bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
            final_price = int(base_price)
            diff = final_price - bal
            msg = (f"{P_STORE} <b>Confirm Purchase</b>\n\n{P_CASH} <b>Price:</b> {format_price(uid, final_price)}\n💳 <b>Balance:</b> {format_price(uid, bal)}\n\n🏳️ <b>Country:</b> {country}\n🌍 <b>Region:</b> Server 2 (Local)")
            btns = [[p_btn("Need Recharge", "menu_deposit")] if diff > 0 else [p_btn("✅ Purchase", f"s2_buy|{country}|{year}|{final_price}")]]
            await e.edit(msg, buttons=btns)

        elif data.startswith("s2_buy|"):
            parts = data.split("|")
            country, year_str, price_str = parts[1], parts[2], parts[3]
            specific_phone = parts[4] if len(parts) > 4 else None
            final_price = int(price_str)

            async with get_user_lock(uid):
                if specific_phone:
                    row = cur.execute("SELECT phone, session_file, country_icon, account_year, twofa, seller_id FROM stock WHERE phone=? AND available=1", (specific_phone,)).fetchone()
                else:
                    row = cur.execute("SELECT phone, session_file, country_icon, account_year, twofa, seller_id FROM stock WHERE country_name LIKE ? AND account_year=? AND price=? AND available=1 LIMIT 1", (f"{country}%", int(year_str), final_price)).fetchone()

                if not row: return await e.answer("❌ Sold out!", alert=True)
                phone, sess, c_icon, actual_year, twofa_pass, seller_id = row

                cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (final_price, uid, final_price))
                if cur.rowcount == 0: return await e.answer("❌ Insufficient Balance!", alert=True)
                cur.execute("UPDATE stock SET available=0 WHERE phone=?", (phone,))
                cur.execute("INSERT OR REPLACE INTO pending_orders (phone, user_id, price, created) VALUES (?,?,?,?)", (phone, uid, final_price, time.time()))
                db.commit()

            await e.edit(f"🔄 <b>Fetching Number (+{phone})...</b>")
            clean_sess = sess if not sess.endswith(".session") else sess[:-8]

            dyn_id, dyn_hash = get_api_credentials()
            client = TelegramClient(clean_sess, dyn_id, dyn_hash)
            try:
                await client.connect()
                if not await client.is_user_authorized(): raise Exception("Session dead")
            except Exception:
                async with get_user_lock(uid):
                    cur.execute("DELETE FROM stock WHERE phone=?", (phone,))
                    cur.execute("DELETE FROM pending_orders WHERE phone=?", (phone,))
                    update_balance(uid, final_price)
                    db.commit()
                await client.disconnect()
                delete_session_files(sess)
                return await e.edit("❌ <b>Account Invalid.</b> Money refunded.", buttons=[[p_btn("Back", "srv_2_pg|1")]])

            await log_primary_purchase(uid, country, final_price, final_price, actual_year, 1, phone, "Server 2")

            display_phone = f"+{phone.lstrip('+')}"
            msg = (f"{P_YES} <b>Account Purchased (Server 2)!</b>\n\n{P_PHONE} <b>Phone:</b> <code>{display_phone}</code>\n🏳️ <b>Country:</b> {c_icon} {country}\n\n"
                   f"🔻 <b>INSTRUCTIONS:</b>\n1. Add Account in Telegram\n2. Enter number\n3. {P_TIME} Listening for OTP automatically...\n\n"
                   f"<i>Note: Auto-cancels in 10 mins if no OTP arrives.</i>")

            btns = [
                [p_btn("🔄 Get OTP", f"get_otp_again|{phone}", style="success")],
                [p_btn("🚪 Logout & Finish", f"logout_finish|{phone}", style="danger")],
                [p_btn("Back to Menu", "menu_main", style="primary")]
            ]
            sent_msg = await e.edit(msg, buttons=btns)
            active_orders[phone] = {'uid': uid, 'client': client, 'sess': sess, 'start_time': time.time(), 'paid': False, 'price': final_price, 'country': country, 'year': actual_year, 'c_icon': c_icon, 'twofa': twofa_pass, 'seller_id': seller_id, 'msg_id': sent_msg.id}
            asyncio.create_task(auto_otp_task(phone))

        elif data.startswith("s2_get_otp|") or data.startswith("get_otp_again|"):
            phone = data.split("|")[1]
            if phone not in active_orders:
                return await safe_answer_cb(e, "⚠️ Session already logged out or expired.", alert=True)

            order = active_orders[phone]
            if order.get('uid') != uid and not is_admin(uid):
                return await safe_answer_cb(e, "❌ Unauthorized order access.", alert=True)

            client = order['client']
            start_time = order['start_time']

            await e.answer("🔄 Fetching latest OTP...", alert=False)
            try:
                latest_code = await get_latest_telegram_login_otp(client, start_time)

                if latest_code:
                    if not order.get('paid'):
                        order['paid'] = True
                        price = order['price']
                        async with get_user_lock(uid):
                            cur.execute("INSERT INTO orders (user_id, country, year, price, phone, otp) VALUES (?,?,?,?,?,?)", (uid, order['country'], order['year'], price, phone, latest_code))
                            cur.execute("DELETE FROM stock WHERE phone=?", (phone,))
                            db.commit()

                        if order.get('seller_id'):
                            seller_cut = int(price * 0.90)
                            update_balance(order['seller_id'], seller_cut, "sales_balance")
                            try: await bot.send_message(order['seller_id'], f"{P_GIFT} <b>Account Sold!</b>\nYour uploaded number +{phone} was just sold. {P_CASH}{seller_cut} has been added to your Sales Balance!")
                            except: pass

                    twofa_text = f"{P_SHIELD} <b>2FA:</b> <code>{order['twofa']}</code>" if order['twofa'] != "None" else f"🔓 <b>2FA:</b> <code>Disabled</code>"
                    display_phone = f"+{phone.lstrip('+')}"
                    msg = (f"{P_YES} <b>Latest OTP Fetched!</b>\n\n"
                           f"{P_PHONE} <b>Phone:</b> <code>{display_phone}</code>\n"
                           f"🏳️ <b>Country:</b> {order['c_icon']} {order['country']}\n"
                           f"{P_TIME} <b>OTP:</b> <code>{latest_code}</code>\n"
                           f"{twofa_text}")
                    btns = [
                        [p_btn("🔄 Read Again / Get OTP", f"get_otp_again|{phone}", style="success"), p_btn("🚪 Logout & Finish", f"logout_finish|{phone}", style="danger")],
                        [p_btn("📜 Order History", "menu_history", style="primary"), p_btn("💳 Deposit Balance", "menu_deposit", style="success")],
                        [p_btn("⬅️ Main Menu", "menu_main", style="primary")]
                    ]
                    try: await e.edit(msg, buttons=btns)
                    except MessageNotModifiedError: pass
                else:
                    await e.answer("⏳ No new OTP found yet. Try again in a few seconds.", alert=True)
            except Exception as ex:
                await e.answer("❌ Error fetching OTP.", alert=True)

        elif data.startswith("logout_finish|"):
            phone = data.split("|")[1]
            order = active_orders.get(phone)
            twofa = "None"
            country = "N/A"

            if order:
                if order.get('uid') != uid and not is_admin(uid):
                    return await safe_answer_cb(e, "❌ Unauthorized session access.", alert=True)
                twofa = order.get('twofa', 'None')
                country = order.get('country', 'N/A')
            else:
                row = cur.execute("SELECT country, twofa, user_id FROM orders WHERE phone=?", (phone,)).fetchone()
                if not row:
                    row = cur.execute("SELECT country_name, twofa, seller_id FROM stock WHERE phone=?", (phone,)).fetchone()
                if row:
                    if row[2] != uid and not is_admin(uid):
                        return await safe_answer_cb(e, "❌ Unauthorized session access.", alert=True)
                    country, twofa = row[0], row[1]
                else:
                    return await safe_answer_cb(e, "⚠️ Order session not found or already logged out.", alert=True)

            is_lzt = "_" in phone
            display_phone = f"Hidden-{phone.split('_')[1]}" if is_lzt else f"+{phone.lstrip('+')}"
            server_name = "Server 1 (Global Premium)" if is_lzt else "Server 2 (Instant Stock)"
            otp_btn_cb = f"lzt_get_otp|{phone}" if is_lzt else f"get_otp_again|{phone}"

            twofa_line = f"{P_SHIELD} <b>2FA Password:</b> <code>{twofa}</code>\n" if twofa and twofa != "None" else "🔓 <b>2FA Password:</b> <code>Disabled</code>\n"

            msg = (f"🚪 <b>Logout & Finish Control Center</b>\n\n"
                   f"{P_PHONE} <b>Account Phone:</b> <code>{display_phone}</code>\n"
                   f"🏳️ <b>Country:</b> {country}\n"
                   f"⚡ <b>Server Source:</b> {server_name}\n"
                   f"{twofa_line}\n"
                   f"🔻 <b>STEPS TO SECURE YOUR ACCOUNT:</b>\n"
                   f"1. Open Telegram App → Add Account using <code>{display_phone}</code>\n"
                   f"2. Tap <b>🔄 Get OTP</b> to receive login code\n"
                   f"3. Enter 2FA Password if enabled\n"
                   f"4. After login, tap <b>🚪 Terminate Bot Session & Finish</b> below to log out our bot!\n")

            btns = [
                [p_btn("🔄 Get OTP", otp_btn_cb, style="success"), p_btn("📱 View Active Devices", f"view_devices|{phone}", style="primary")],
                [p_btn("🚪 Terminate Bot Session & Finish", f"logout_finish_confirm|{phone}", style="danger")],
                [p_btn("🏠 Back to Main Menu", "menu_main", style="primary")]
            ]
            await e.edit(msg, buttons=btns)

        elif data.startswith("logout_bot|"):
            phone = data.split("|")[1]
            if phone in active_orders:
                order = active_orders.pop(phone)
                cur.execute("DELETE FROM pending_orders WHERE phone=?", (phone,))
                db.commit()
                if order.get('uid') != uid and not is_admin(uid):
                    return await safe_answer_cb(e, "❌ Unauthorized session access.", alert=True)
                try: await order['client'].log_out()
                except: pass
                try: await order['client'].disconnect()
                except: pass
                if order.get('sess'):
                    delete_session_files(order['sess'])
                await e.edit(f"{P_YES} <b>Session Finished & Logged out successfully.</b>", buttons=[[p_btn("Back to Menu", "menu_main", style="primary")]])
            else:
                await e.answer("⚠️ No active order found or already logged out.", alert=True)

        # --- MENU EXTRAS ---
        elif data == "menu_account":
            await render_user_profile(e, uid)

        elif data == "menu_uploads" or data.startswith("page_uploads_"):
            page = 1
            if data.startswith("page_uploads_"):
                try: page = int(data.split("_")[2])
                except: page = 1
            limit, offset = 5, (page - 1) * 5
            
            total_cnt = cur.execute("SELECT COUNT(*) FROM stock WHERE seller_id=?", (uid,)).fetchone()[0]
            total_pages = max(1, (total_cnt + limit - 1) // limit)
            rows = cur.execute("SELECT phone, country_name, account_year, category, price, available, added_date FROM stock WHERE seller_id=? ORDER BY added_date DESC LIMIT ? OFFSET ?", (uid, limit, offset)).fetchall()
            
            msg = (f"📦 <b>MY UPLOADED ACCOUNTS</b>\n"
                   f"━━━━━━━━━━━━━━━━━━━━\n"
                   f"📑 <b>Page:</b> {page} / {total_pages}\n"
                   f"📦 <b>Total Uploaded:</b> {total_cnt} accounts\n"
                   f"━━━━━━━━━━━━━━━━━━━━\n\n")
            
            btns = []
            if not rows:
                msg += "<i>You have not uploaded any accounts yet.</i>\n"
            else:
                for ph, c_name, yr, cat, pr, avail, a_dt in rows:
                    st_str = "🟢 AVAILABLE ON MARKET" if avail == 1 else "🔴 SOLD / REMOVED"
                    c_flag = get_flag_by_country_name(c_name or "Unknown")
                    clean_ph = f"+{str(ph).lstrip('+')}" if str(ph).lstrip('+').isdigit() else ph
                    msg += (f"📱 <code>{clean_ph}</code>\n"
                            f"🏳️ <b>Details:</b> {c_flag} {html.escape(c_name or 'Unknown')} ({yr}) | {cat}\n"
                            f"💰 <b>Price:</b> {format_price(uid, pr or 0)}\n"
                            f"📊 <b>Status:</b> {st_str}\n"
                            f"📅 <b>Date:</b> {format_purchase_datetime(a_dt)}\n"
                            f"────────────────\n")
                    if avail == 1:
                        btns.append([p_btn(f"🗑 Remove {clean_ph}", f"sell_rm|{ph}", style="danger")])
            
            nav = []
            if page > 1: nav.append(p_btn("⬅️ Prev", f"page_uploads_{page-1}", style="primary"))
            if offset + limit < total_cnt: nav.append(p_btn("Next ➡️", f"page_uploads_{page+1}", style="primary"))
            if nav: btns.append(nav)
            btns.append([p_btn("Back to Profile", "menu_account", style="danger")])
            await safe_show_message(e, msg, buttons=btns)

        elif data == "claim_promo":
            promo_state[uid] = "wait_code"
            await e.edit(f"{P_GIFT} <b>Claim Promo Code</b>\n\nPlease enter or reply with your promo code below:", buttons=[[p_btn("Cancel", "menu_account")]])

        elif data == "tgl_curr":
            c_pref = get_currency_pref(uid)
            ns = "USDT" if c_pref == "INR" else "INR"
            cur.execute("UPDATE users SET pref_curr=? WHERE user_id=?", (ns, uid))
            db.commit()
            await e.answer(f"Currency updated to {ns}", alert=False)
            await render_user_profile(e, uid)

        elif data == "menu_deposit":
            manual_dep_state.pop(uid, None)
            deposit_input.pop(uid, None)
            current_msg_id = callback_message_id(e)
            deleted_msg_ids = await cleanup_deposit_media(uid)
            msg = f"💳 <b>Select Payment Method:</b>\n\n🟢 Choose Automatic for instant credit.\n⏳ Choose Manual for other methods."
            btns = build_deposit_menu_buttons()
            if current_msg_id and current_msg_id in deleted_msg_ids:
                await bot.send_message(uid, msg, buttons=btns)
            else:
                try:
                    await e.edit(msg, buttons=btns)
                except Exception:
                    await bot.send_message(uid, msg, buttons=btns)

        elif data == "wd_sales":
            s_bal = cur.execute("SELECT sales_balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
            if s_bal <= 0: return await e.answer("❌ Sales Balance is 0.", alert=True)
            btns = [[p_btn("To Main Balance (Instant)", "wd_to_main")], [p_btn("To UPI (Min ₹50)", "wd_to_upi")], [p_btn("Back", "menu_account")]]
            await e.edit(f"🤝 <b>Withdraw Sales Balance</b>\n\nAvailable: ₹{s_bal}\n\nSelect Method:", buttons=btns)

        elif data == "wd_to_main":
            async with get_user_lock(uid):
                s_bal = cur.execute("SELECT sales_balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
                if s_bal <= 0: return await e.answer("❌ Error.", alert=True)
                cur.execute("UPDATE users SET sales_balance = 0, balance = balance + ? WHERE user_id=?", (s_bal, uid))
                db.commit()
            await e.edit(f"{P_YES} <b>Successfully transferred ₹{s_bal} to Main Balance!</b>", buttons=[[p_btn("Back to Menu", "menu_account")]])

        elif data == "wd_to_upi":
            s_bal = cur.execute("SELECT sales_balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
            if s_bal < 50: return await e.answer("❌ Minimum ₹50 required for UPI withdrawal.", alert=True)
            wd_state[uid] = {'amount': s_bal}
            await e.edit(f"{P_BANK} <b>Enter your UPI ID to withdraw:</b>\n\n<i>Reply to this message with your exact UPI ID.</i>", buttons=[[p_btn("Cancel", "menu_account")]])

        elif data == "menu_sell":
            rows = cur.execute("SELECT country_code, year, price_good, price_spam FROM sell_prices").fetchall()
            if not rows: return await e.answer("Selling is disabled by Admin.", alert=True)
            msg = f"🤝 <b>Sell Your Accounts to Us!</b>\n\n<b>Allowed Countries:</b>\n"
            for r in rows: msg += f"• +{r[0]} ({r[1]}) | Good: ₹{r[2]} | Spam: ₹{r[3]}\n"
            msg += f"\n<i>Note: We charge a 10% admin fee on all sales.</i>\n\n👇 <b>Reply to this message with the phone number you want to sell (e.g., +919999999999):</b>"
            sell_state[uid] = {'step': 'wait_num'}
            await e.edit(msg, buttons=[[p_btn("Cancel", "menu_main")]])

        elif data.startswith("sell_chk|"):
            phone = data.split("|")[1]
            if phone in selling_accounts:
                st = selling_accounts[phone]
                if st.get('uid') != uid and not is_admin(uid):
                    return await safe_answer_cb(e, "❌ Unauthorized access.", alert=True)
                client = st['client']
                try:
                    auths = await client(GetAuthorizationsRequest())
                    count = len(auths.authorizations)
                    if count > 1:
                        await safe_answer_cb(e, f"⚠️ Active sessions: {count}. Delete other devices in Telegram App!", alert=True)
                    else:
                        await safe_answer_cb(e, "✅ Only 1 session active! Verification will complete soon.", alert=True)
                except Exception as ex:
                    await safe_answer_cb(e, f"Error checking sessions: {ex}", alert=True)
            else:
                await safe_answer_cb(e, "Session verification finished or expired.", alert=True)

        elif data.startswith("up_manage|"):
            phone = data.split("|")[1]
            row = cur.execute("SELECT seller_id FROM stock WHERE phone=?", (phone,)).fetchone()
            if not row or (row[0] != uid and not is_admin(uid)):
                return await safe_answer_cb(e, "❌ Unauthorized stock access.", alert=True)
            msg = f"📱 <b>Manage Account:</b> <code>+{phone}</code>\nWhat would you like to do?\n\n<i>You can only retrieve OTPs after removing the account from the marketplace.</i>"
            btns = [
                [p_btn("Remove Account & Get Login", f"up_rm|{phone}")],
                [p_btn("Back", "menu_uploads")]
            ]
            await e.edit(msg, buttons=btns)

        elif data.startswith("up_rm|"):
            phone = data.split("|")[1]
            row = cur.execute("SELECT seller_id FROM stock WHERE phone=?", (phone,)).fetchone()
            if not row or (row[0] != uid and not is_admin(uid)):
                return await safe_answer_cb(e, "❌ Unauthorized stock access.", alert=True)
            cur.execute("DELETE FROM stock WHERE phone=?", (phone,))
            cur.execute("INSERT OR REPLACE INTO blacklisted_phones (phone) VALUES (?)", (phone,))
            db.commit()
            await e.edit("✅ Account removed from market successfully.\n<i>Note: You cannot re-upload this specific number for 90 days.</i>\n\nClick below to securely access the account and OTP.", buttons=[[p_btn("Get Login / OTP", f"sell_get|{phone}")], [p_btn("Back", "menu_uploads")]])

        elif data.startswith("sell_get|"):
            phone = data.split("|")[1]
            sp = f"sessions/{phone}"

            dyn_id, dyn_hash = get_api_credentials()
            client = TelegramClient(sp, dyn_id, dyn_hash)
            await e.answer("🔄 Fetching latest OTP...", alert=False)
            try:
                await client.connect()
                msgs = await client.get_messages(777000, limit=3)
                code = next((re.search(OTP_REGEX, m.message).group() for m in msgs if m.message and re.search(OTP_REGEX, m.message)), "Not Found")
                await client.disconnect()

                msg = (f"{P_YES} <b>Account Retrieval Info</b>\n\n"
                       f"{P_PHONE} <b>Phone:</b> <code>{phone}</code>\n"
                       f"{P_TIME} <b>OTP:</b> <code>{code}</code>\n"
                       f"<i>Use this code to login and secure your account.</i>")
                btns = [[p_btn("🔄 Refresh OTP", f"sell_get|{phone}")], [p_btn("🚪 Delete Session", f"sell_rm_final|{phone}")]]
                try: await e.edit(msg, buttons=btns)
                except MessageNotModifiedError: pass
            except Exception as ex: await e.answer(f"Error: {ex}", alert=True)

        elif data.startswith("sell_rm_final|"):
            phone = data.split("|")[1]
            try:
                sp = f"sessions/{phone}"
                dyn_id, dyn_hash = get_api_credentials()
                client = TelegramClient(sp, dyn_id, dyn_hash)
                await client.connect()
                await client.log_out()
                await client.disconnect()
            except: pass
            delete_session_files(f"sessions/{phone}")
            await e.edit(f"{P_YES} <b>Session Deleted & Bot Logged Out successfully.</b>", buttons=[[p_btn("Back to Menu", "menu_main")]])

        elif data == "menu_history" or data.startswith("page_purchases_"):
            page = 1
            if data.startswith("page_purchases_"):
                try: page = int(data.split("_")[2])
                except: page = 1
            limit, offset = 5, (page - 1) * 5
            t_row = cur.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,)).fetchone()
            today_row = cur.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND date(date)=date('now')", (uid,)).fetchone()
            total = t_row[0] if t_row else 0
            today_total = today_row[0] if today_row else 0
            total_pages = max(1, (total + limit - 1) // limit)
            
            rows = cur.execute("SELECT id, phone, date, country, price, server FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?", (uid, limit, offset)).fetchall()
            
            msg = (f"{P_DOC} <b>PURCHASE HISTORY CENTER</b>\n"
                   f"━━━━━━━━━━━━━━━━━━━━\n"
                   f"📑 <b>Page:</b> {page} / {total_pages}\n"
                   f"🛒 <b>Total Purchases:</b> {total}\n"
                   f"🗓 <b>Purchases Today:</b> {today_total}\n"
                   f"━━━━━━━━━━━━━━━━━━━━\n\n")
            
            btns = []
            if not rows:
                msg += "<i>No purchase records found.</i>\n"
            else:
                for oid, ph, d, country, price, server in rows:
                    ph_str = str(ph)
                    if ph_str.startswith("LZT_"):
                        item_id = ph_str.replace("LZT_", "")
                        display_ph = f"Server 1 (Item #{item_id})"
                        opt_cb = f"lzt_otp|{item_id}"
                        log_cb = f"logout_finish|{item_id}"
                    else:
                        clean_ph = f"+{ph_str.lstrip('+')}" if ph_str.lstrip('+').isdigit() else ph_str
                        display_ph = clean_ph
                        opt_cb = f"get_otp_again|{ph_str}"
                        log_cb = f"logout_finish|{ph_str}"

                    c_flag = get_flag_by_country_name(country or "Unknown")
                    msg += (f"📦 <b>Order #{oid}</b>\n"
                            f"📱 <b>Number:</b> <code>{display_ph}</code>\n"
                            f"🏳️ <b>Details:</b> {c_flag} {html.escape(country or 'Unknown')} | {server or 'Server'}\n"
                            f"💰 <b>Price:</b> {format_price(uid, price or 0)}\n"
                            f"📅 <b>Date:</b> {format_purchase_datetime(d)}\n"
                            f"────────────────\n")
                    
                    row_action = [
                        p_btn(f"🔄 OTP #{oid}", opt_cb, style="primary"),
                        p_btn(f"🚪 Logout #{oid}", log_cb, style="danger")
                    ]
                    btns.append(row_action)

            nav = []
            if page > 1:
                nav.append(p_btn("⬅️ Prev", f"page_purchases_{page-1}", style="primary"))
            if offset + limit < total:
                nav.append(p_btn("Next ➡️", f"page_purchases_{page+1}", style="primary"))
            
            if nav:
                btns.append(nav)
            
            btns.append([
                p_btn("💳 View Deposit History", "menu_dephistory", style="success"),
                p_btn("Main Menu", "menu_main", style="danger")
            ])
            await safe_show_message(e, msg, buttons=btns)

        elif data == "menu_dephistory" or data.startswith("page_deposits_"):
            page = 1
            if data.startswith("page_deposits_"):
                try: page = int(data.split("_")[2])
                except: page = 1
            limit, offset = 5, (page - 1) * 5
            
            dep_rows = cur.execute("SELECT id, amount, method_name, status, date FROM deposits WHERE user_id=?", (uid,)).fetchall()
            upi_rows = cur.execute("SELECT order_id, amount, 'UPI Automatic', status, date FROM upi_orders WHERE user_id=?", (uid,)).fetchall()
            
            all_deps = []
            for d in dep_rows:
                all_deps.append({"id": f"D{d[0]}", "amt": d[1], "method": d[2] or "Deposit", "status": d[3] or "pending", "date": d[4]})
            for u in upi_rows:
                all_deps.append({"id": str(u[0]), "amt": u[1], "method": u[2], "status": u[3] or "pending", "date": u[4]})
            
            all_deps.sort(key=lambda x: str(x["date"]), reverse=True)
            total = len(all_deps)
            total_pages = max(1, (total + limit - 1) // limit)
            total_success_amt = sum(x["amt"] for x in all_deps if str(x["status"]).lower() in ("success", "approved", "completed"))
            
            page_items = all_deps[offset:offset+limit]
            
            msg = (f"💳 <b>DEPOSIT HISTORY CENTER</b>\n"
                   f"━━━━━━━━━━━━━━━━━━━━\n"
                   f"📑 <b>Page:</b> {page} / {total_pages}\n"
                   f"💰 <b>Total Credited:</b> {format_price(uid, total_success_amt)}\n"
                   f"📥 <b>Total Transactions:</b> {total}\n"
                   f"━━━━━━━━━━━━━━━━━━━━\n\n")
            
            if not page_items:
                msg += "<i>No deposit records found.</i>\n"
            else:
                for item in page_items:
                    st = str(item["status"]).lower()
                    if st in ("success", "approved", "completed"):
                        badge = "🟢 SUCCESS"
                    elif st in ("rejected", "failed"):
                        badge = "🔴 REJECTED"
                    else:
                        badge = "🟡 PENDING"

                    msg += (f"🆔 <b>ID:</b> <code>{item['id']}</code>\n"
                            f"💳 <b>Method:</b> {html.escape(item['method'])}\n"
                            f"💵 <b>Amount:</b> {format_price(uid, item['amt'])}\n"
                            f"📊 <b>Status:</b> {badge}\n"
                            f"📅 <b>Date:</b> {format_purchase_datetime(item['date'])}\n"
                            f"────────────────\n")
            
            btns = []
            nav = []
            if page > 1:
                nav.append(p_btn("⬅️ Prev", f"page_deposits_{page-1}", style="primary"))
            if offset + limit < total:
                nav.append(p_btn("Next ➡️", f"page_deposits_{page+1}", style="primary"))
            if nav:
                btns.append(nav)
            
            btns.append([
                p_btn("📦 View Purchase History", "menu_history", style="success"),
                p_btn("Main Menu", "menu_main", style="danger")
            ])
            await safe_show_message(e, msg, buttons=btns)

        elif data == "menu_help":
            btns = [
                [p_btn("📢 Updates Channel", url="https://t.me/FreshTgSals")],
                [p_btn("📜 Terms And Conditions", url=TERMS_URL)],
                [p_btn("💬 Contact For Support", url=get_support_url())],
                [p_btn("Back", "menu_main")]
            ]
            await e.edit(f"⛔️ <b>Help & Support</b>\n\nHow can we help you today? Please use the navigation links below:", buttons=btns)

        elif data.startswith("dep_upi"):
            if not is_method_on("upi_status"):
                return await e.answer("UPI deposits are currently disabled.", alert=True)
            await init_upi_keypad(e)
        elif data.startswith("depm_"): await manual_deposit_init(e, data.replace("depm_", ""))
        elif data.startswith("kp_"): await keypad_logic(e)
        elif data.startswith("check_upi_"): await verify_upi_payment(e, data.replace("check_upi_", ""))

        # --- KEYPAD DYNAMIC LOGIC FOR ADMINS ---
        elif data.startswith("kp_adm|"):
            parts = data.split("|")
            t_uid, order_id, d_type, action, cur_val = int(parts[1]), parts[2], parts[3], parts[4], parts[5]

            if action == "del":
                cur_val = cur_val[:-1]
            elif action == "confirm":
                final_amt = int(cur_val) if cur_val.isdigit() else 0
                if final_amt <= 0:
                    return await e.answer("❌ Console value must be larger than zero to confirm.", alert=True)

                update_balance(t_uid, final_amt)
                cur.execute("UPDATE users SET total_deposited = total_deposited + ? WHERE user_id=?", (final_amt, t_uid))

                if d_type == "upi":
                    cur.execute("UPDATE upi_orders SET status='success' WHERE order_id=?", (order_id,))
                elif d_type == "man":
                    cur.execute("UPDATE deposits SET status='success' WHERE id=?", (order_id.replace("M", ""),))

                method_label = "UPI Automatic" if d_type == "upi" else "Manual"
                if d_type == "man":
                    method_row = cur.execute("SELECT method_name FROM deposits WHERE id=?", (order_id.replace("M", ""),)).fetchone()
                    if method_row and method_row[0]:
                        method_label = method_row[0]

                db.commit()
                await log_primary_deposit(t_uid, final_amt, f"CONSOLE_{method_label}")
                await process_referral_bonus(t_uid, final_amt)
                try:
                    await bot.send_message(t_uid, f"✅ Your {html.escape(method_label)} payment of ₹{final_amt} has been approved and credited.")
                except:
                    pass
                await e.edit(f"✅ Approved <b>{html.escape(method_label)}</b> and credited ₹{final_amt} to user <code>{t_uid}</code>!")
                return
            else:
                if len(cur_val) < 6:
                    cur_val += action

            await render_admin_review_keypad(e, t_uid, order_id, d_type, cur_val)
            return

        # --- LOOKUP ACTIONS (LKA_) ---
        elif data.startswith("lka_") and is_admin(uid):
            parts = data.split("|")
            cmd = parts[0]

            if cmd == "lka_ban":
                t_uid = int(parts[1])
                is_banned = is_user_banned(t_uid)
                new_ban = 0 if is_banned else 1
                cur.execute("UPDATE users SET banned=? WHERE user_id=?", (new_ban, t_uid))
                db.commit()
                status_label = "UNBANNED 🟢" if new_ban == 0 else "BANNED 🔴"
                await e.answer(f"User {t_uid} {status_label}", alert=True)
                return await perform_360_user_lookup(e, uid, str(t_uid))

            elif cmd == "lka_back" or cmd == "lka_ref":
                t_uid = int(parts[1])
                lookup_action_state.pop(uid, None)
                lookup_search_state.pop(uid, None)
                await safe_answer_cb(e)
                return await perform_360_user_lookup(e, uid, str(t_uid))

            elif cmd == "lka_bal":
                mode = parts[1]
                t_uid = int(parts[2])
                u_disp = await get_user_display_name(t_uid)
                lookup_action_state[uid] = {"action": f"bal_{mode}", "target_id": t_uid}
                lbl = "Add" if mode == "add" else "Deduct"
                return await safe_show_message(
                    e,
                    f"💳 <b>{lbl} Balance for User {u_disp}</b>\n\nEnter the amount to {lbl.lower()} in INR. Type /cancel to abort.",
                    buttons=[[p_btn("Back to Profile", f"lka_back|{t_uid}", style="danger")]]
                )

            elif cmd == "lka_msg":
                t_uid = int(parts[1])
                u_disp = await get_user_display_name(t_uid)
                lookup_action_state[uid] = {"action": "send_msg", "target_id": t_uid}
                return await safe_show_message(
                    e,
                    f"💬 <b>Send Message to User {u_disp}</b>\n\nType the message text or send media to forward to this user. Type /cancel to abort.",
                    buttons=[[p_btn("Back to Profile", f"lka_back|{t_uid}", style="danger")]]
                )

            elif cmd == "lka_ords":
                t_uid = int(parts[1])
                page = int(parts[2]) if len(parts) > 2 else 1
                u_disp = await get_user_display_name(t_uid)
                limit, offset = 10, (page - 1) * 10
                orders = cur.execute("SELECT country, year, price, phone, date FROM orders WHERE user_id=? ORDER BY date DESC LIMIT ? OFFSET ?", (t_uid, limit, offset)).fetchall()
                total_cnt = cur.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (t_uid,)).fetchone()[0]
                msg = f"📦 <b>Orders History for User {u_disp}</b> (Page {page})\nTotal Orders: {total_cnt}\n\n"
                for c, y, p, ph, dt in orders:
                    msg += f"• {str(dt)[:16] if dt else '?'} | {c} ({y}) | ₹{p} | <code>{ph}</code>\n"
                if not orders: msg += "No orders on this page.\n"
                btns = []
                nav = []
                if page > 1: nav.append(p_btn("Prev", f"lka_ords|{t_uid}|{page-1}", style="primary"))
                if offset + limit < total_cnt: nav.append(p_btn("Next", f"lka_ords|{t_uid}|{page+1}", style="primary"))
                if nav: btns.append(nav)
                btns.append([p_btn("Back to Profile", f"lka_back|{t_uid}", style="danger")])
                return await safe_show_message(e, msg, buttons=btns)

            elif cmd == "lka_deps":
                t_uid = int(parts[1])
                page = int(parts[2]) if len(parts) > 2 else 1
                u_disp = await get_user_display_name(t_uid)
                limit, offset = 10, (page - 1) * 10
                deps = cur.execute("SELECT amount, method_name, status, date FROM deposits WHERE user_id=? ORDER BY date DESC LIMIT ? OFFSET ?", (t_uid, limit, offset)).fetchall()
                total_cnt = cur.execute("SELECT COUNT(*) FROM deposits WHERE user_id=?", (t_uid,)).fetchone()[0]
                msg = f"💳 <b>Recharges Log for User {u_disp}</b> (Page {page})\nTotal Recharges: {total_cnt}\n\n"
                for a, m, s, dt in deps:
                    st_icon = "🟢" if s == 'success' else ("🔴" if s == 'rejected' else "🟡")
                    msg += f"• {st_icon} {str(dt)[:16] if dt else '?'} | {m} ₹{a} | {str(s).upper()}\n"
                if not deps: msg += "No recharges on this page.\n"
                btns = []
                nav = []
                if page > 1: nav.append(p_btn("Prev", f"lka_deps|{t_uid}|{page-1}", style="primary"))
                if offset + limit < total_cnt: nav.append(p_btn("Next", f"lka_deps|{t_uid}|{page+1}", style="primary"))
                if nav: btns.append(nav)
                btns.append([p_btn("Back to Profile", f"lka_back|{t_uid}", style="danger")])
                return await safe_show_message(e, msg, buttons=btns)

            elif cmd == "lka_refs":
                t_uid = int(parts[1])
                page = int(parts[2]) if len(parts) > 2 else 1
                u_disp = await get_user_display_name(t_uid)
                limit, offset = 10, (page - 1) * 10
                refs = cur.execute("SELECT user_id, joined_date, total_deposited FROM users WHERE referred_by=? ORDER BY joined_date DESC LIMIT ? OFFSET ?", (t_uid, limit, offset)).fetchall()
                total_cnt = cur.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (t_uid,)).fetchone()[0]
                msg = f"👥 <b>Direct Referrals for User {u_disp}</b> (Page {page})\nTotal Referrals: {total_cnt}\n\n"
                for r_uid, j_dt, t_dep in refs:
                    r_disp = await get_user_display_name(r_uid)
                    msg += f"• User {r_disp} | Joined: {str(j_dt)[:10]} | Deposited: ₹{t_dep}\n"
                if not refs: msg += "No referrals found.\n"
                btns = []
                nav = []
                if page > 1: nav.append(p_btn("Prev", f"lka_refs|{t_uid}|{page-1}", style="primary"))
                if offset + limit < total_cnt: nav.append(p_btn("Next", f"lka_refs|{t_uid}|{page+1}", style="primary"))
                if nav: btns.append(nav)
                btns.append([p_btn("Back to Profile", f"lka_back|{t_uid}", style="danger")])
                return await safe_show_message(e, msg, buttons=btns)

        # --- ADMIN DASHBOARD INTERACTIONS ---
        elif data.startswith("adm_") and is_admin(uid):
            action = data[4:]

            if action == "adminmain":
                btns = [
                    [p_btn("🔍 User Lookup / Search", "adm_lookup", style="success"), p_btn("Sell Settings", "adm_sellset", style="primary")],
                    [p_btn("Server 1 Settings", "adm_lztset", style="primary"), p_btn("Manage Stock", "adm_managestock", style="primary")],
                    [p_btn("Add Stock (Single)", "adm_addstock", style="success"), p_btn("Bulk Upload (ZIP)", "adm_addzip", style="success")],
                    [p_btn("Statistics", "adm_stats", style="primary"), p_btn("Payments", "adm_payments", style="primary")],
                    [p_btn("Withdrawals", "adm_wdlist", style="primary"), p_btn("Toggle Server 1", "adm_tgl_s1", style="danger")],
                    [p_btn("Change Balance", "adm_bal", style="success"), p_btn("Ban User", "adm_ban", style="danger")],
                    [p_btn("User Info", "adm_userinfo", style="primary"), p_btn("Broadcast", "adm_bcast", style="primary")],
                    [p_btn("Discount", "adm_discount", style="primary"), p_btn("Create Promo Code", "adm_createpromo", style="success")],
                    [p_btn("Create Giveaway", "adm_creategiveaway", style="success"), p_btn("Ref %", "adm_refpct", style="primary")],
                    [p_btn("Min Deposit configuration", "adm_min_dep", style="primary"), p_btn("Game: Fight settings", "adm_tgl_fight", style="primary")],
                    [p_btn("Manage API ID/Hash", "adm_apis", style="primary"), p_btn("Bulk Upload Warnings", "adm_bulkwarn", style="primary")],
                    [p_btn("Toggle Bot Status", "adm_togglebot", style="danger"), p_btn("Auto Price Setup", "adm_autoprice", style="success")],
                    [p_btn("Backup Bot Data", "adm_backup", style="success"), p_btn("Restore Bot Data", "adm_restore", style="danger")],
                    [p_btn("Manage Admins", "adm_manageadmins", style="primary")],
                    [p_btn("💸 Sell Price List", "adm_spl", style="success")],
                    [p_btn("Back to Bot", "menu_main", style="danger")]
                ]
                await e.edit(f"💻 <b>Admin Dashboard</b>", buttons=btns)

            elif action == "spl" or action.startswith("spl_"):
                if not has_perm(uid, 'p_settings'):
                    return await e.answer("No permission.", alert=True)
                await handle_spl_admin(e, uid, data)

            elif action == "lookup" or action == "userinfo":
                lookup_search_state[uid] = True
                return await e.edit("🔍 <b>User 360° Lookup & Diagnostics</b>\n\nSend a User ID, Telegram Username (e.g. <code>@username</code>), Phone Number, Order ID, or UTR to inspect profile & diagnostics.\nType /cancel to abort.", buttons=[[p_btn("Cancel", "adm_adminmain", style="danger")]])

            elif action == "live_ref":
                await e.answer("Refreshing live stats...", alert=True)
                return await handle_live_command(e)

            elif action == "tgl_fight":
                curr = cur.execute("SELECT value FROM settings WHERE key='fight_game_status'").fetchone()[0]
                ns = 'off' if curr == 'on' else 'on'
                cur.execute("UPDATE settings SET value=? WHERE key='fight_game_status'", (ns,))
                db.commit()
                await e.answer(f"Fight game matches are now: {ns.upper()}", alert=True)

            elif action == "togglebot" and has_perm(uid, 'p_settings'):
                new_status = 'off' if is_bot_online() else 'on'
                cur.execute("UPDATE settings SET value=? WHERE key='bot_status'", (new_status,))
                db.commit()
                await e.answer(f"Bot turned {new_status.upper()}", alert=True)

            elif action == "tgl_s1" and has_perm(uid, 'p_settings'):
                curr = cur.execute("SELECT value FROM settings WHERE key='server1_status'").fetchone()[0]
                ns = 'off' if curr == 'on' else 'on'
                cur.execute("UPDATE settings SET value=? WHERE key='server1_status'", (ns,))
                db.commit()
                await e.answer(f"Server 1 turned {ns.upper()}", alert=True)

            elif action == "stats":
                u_row = cur.execute("SELECT COUNT(*) FROM users").fetchone()
                u = u_row[0] if u_row else 0
                s_row = cur.execute("SELECT COUNT(*) FROM stock WHERE available=1").fetchone()
                s = s_row[0] if s_row else 0
                r_row = cur.execute("SELECT value FROM settings WHERE key='upi_revenue'").fetchone()
                r = r_row[0] if r_row else "0"
                bal_row = cur.execute("SELECT SUM(balance) FROM users").fetchone()
                total_bal = bal_row[0] if bal_row and bal_row[0] else 0
                o_row = cur.execute("SELECT COUNT(*), SUM(price) FROM orders").fetchone()
                total_orders = o_row[0] if o_row else 0
                total_spent = o_row[1] if o_row and o_row[1] else 0

                msg = (f"📊 <b>ADVANCED STATS</b>\n\n👥 <b>Total Users:</b> {u}\n📦 <b>Accounts in Stock:</b> {s}\n"
                       f"💰 <b>Total UPI Revenue:</b> ₹{r}\n\n💳 <b>Overall Users Balance:</b> ₹{total_bal}\n"
                       f"🛒 <b>Total Accounts Sold:</b> {total_orders}\n💲 <b>Overall Sales Amount:</b> ₹{total_spent}")
                return await e.edit(msg, buttons=[[p_btn("Back", "adm_adminmain")]])

            elif action == "autoprice" and has_perm(uid, 'p_manage_stock'):
                rows = cur.execute("SELECT country, year, price FROM auto_prices ORDER BY country, year LIMIT 30").fetchall()
                msg = "🤖 <b>Auto Price Setup</b>\n\nAuto prices are used during single and ZIP session upload.\n\n"
                msg += "<i>No auto prices set yet.</i>" if not rows else "".join([f"• {html.escape(str(c))} ({y}) = ₹{p}\n" for c, y, p in rows])
                btns = [[p_btn("➕ Set Auto Price", "adm_autoprice_set", style="success")], [p_btn("Back", "adm_adminmain", style="danger")]]
                return await e.edit(msg, buttons=btns)

            elif action == "backup" and has_perm(uid, 'p_settings'):
                try:
                    backup_path = f"otp_bot_backup_{int(time.time())}.db"
                    dst = sqlite3.connect(backup_path)
                    db.backup(dst)
                    dst.close()
                    await bot.send_file(uid, backup_path, caption="✅ Bot data backup")
                    os.remove(backup_path)
                except Exception as ex:
                    await send_admin_error("Backup failed", str(ex))
                    await e.answer("Backup failed", alert=True)
                return

            elif action == "restore" and has_perm(uid, 'p_settings'):
                restore_state[uid] = True
                return await e.edit("♻️ <b>Restore Bot Data</b>\n\nSend the backup .db file as a document in this chat. Type /cancel to abort.", buttons=[[p_btn("Cancel", "adm_adminmain")]])

            elif action == "sellset":
                rows = cur.execute("SELECT * FROM sell_prices").fetchall()
                msg = f"🤝 <b>Manage Allowed Sell Countries</b>\n\n"
                for r in rows: msg += f"+{r[0]} ({r[1]}) | Good: ₹{r[2]} | Spam: ₹{r[3]}\n"
                btns = [[p_btn("Add/Edit Country", "adm_addsell", style="success")], [p_btn("Remove Country", "adm_rmsell", style="danger")], [p_btn("Back", "adm_adminmain", style="danger")]]
                await e.edit(msg, buttons=btns)

            elif action == "lztset":
                g = cur.execute("SELECT value FROM settings WHERE key='lzt_global_markup'").fetchone()[0]
                s1_status = "ON" if cur.execute("SELECT value FROM settings WHERE key='server1_status'").fetchone()[0] == 'on' else "OFF"

                lzt_bal = "Error"
                try:
                    me_res = await lzt_request('GET', '/me')
                    if me_res and 'user' in me_res:
                        lzt_bal = me_res['user'].get('balance', 'Error')
                except: pass

                msg = f"🌍 <b>Server 1 Settings</b>\nServer 1 Status: {s1_status}\nMarket Balance: {lzt_bal} RUB\nGlobal Markup: {g}%\n\nCustom Country Markups:\n"
                rows = cur.execute("SELECT * FROM lzt_settings").fetchall()
                for r in rows: msg += f"{r[0]}: {r[1]}%\n"

                btns = [
                    [p_btn("Set Global Markup", "adm_setgmarkup", style="primary")],
                    [p_btn("Set Custom Country Markup", "adm_setcmarkup", style="primary")],
                    [p_btn("Set Market Token", "adm_setlzttoken", style="success")],
                    [p_btn("Back", "adm_adminmain", style="danger")]
                ]
                await e.edit(msg, buttons=btns)

            elif action == "wdlist":
                rows = cur.execute("SELECT id, user_id, amount, method, details FROM withdrawals WHERE status='pending' LIMIT 10").fetchall()
                if not rows: return await e.edit("No pending withdrawals.", buttons=[[p_btn("Back", "adm_adminmain")]])
                msg = f"💳 <b>Pending Withdrawals</b>\n\n"
                btns = []
                for r in rows:
                    msg += f"ID: {r[0]} | User: {r[1]} | ₹{r[2]} | {r[3]}: {r[4]}\n"
                    btns.append([p_btn(f"✅ App #{r[0]}", f"wd_act|app|{r[0]}", style="success"), p_btn(f"❌ Rej #{r[0]}", f"wd_act|rej|{r[0]}", style="danger")])
                btns.append([p_btn("Back", "adm_adminmain", style="danger")])
                await e.edit(msg, buttons=btns)

            elif action == "payments" and has_perm(uid, 'p_settings'):
                upi_st = "ON" if is_method_on("upi_status") else "OFF"
                cw_st = "ON" if is_method_on("cwallet_status") else "OFF"
                btns = [
                    [p_btn(f"UPI: {upi_st}", "adm_tgl_upi", style="primary"), p_btn(f"Cwallet: {cw_st}", "adm_tgl_cw", style="primary")],
                    [p_btn("Set $ Rate", "adm_usdtrate", style="primary")],
                    [p_btn("Add Payment Method", "adm_addpay", style="success")],
                    [p_btn("Remove Payment Method", "adm_delpay", style="danger")],
                    [p_btn("Back", "adm_adminmain", style="danger")]
                ]
                await e.edit(f"💳 <b>Manage Payment Methods</b>", buttons=btns)
            elif action == "tgl_upi" and has_perm(uid, 'p_settings'):
                ns = 'off' if is_method_on("upi_status") else 'on'
                cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('upi_status', ?)", (ns,))
                db.commit()
                await e.answer(f"UPI {ns.upper()}", alert=True)
            elif action == "tgl_cw" and has_perm(uid, 'p_settings'):
                ns = 'off' if is_method_on("cwallet_status") else 'on'
                cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('cwallet_status', ?)", (ns,))
                db.commit()
                await e.answer(f"Cwallet {ns.upper()}", alert=True)

            elif action == "manageadmins" and uid == ADMIN_ID:
                rows = cur.execute("SELECT user_id FROM admins").fetchall()
                msg = f"👥 <b>Manage Sub-Admins</b>\n\n"
                for r in rows: msg += f"👤 <code>{r[0]}</code>\n"
                btns = [[p_btn("Add Admin", "adm_addadmin", style="success"), p_btn("Edit Admin", "adm_editadminreq", style="primary")], [p_btn("Back", "adm_adminmain", style="danger")]]
                await e.edit(msg, buttons=btns)

            elif action == "managestock" and has_perm(uid, 'p_manage_stock'):
                rows = cur.execute("SELECT DISTINCT country_name FROM stock ORDER BY country_name LIMIT 10 OFFSET 0").fetchall()
                btns = [[p_btn(f"{get_flag_by_country_name(c[0])} {c[0]}", f"adm_msc|{c[0]}")] for c in rows]
                btns.append([p_btn("🤖 Auto Price Setup", "adm_autoprice")])
                btns.append([p_btn("Next", "adm_mspg|2"), p_btn("Back", "adm_adminmain")])
                await e.edit(f"📜 <b>Manage Stock</b> (Page 1)", buttons=btns)

            elif action.startswith("mspg|") and has_perm(uid, 'p_manage_stock'):
                page = int(action.split("|")[1])
                limit, offset = 10, (page - 1) * 10
                rows = cur.execute("SELECT DISTINCT country_name FROM stock ORDER BY country_name LIMIT ? OFFSET ?", (limit, offset)).fetchall()
                total = cur.execute("SELECT COUNT(DISTINCT country_name) FROM stock").fetchone()[0]
                btns = [[p_btn(f"{get_flag_by_country_name(c[0])} {c[0]}", f"adm_msc|{c[0]}")] for c in rows]
                nav = []
                if page > 1: nav.append(p_btn("Prev", f"adm_mspg|{page-1}"))
                if offset + limit < total: nav.append(p_btn("Next", f"adm_mspg|{page+1}"))
                if nav: btns.append(nav)
                btns.append([p_btn("Back", "adm_adminmain")])
                await e.edit(f"📜 <b>Manage Stock</b> (Page {page})", buttons=btns)

            elif action.startswith("msc|") and has_perm(uid, 'p_manage_stock'):
                c_name = action.split("|")[1]
                years = cur.execute("SELECT DISTINCT account_year FROM stock WHERE country_name=? ORDER BY account_year DESC", (c_name,)).fetchall()
                btns = [[p_btn("Edit Country Name", f"adm_msedit|name|{c_name}"), p_btn("Edit Flag", f"adm_msedit|flag|{c_name}")], [p_btn("Edit Common Price", f"adm_msedit|cprice|{c_name}")] ]
                y_btns = []
                for (y,) in years: y_btns.append(p_btn(f"{y}", f"adm_msedit|yprice|{c_name}|{y}"))
                for i in range(0, len(y_btns), 3): btns.append(y_btns[i:i+3])
                btns.append([p_btn("Back", "adm_mspg|1")])
                await e.edit(f"{get_flag_by_country_name(c_name)} <b>Managing: {c_name}</b>", buttons=btns)

            # ADMIN CONVERSATIONS
            else:
                async def get_reply(txt):
                    prompt_text = txt + "\n<i>(Reply to this message. Type /cancel to abort)</i>"
                    async with bot.conversation(uid, timeout=600) as conv:
                        m = await conv.send_message(prompt_text)
                        while True:
                            resp = await conv.get_response()
                            msg_text = (resp.text or "").strip()
                            if msg_text.lower() == "/cancel":
                                raise ConversationCancelled("Cancelled")
                            is_reply = getattr(resp, "reply_to_msg_id", None) == m.id
                            if not is_reply:
                                continue
                            return resp

                try:
                    if action == "addsell":
                        c = (await get_reply("Enter Country Code (e.g., 91):")).text.replace("+", "")
                        y = (await get_reply("Enter Year (e.g., 2024 or 'Common'):")).text
                        pg = int((await get_reply("Enter Price for Good Account (₹):")).text)
                        ps = int((await get_reply("Enter Price for Spam Account (₹):")).text)
                        cur.execute("INSERT OR REPLACE INTO sell_prices (country_code, year, price_good, price_spam) VALUES (?,?,?,?)", (c, y, pg, ps))
                        db.commit()
                        await bot.send_message(uid, f"✅ Saved Sell Settings for +{c} ({y})!")

                    elif action == "min_dep":
                        cur_upi = cur.execute("SELECT value FROM settings WHERE key='min_upi_dep'").fetchone()[0]
                        cur_cw = cur.execute("SELECT value FROM settings WHERE key='min_cw_dep'").fetchone()[0]
                        upi_val = int((await get_reply(f"💵 <b>Current UPI Minimum: ₹{cur_upi}</b>\n\nEnter new minimum limit:")).text)
                        cw_val = int((await get_reply(f"💵 <b>Current Cwallet Minimum: ₹{cur_cw}</b>\n\nEnter new minimum limit:")).text)
                        cur.execute("UPDATE settings SET value=? WHERE key='min_upi_dep'", (str(upi_val),))
                        cur.execute("UPDATE settings SET value=? WHERE key='min_cw_dep'", (str(cw_val),))
                        db.commit()
                        await bot.send_message(uid, f"✅ Wallet minimum configurations updated successfully!")

                    elif action == "rmsell":
                        c = (await get_reply("Enter Country Code to remove:")).text.replace("+", "")
                        y = (await get_reply("Enter Year to remove (or type 'All'):")).text
                        if y.lower() == 'all': cur.execute("DELETE FROM sell_prices WHERE country_code=?", (c,))
                        else: cur.execute("DELETE FROM sell_prices WHERE country_code=? AND year=?", (c, y))
                        db.commit()
                        await bot.send_message(uid, f"✅ Removed settings for +{c}.")

                    elif action == "setgmarkup":
                        m = int((await get_reply("Enter Global Markup %:")).text)
                        cur.execute("UPDATE settings SET value=? WHERE key='lzt_global_markup'", (str(m),))
                        db.commit()
                        clear_lzt_cache()
                        await bot.send_message(uid, f"✅ Global markup set to {m}%. Server 1 stock cache refreshed.")

                    elif action == "setcmarkup":
                        buttons, page, total_pages = build_country_markup_buttons(1)
                        await e.edit(
                            f"🌍 <b>Select country for custom Server 1 markup</b>\n\n"
                            f"Page {page}/{total_pages}. Button values show the currently effective markup.\n"
                            f"After selecting a country, send the custom markup percent. Send <code>0</code> to remove its custom markup and use global markup.",
                            buttons=buttons
                        )

                    elif action.startswith("cmarkpg|"):
                        page = int(action.split("|")[1])
                        buttons, page, total_pages = build_country_markup_buttons(page)
                        await e.edit(
                            f"🌍 <b>Select country for custom Server 1 markup</b>\n\nPage {page}/{total_pages}.",
                            buttons=buttons
                        )

                    elif action.startswith("cmark|"):
                        iso = action.split("|")[1]
                        country = next((name for name, data in COUNTRY_CODES.items() if data[0] == iso), None)
                        if not country:
                            return await e.answer("Country not found.", alert=True)
                        current_markup = get_lzt_markup(country)
                        m = int((await get_reply(
                            f"💹 <b>{COUNTRY_CODES[country][1]} {country}</b> current effective markup: <b>{current_markup}%</b>\n\n"
                            f"Enter custom markup % for this country. Send <code>0</code> to remove custom markup and use global markup."
                        )).text)
                        if m == 0:
                            cur.execute("DELETE FROM lzt_settings WHERE LOWER(country)=LOWER(?) OR LOWER(country)=LOWER(?)", (country, iso))
                            result = f"✅ Removed custom markup for {country}. It now uses global markup."
                        else:
                            cur.execute("INSERT OR REPLACE INTO lzt_settings (country, markup_percent) VALUES (?,?)", (country, m))
                            result = f"✅ Custom markup for {country} set to {m}%."
                        db.commit()
                        clear_lzt_cache()
                        await bot.send_message(uid, result)

                    elif action == "setlzttoken":
                        token_input = (await get_reply("Enter API token (or type 'remove' to clear):")).text.strip()
                        global _lzt_missing_logged
                        if token_input.lower() == "remove":
                            cur.execute("DELETE FROM settings WHERE key='lzt_token'")
                            db.commit()
                            save_env_key("LZT_TOKEN", "")
                            _lzt_missing_logged = False
                            await bot.send_message(uid, f"✅ Token removed and cleared from .env.")
                        else:
                            clean_token = token_input.replace("Bearer ", "").strip()
                            cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('lzt_token', ?)", (clean_token,))
                            db.commit()
                            save_env_key("LZT_TOKEN", clean_token)
                            _lzt_missing_logged = False
                            await bot.send_message(uid, f"✅ Token saved and synchronized to .env file.")

                    elif action == "apis" and has_perm(uid, 'p_settings'):
                        rows = cur.execute("SELECT id, api_id, label, active, added_date FROM api_credentials ORDER BY id DESC LIMIT 30").fetchall()
                        msg = "🔐 <b>Telegram API Pool</b>\n\n"
                        if rows:
                            for api_pk, api_id_val, label, active, added in rows:
                                status = "✅ ON" if active else "⛔ OFF"
                                msg += f"ID <code>{api_pk}</code> | <code>{api_id_val}</code> | {html.escape(label or 'API')} | {status}\n"
                        else:
                            msg += "No custom API credentials added yet. Bot is using fallback/default credentials.\n"
                        msg += "\nAdd multiple API ID/HASH pairs to rotate Server 2 session logins and reduce repeated API reuse."
                        btns = [
                            [p_btn("➕ Add API", "adm_addapi"), p_btn("🗑 Delete API", "adm_delapi")],
                            [p_btn("🔁 Toggle API", "adm_tglapi")],
                            [p_btn("Back", "adm_adminmain")]
                        ]
                        await e.edit(msg, buttons=btns)

                    elif action == "addapi" and has_perm(uid, 'p_settings'):
                        new_api_id = (await get_reply("Enter Telegram API ID (numeric):")).text.strip()
                        if not new_api_id.isdigit():
                            return await bot.send_message(uid, "❌ API ID must be numeric.")
                        new_api_hash = (await get_reply("Enter Telegram API HASH:")).text.strip()
                        if not new_api_hash:
                            return await bot.send_message(uid, "❌ API HASH cannot be empty.")
                        label = (await get_reply("Enter a short label/name for this API:")).text.strip() or f"API {new_api_id}"
                        cur.execute("INSERT INTO api_credentials (api_id, api_hash, label, active) VALUES (?,?,?,1)", (int(new_api_id), new_api_hash, label[:60]))
                        db.commit()
                        await bot.send_message(uid, f"✅ API added to rotation. ID: <code>{new_api_id}</code> Label: <b>{html.escape(label[:60])}</b>")

                    elif action == "delapi" and has_perm(uid, 'p_settings'):
                        api_pk = (await get_reply("Send API row ID to delete. Open Manage API ID/Hash to see IDs.")).text.strip()
                        if not api_pk.isdigit():
                            return await bot.send_message(uid, "❌ Row ID must be numeric.")
                        cur.execute("DELETE FROM api_credentials WHERE id=?", (int(api_pk),))
                        db.commit()
                        await bot.send_message(uid, "✅ API row deleted." if cur.rowcount else "❌ API row not found.")

                    elif action == "tglapi" and has_perm(uid, 'p_settings'):
                        api_pk = (await get_reply("Send API row ID to toggle ON/OFF. Open Manage API ID/Hash to see IDs.")).text.strip()
                        if not api_pk.isdigit():
                            return await bot.send_message(uid, "❌ Row ID must be numeric.")
                        row = cur.execute("SELECT active FROM api_credentials WHERE id=?", (int(api_pk),)).fetchone()
                        if not row:
                            return await bot.send_message(uid, "❌ API row not found.")
                        new_active = 0 if row[0] else 1
                        cur.execute("UPDATE api_credentials SET active=? WHERE id=?", (new_active, int(api_pk)))
                        db.commit()
                        await bot.send_message(uid, f"✅ API row is now {'ON' if new_active else 'OFF'}.")

                    elif action == "setapi" and has_perm(uid, 'p_settings'):
                        new_api_id = (await get_reply("Enter your Telegram API ID (numeric):")).text.strip()
                        if not new_api_id.isdigit():
                            return await bot.send_message(uid, "❌ API ID must be numeric.")
                        new_api_hash = (await get_reply("Enter your Telegram API HASH:")).text.strip()
                        if not new_api_hash:
                            return await bot.send_message(uid, "❌ API HASH cannot be empty.")

                        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('api_id', ?)", (new_api_id,))
                        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('api_hash', ?)", (new_api_hash,))
                        cur.execute("INSERT INTO api_credentials (api_id, api_hash, label, active) VALUES (?,?,?,1)", (int(new_api_id), new_api_hash, f"Legacy {new_api_id}"))
                        db.commit()
                        await bot.send_message(uid, f"✅ API credentials saved and added to rotation. API ID: {new_api_id}")

                    elif action == "bulkwarn":
                        warning_text = (
                            f"⚠️ <b>BULK SESSION UPLOAD SAFEGUARDS & WARNINGS</b>\n\n"
                            f"Uploading bulk accounts simultaneously carries high risks of account freezes or bans if proper parameters are not maintained:\n\n"
                            f"1️⃣ <b>IP Address Consistency</b>: If sessions are created on different IP ranges and suddenly logged in from the bot's server IP simultaneously, Telegram may flag them as suspicious and freeze them.\n"
                            f"2️⃣ <b>API ID & Hash Matches</b>: Ensure the API ID and API Hash matched in the session matches what the bot currently uses. Mismatched API details during requests trigger quick terminations.\n"
                            f"3️⃣ <b>Lack of Delays</b>: Accessing bulk sessions consecutively without sufficient delays flags automated scraping activity.\n\n"
                            f"<i>💡 Recommendation: Always test with 1-2 accounts before performing major bulk uploads.</i>"
                        )
                        await bot.send_message(uid, warning_text, buttons=[[p_btn("Back", "adm_adminmain")]])

                    elif action == "ap_add_country" and has_perm(uid, 'p_manage_stock'):
                        code = (await get_reply(f"📱 <b>Enter Country Calling Code (without +):</b>\n<i>Example: 91</i>")).text.replace("+", "").strip()
                        flag = html.escape((await get_reply(f"🏳️ <b>Enter Country Flag Emoji:</b>\n<i>Example: 🇮🇳</i>")).text.strip())
                        name = html.escape((await get_reply(f"🌍 <b>Enter Country Name:</b>\n<i>Example: India</i>")).text.strip())
                        cur.execute("INSERT OR REPLACE INTO custom_countries (code, name, flag) VALUES (?,?,?)", (code, name, flag))
                        db.commit()
                        await bot.send_message(uid, f"✅ <b>Custom Country Added Successfully!</b>\n{flag} {name} (+{code})")

                    elif action == "userinfo" and has_perm(uid, 'p_stats'):
                        t_uid = int((await get_reply(f"👤 <b>Enter User ID:</b>")).text)
                        u_row = cur.execute("SELECT balance, total_deposited, joined_date, banned, discount FROM users WHERE user_id=?", (t_uid,)).fetchone()
                        if not u_row: return await bot.send_message(uid, f"❌ User not found.")

                        o_row = cur.execute("SELECT COUNT(*), SUM(price) FROM orders WHERE user_id=?", (t_uid,)).fetchone()
                        up_row = cur.execute("SELECT SUM(amount) FROM upi_orders WHERE user_id=? AND status='success'", (t_uid,)).fetchone()

                        bal, dep, joined, is_banned, disc = u_row
                        o_count = o_row[0] if o_row else 0
                        o_spent = o_row[1] if o_row and o_row[1] else 0
                        u_upi = up_row[0] if up_row and up_row[0] else 0

                        msg = (f"👤 <b>USER INFO:</b> <code>{t_uid}</code>\n\n"
                               f"💰 Balance: ₹{bal}\n"
                               f"💳 Total Deposited: ₹{dep}\n"
                               f"🏦 UPI Deposited: ₹{u_upi}\n"
                               f"🛒 Total Orders: {o_count}\n"
                               f"💲 Total Spent: ₹{o_spent}\n"
                               f"🎁 Discount: {disc}%\n"
                               f"📅 Joined: {joined}\n"
                               f"🚫 Banned: {'Yes' if is_banned else 'No'}")
                        ban_label = "✅ Unban User" if is_banned else "🚫 Ban User"
                        await bot.send_message(uid, msg, buttons=[[p_btn(ban_label, "adm_ban")]])

                    elif action == "addadmin" and uid == ADMIN_ID:
                        new_ad = int((await get_reply(f"👤 <b>Enter User ID for new Admin:</b>")).text)
                        cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_ad,))
                        db.commit()
                        await bot.send_message(uid, f"✅ Admin added!")
                        class FakeEvent:
                            async def edit(self, text, buttons): await bot.send_message(uid, text, buttons=buttons)
                            async def answer(self, txt, alert): pass
                        await edit_admin_menu(FakeEvent(), new_ad)

                    elif action == "editadminreq" and uid == ADMIN_ID:
                        t_id = int((await get_reply(f"👤 <b>Enter User ID to edit:</b>")).text)
                        class FakeEvent:
                            async def edit(self, text, buttons): await bot.send_message(uid, text, buttons=buttons)
                            async def answer(self, txt, alert): pass
                        await edit_admin_menu(FakeEvent(), t_id)

                    elif action.startswith("msedit|") and has_perm(uid, 'p_manage_stock'):
                        parts = action.split("|")
                        m_act, c_name = parts[1], parts[2]
                        if m_act == "name":
                            new_name = html.escape((await get_reply(f"📜 <b>Enter NEW Name for {c_name}:</b>")).text)
                            cur.execute("UPDATE stock SET country_name=? WHERE country_name=?", (new_name, c_name))
                            cur.execute("UPDATE auto_prices SET country=? WHERE country=?", (new_name, c_name))
                            db.commit()
                            await bot.send_message(uid, f"✅ Country '{c_name}' successfully renamed to '{new_name}'!")
                        elif m_act == "flag":
                            new_flag = html.escape((await get_reply(f"🏳️ <b>Enter NEW Flag Emoji for {c_name}:</b>")).text)
                            cur.execute("UPDATE stock SET country_icon=? WHERE country_name=?", (new_flag, c_name))
                            db.commit()
                            await bot.send_message(uid, f"✅ Flag updated to {new_flag} for '{c_name}'!")
                        elif m_act == "cprice":
                            new_p = int((await get_reply(f"💰 <b>Enter NEW Common Price for all {c_name} accounts:</b>")).text)
                            cur.execute("UPDATE stock SET price=? WHERE country_name=?", (new_p, c_name))
                            db.commit()
                            await bot.send_message(uid, f"✅ All existing '{c_name}' accounts updated to ₹{new_p}!")
                        elif m_act == "yprice":
                            year = parts[3]
                            new_p = int((await get_reply(f"💰 <b>Enter NEW Price for {c_name} ({year}):</b>")).text)
                            cur.execute("UPDATE stock SET price=? WHERE country_name=? AND account_year=?", (new_p, c_name, year))
                            db.commit()
                            await bot.send_message(uid, f"✅ All existing '{c_name}' ({year}) accounts updated to ₹{new_p}!")

                    elif action.startswith("apset|") and has_perm(uid, 'p_manage_stock'):
                        parts = action.split("|")
                        c_name, year = parts[1], parts[2]
                        new_p = int((await get_reply(f"🤖 <b>Enter Auto-Price for {c_name} ({year}):</b>\n<i>(Enter 0 to remove this auto-price)</i>")).text)
                        if new_p == 0:
                            cur.execute("DELETE FROM auto_prices WHERE country=? AND year=?", (c_name, year))
                            await bot.send_message(uid, f"✅ Auto-Price for {c_name} ({year}) removed!")
                        else:
                            cur.execute("INSERT OR REPLACE INTO auto_prices (country, year, price) VALUES (?,?,?)", (c_name, year, new_p))
                            await bot.send_message(uid, f"✅ Auto-Price for {c_name} ({year}) set to ₹{new_p}! Incoming accounts will use this price automatically.")
                        db.commit()

                    elif action == "addpay" and has_perm(uid, 'p_settings'):
                        name = html.escape((await get_reply(f"💳 <b>Enter Payment Method Name:</b>")).text)
                        qr_msg = await get_reply(f"📸 <b>Send QR Code Image (Or type 'skip'):</b>")
                        qr_path = ""
                        if qr_msg.photo:
                            qr_path = f"qr_{int(time.time())}.jpg"
                            await bot.download_media(qr_msg, qr_path)
                        cap_msg = (await get_reply(f"📜 <b>Enter Payment Caption:</b>")).text
                        cap_msg = html.escape(cap_msg).replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
                        cur.execute("INSERT INTO custom_payments (name, caption, qr_file_id) VALUES (?,?,?)", (name, cap_msg, qr_path))
                        db.commit()
                        await bot.send_message(uid, f"✅ Payment Method '{name}' added successfully!")

                    elif action == "delpay" and has_perm(uid, 'p_settings'):
                        rows = cur.execute("SELECT id, name FROM custom_payments").fetchall()
                        if not rows: return await bot.send_message(uid, f"❌ No custom payment methods.")
                        msg = f"📜 <b>Reply with the ID of the method to delete:</b>\n\n"
                        for r in rows: msg += f"ID: {r[0]} - {r[1]}\n"
                        del_id = int((await get_reply(msg)).text)
                        file_path = cur.execute("SELECT qr_file_id FROM custom_payments WHERE id=?", (del_id,)).fetchone()
                        if file_path and file_path[0] and os.path.exists(file_path[0]): os.remove(file_path[0])
                        cur.execute("DELETE FROM custom_payments WHERE id=?", (del_id,))
                        db.commit()
                        await bot.send_message(uid, f"✅ Deleted!")

                    elif action == "addzip" and has_perm(uid, 'p_add_stock'):
                        resp = await get_reply(f"📦 <b>Send the ZIP file containing <code>.session</code> files:</b>")
                        if not resp.file or not (resp.file.name or "").lower().endswith('.zip'):
                            return await bot.send_message(uid, f"❌ Invalid file.")

                        await bot.send_message(uid, f"⏳ <b>Extracting & Scanning Accounts...</b>")
                        os.makedirs("sessions", exist_ok=True)
                        zip_path = await bot.download_media(resp, "temp_sessions.zip")
                        if not zip_path or not os.path.exists(zip_path):
                            return await bot.send_message(uid, f"❌ Could not download ZIP file.")

                        extracted_dir = f"temp_extracted_{int(time.time())}"
                        os.makedirs(extracted_dir, exist_ok=True)
                        try:
                            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                                for member in zip_ref.infolist():
                                    target = os.path.abspath(os.path.join(extracted_dir, member.filename))
                                    if not target.startswith(os.path.abspath(extracted_dir) + os.sep):
                                        raise ValueError("Unsafe ZIP path detected")
                                zip_ref.extractall(extracted_dir)

                            groups = {}
                            for root, _, files in os.walk(extracted_dir):
                                for file in files:
                                    if not file.endswith(".session"):
                                        continue
                                    sess_path = os.path.join(root, file)
                                    clean_path = sess_path[:-8]
                                    client = None
                                    try:
                                        dyn_id, dyn_hash = get_random_api_credentials()
                                        client = TelegramClient(clean_path, dyn_id, dyn_hash)
                                        await client.connect()
                                        if not await client.is_user_authorized():
                                            continue
                                        me = await client.get_me()
                                        phone = getattr(me, 'phone', None)
                                        if not phone:
                                            continue

                                        c_name, c_icon, _ = get_country_info(phone)
                                        pwd = await client(GetPasswordRequest())
                                        has_2fa = pwd.has_password
                                        year = await detect_account_year(client)

                                        key = (c_name, year, has_2fa)
                                        if key not in groups:
                                            groups[key] = []
                                        groups[key].append({"phone": phone, "path": clean_path, "c_icon": c_icon})
                                    except Exception as ex:
                                        logger.error(f"Scan error: {ex}")
                                    finally:
                                        if client and client.is_connected():
                                            await client.disconnect()

                            for key in list(groups.keys()):
                                if key[0] == "Unknown":
                                    sample_phone = groups[key][0]["phone"]
                                    await bot.send_message(uid, f"⚠️ <b>Country not recognized for +{sample_phone}!</b>")
                                    new_icon = html.escape((await get_reply(f"🏳️ <b>Enter Country Flag Emoji:</b>")).text)
                                    new_name = html.escape((await get_reply(f"🌍 <b>Enter Country Name:</b>")).text)
                                    new_key = (new_name, key[1], key[2])
                                    groups[new_key] = groups.pop(key)
                                    for acc in groups[new_key]:
                                        acc["c_icon"] = new_icon

                            success = 0
                            for (c_name, year, has_2fa), accs in groups.items():
                                c_icon = accs[0]["c_icon"]
                                twofa_pass = "None"
                                if has_2fa:
                                    twofa_pass = html.escape((await get_reply(f"🔐 <b>Enter 2FA Password for {len(accs)}x {c_name} accounts:</b>")).text)
                                auto_row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year=?", (c_name, str(year))).fetchone()
                                if not auto_row:
                                    auto_row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year='Common'", (c_name,)).fetchone()
                                if auto_row:
                                    price = auto_row[0]
                                    await bot.send_message(uid, f"⚡ <b>Auto-Price Applied:</b> {len(accs)}x {c_name} ({year}) at ₹{price}.")
                                else:
                                    existing_price = cur.execute("SELECT price FROM stock WHERE country_name=? LIMIT 1", (c_name,)).fetchone()
                                    if existing_price:
                                        price = existing_price[0]
                                        await bot.send_message(uid, f"⚡ <b>Auto-Added:</b> {len(accs)}x {c_name} at ₹{price} (Copied from DB).")
                                    else:
                                        price = int((await get_reply(f"📌 Found {len(accs)}x {c_name} ({year}).\n💰 Enter Price (₹):")).text)

                                for acc in accs:
                                    perm_base = os.path.join("sessions", str(acc['phone']))
                                    for ext in ['.session', '.session-wal', '.session-shm', '.session-journal']:
                                        source_path = acc['path'] + ext
                                        if os.path.exists(source_path):
                                            shutil.move(source_path, perm_base + ext)
                                    cur.execute("INSERT OR REPLACE INTO stock (phone, session_file, country_name, country_icon, account_year, category, price, available, twofa) VALUES (?,?,?,?,?,?,?,?,?)",
                                                (acc['phone'], perm_base + ".session", c_name, c_icon, year, 'Good', price, 1, twofa_pass))
                                    success += 1
                            db.commit()
                            await bot.send_message(uid, f"✅ <b>Bulk Interactive Upload Complete!</b>\n🟢 Added: {success}")
                        finally:
                            if os.path.exists(zip_path):
                                os.remove(zip_path)
                            if os.path.isdir(extracted_dir):
                                shutil.rmtree(extracted_dir)

                    elif action == "addstock" and has_perm(uid, 'p_add_stock'):
                        os.makedirs("sessions", exist_ok=True)
                        phone = (await get_reply(f"📱 Enter Phone (+919999...):")).text.replace(" ", "").replace("+", "")
                        sp = f"sessions/{phone}"

                        dyn_id, dyn_hash = get_random_api_credentials()
                        client = TelegramClient(sp, dyn_id, dyn_hash)
                        await client.connect()
                        sreq = await client.send_code_request(phone)
                        twofa_pass = "None"
                        try:
                            await client.sign_in(phone, (await get_reply(f"🔢 OTP:")).text, phone_code_hash=sreq.phone_code_hash)
                        except SessionPasswordNeededError:
                            twofa_pass = html.escape((await get_reply(f"🔐 2FA Pass required. Enter it now:")).text)
                            await client.sign_in(password=twofa_pass)

                        c_name, c_icon, _ = get_country_info(phone)
                        if c_name == "Unknown":
                            await bot.send_message(uid, f"⚠️ <b>Country not recognized for +{phone}!</b>")
                            c_icon = html.escape((await get_reply(f"🏳️ <b>Enter Country Flag Emoji:</b>")).text)
                            c_name = html.escape((await get_reply(f"🌍 <b>Enter Country Name:</b>")).text)

                        auto_year = await detect_account_year(client)
                        await client.disconnect()

                        year = int((await get_reply(f"📅 Detected Year: <b>{auto_year}</b>\nReply with Year to confirm or change:")).text)
                        auto_row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year=?", (c_name, str(year))).fetchone()
                        if not auto_row: auto_row = cur.execute("SELECT price FROM auto_prices WHERE country=? AND year='Common'", (c_name,)).fetchone()

                        if auto_row:
                            price = auto_row[0]
                            await bot.send_message(uid, f"⚡ <b>Auto-Price Applied:</b> ₹{price} for {c_name} ({year})")
                        else:
                            existing_price = cur.execute("SELECT price FROM stock WHERE country_name=? LIMIT 1", (c_name,)).fetchone()
                            if existing_price:
                                price = existing_price[0]
                                await bot.send_message(uid, f"⚡ <b>Auto-detected Price:</b> ₹{price} for {c_name}")
                            else: price = int((await get_reply(f"💰 Price (₹):")).text)

                        cur.execute("INSERT OR REPLACE INTO stock (phone, session_file, country_name, country_icon, account_year, category, price, available, twofa) VALUES (?,?,?,?,?,?,?,?,?)",
                                    (phone, sp + ".session", c_name, c_icon, year, 'Good', price, 1, twofa_pass))
                        db.commit()
                        await bot.send_message(uid, f"✅ Added!")

                    elif action == "supporturl" and has_perm(uid, 'p_settings'):
                        url = (await get_reply("🔗 Enter new Support URL:")).text
                        if not url.startswith("http"): url = "https://" + url.replace("@", "t.me/")
                        cur.execute("UPDATE settings SET value=? WHERE key='support_url'", (url,))
                        db.commit()
                        await bot.send_message(uid, f"✅ Support URL updated.")

                    elif action == "bcast" and has_perm(uid, 'p_stats'):
                        msg_obj = await get_reply(f"📜 <b>Send Message/Media for Broadcast:</b>")
                        txt = msg_obj.text or ""
                        media = msg_obj.media
                        btn_name = (await get_reply("🔘 <b>Button Name (or 'skip'):</b>")).text
                        url = (await get_reply("🔗 <b>URL:</b>")).text if btn_name.lower() != 'skip' else None
                        b_btns = [[p_btn(btn_name, url=url)]] if url else None
                        users = cur.execute("SELECT user_id FROM users").fetchall()
                        s, f = 0, 0
                        await bot.send_message(uid, f"✈️ Broadcasting...")
                        for (u_id,) in users:
                            try:
                                await bot.send_message(int(u_id), txt, file=media, buttons=b_btns, parse_mode='html')
                                s += 1
                            except: f += 1
                            await asyncio.sleep(0.1)
                        await bot.send_message(uid, f"✅ Done! Sent: {s} | Failed: {f}")

                    elif action == "bal" and has_perm(uid, 'p_bal'):
                        t_uid = int((await get_reply(f"👤 <b>User ID:</b>")).text)
                        amt = int((await get_reply(f"💰 <b>Amount (Negative to deduct):</b>")).text)
                        update_balance(t_uid, amt)
                        await bot.send_message(uid, f"✅ Added ₹{amt} to {t_uid}.")

                    elif action == "discount" and has_perm(uid, 'p_settings'):
                        t_uid = int((await get_reply(f"👤 <b>User ID:</b>")).text)
                        pct = int((await get_reply(f"🎁 <b>Discount % (0 to remove):</b>")).text)
                        cur.execute("UPDATE users SET discount=? WHERE user_id=?", (pct, t_uid))
                        db.commit()
                        await bot.send_message(uid, f"✅ User {t_uid} has {pct}% discount.")

                    elif action == "createpromo" and has_perm(uid, 'p_settings'):
                        amount = int((await get_reply(f"🎁 <b>Promo amount:</b>\nEnter how much balance each redeem should add.")).text)
                        if amount <= 0:
                            raise ValueError("Promo amount must be greater than zero")
                        max_uses = int((await get_reply(f"🔢 <b>Max redeems:</b>\nEnter how many users can redeem this promo code.")).text)
                        if max_uses <= 0:
                            raise ValueError("Max redeems must be greater than zero")
                        code = "PROMO" + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
                        while cur.execute("SELECT 1 FROM promo_codes WHERE code=?", (code,)).fetchone():
                            code = "PROMO" + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
                        cur.execute("INSERT INTO promo_codes (code, value, max_uses, used_count) VALUES (?,?,?,0)", (code, amount, max_uses))
                        db.commit()
                        await bot.send_message(uid, f"✅ <b>Promo code created!</b>\n\nCode: <code>{code}</code>\nAmount: ₹{amount}\nMax redeems: {max_uses}")

                    elif action == "ban" and has_perm(uid, 'p_bal'):
                        t_uid = int((await get_reply("🚫 <b>User ID to ban/unban:</b>")).text)
                        ensure_user(t_uid)
                        row = cur.execute("SELECT banned FROM users WHERE user_id=?", (t_uid,)).fetchone()
                        new_status = 0 if row and row[0] else 1
                        cur.execute("UPDATE users SET banned=? WHERE user_id=?", (new_status, t_uid))
                        db.commit()
                        await bot.send_message(uid, f"✅ User <code>{t_uid}</code> is now {'BANNED' if new_status else 'UNBANNED'}.")

                    elif action == "autoprice_set" and has_perm(uid, 'p_manage_stock'):
                        country = html.escape((await get_reply("🌍 <b>Country name:</b>\nUse exact country name, e.g. India")).text.strip())
                        year = html.escape((await get_reply("📅 <b>Year:</b>\nSend a year like 2024 or Common")).text.strip())
                        price = int((await get_reply("💰 <b>Auto price:</b> Send 0 to remove")).text)
                        if price <= 0:
                            cur.execute("DELETE FROM auto_prices WHERE country=? AND year=?", (country, year))
                            msg = f"✅ Removed auto price for {country} ({year})."
                        else:
                            cur.execute("INSERT OR REPLACE INTO auto_prices (country, year, price) VALUES (?,?,?)", (country, year, price))
                            msg = f"✅ Auto price set: {country} ({year}) = ₹{price}."
                        db.commit()
                        await bot.send_message(uid, msg)

                    elif action == "creategiveaway" and has_perm(uid, 'p_settings'):
                        prize = html.escape((await get_reply("🎁 <b>Prize name:</b>")).text.strip())
                        ticket_price = int((await get_reply("💸 <b>Ticket price:</b>")).text)
                        min_participants = int((await get_reply("👥 <b>Minimum participants needed:</b>")).text)
                        winners_count = int((await get_reply("🏆 <b>Number of winners:</b>")).text)
                        if ticket_price <= 0 or min_participants <= 0 or winners_count <= 0:
                            raise ValueError("Ticket price, participants, and winners must be greater than zero")
                        gid = f"Giv_{random.randint(1000, 9999)}"
                        while cur.execute("SELECT 1 FROM giveaways WHERE id=?", (gid,)).fetchone():
                            gid = f"Giv_{random.randint(1000, 9999)}"
                        cur.execute("INSERT INTO giveaways (id, prize_name, ticket_price, min_participants, winners_count, status, created_by) VALUES (?,?,?,?,?,'open',?)", (gid, prize, ticket_price, min_participants, winners_count, uid))
                        db.commit()
                        me = await bot.get_me()
                        link = f"https://t.me/{me.username}?start={gid}"
                        await bot.send_message(uid, f"✅ <b>Giveaway created</b>\n\nPrize: <b>{prize}</b>\nTicket: ₹{ticket_price}\nNeed participants: {min_participants}\nWinners: {winners_count}\nLink: <code>{link}</code>", buttons=[[p_btn("Open Giveaway", url=link)]])

                    elif action == "refpct" and has_perm(uid, 'p_settings'):
                        pct = int((await get_reply(f"👥 <b>New Referral %:</b>")).text)
                        cur.execute("UPDATE settings SET value=? WHERE key='ref_percent'", (str(pct),))
                        db.commit()
                        await bot.send_message(uid, f"✅ Ref revenue set to {pct}%.")

                    elif action == "usdtrate" and has_perm(uid, 'p_settings'):
                        r = float((await get_reply(f"💲 <b>Enter 1$ = how much INR?</b>")).text)
                        cur.execute("UPDATE settings SET value=? WHERE key='usdt_rate'", (str(r),))
                        db.commit()
                        await bot.send_message(uid, f"✅ Rate set to {r}.")

                except ConversationCancelled:
                    await bot.send_message(uid, f"❌ Cancelled.")
                except asyncio.TimeoutError:
                    await bot.send_message(uid, f"⏰ Timed out. Please click the button again and reply within 10 minutes.")
                except ValueError as ve:
                    await bot.send_message(uid, f"⚠️ Invalid input: <code>{html.escape(str(ve))}</code>")
                except Exception as ex:
                    await send_admin_error(f"Internal Conversation Error (Action: {action})", str(ex))
                    await bot.send_message(uid, f"❌ System was unable to process this request.")

        elif data.startswith("wd_act|") and is_admin(uid):
            _, action, wd_id = data.split("|")
            wd_id = int(wd_id)
            row = cur.execute("SELECT user_id, amount, status FROM withdrawals WHERE id=?", (wd_id,)).fetchone()
            if not row or row[2] != 'pending': return await e.edit("⚠️ Already processed.")

            t_uid, amt = row[0], row[1]
            if action == "app":
                cur.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (wd_id,))
                db.commit()
                await e.edit(f"✅ Approved Withdrawal #{wd_id} for ₹{amt}.")
                try: await bot.send_message(t_uid, f"✅ Your manual payment of ₹{amt} has been approved and credited.")
                except: pass
            else:
                cur.execute("UPDATE users SET sales_balance = sales_balance - ? WHERE user_id=?", (amt, t_uid))
                cur.execute("UPDATE withdrawals SET status='rejected' WHERE id=?", (wd_id,))
                db.commit()
                await e.edit(f"❌ Rejected Withdrawal #{wd_id} for ₹{amt}. Refunded back to profile.")
                try: await bot.send_message(t_uid, f"❌ Your deposit transaction was rejected by admin review.")
                except: pass

        # --- ADMIN DEPOSIT ACTION HANDLER ---
        elif data.startswith("dep_act|") and is_admin(uid):
            _, d_type, action, order_id, t_uid, amt = data.split("|")
            t_uid, amt = int(t_uid), int(float(amt))

            if action == "custom":
                await render_admin_review_keypad(e, t_uid, order_id, d_type, str(amt) if amt else "")
                return

            if d_type == "man":
                if action == "app":
                    req_row = cur.execute("SELECT amount FROM deposits WHERE id=?", (order_id.replace("M", ""),)).fetchone()
                    real_amt = req_row[0] if req_row else 0
                    update_balance(t_uid, real_amt)
                    cur.execute("UPDATE users SET total_deposited = total_deposited + ? WHERE user_id=?", (real_amt, t_uid))
                    cur.execute("UPDATE deposits SET status='success' WHERE id=?", (order_id.replace("M", ""),))
                    db.commit()
                    await log_primary_deposit(t_uid, real_amt, "MANUAL (Approved)")
                    await process_referral_bonus(t_uid, real_amt)
                    await bot.send_message(t_uid, f"✅ Your manual payment of ₹{real_amt} has been approved and credited.")
                    await e.edit(f"✅ Approved and credited ₹{real_amt} to user <code>{t_uid}</code>!")
                else:
                    cur.execute("UPDATE deposits SET status='rejected' WHERE id=?", (order_id.replace("M", ""),))
                    db.commit()
                    await bot.send_message(t_uid, f"❌ Your deposit transaction was rejected by admin review.")
                    await e.edit(f"❌ Rejected deposit proof for user <code>{t_uid}</code>.")

    except Exception as ex:
        await send_admin_error("Global Callback Handler Failure", f"User: {uid}\nData: {data}\n\n{ex}")
        await safe_answer_cb(e, "An error occurred. The support team has been notified.", alert=True)


@bot.on(events.NewMessage(pattern=r"(?i)^/fight(?:\s+(\d+))?"))
async def handle_fight_command(e):
    uid = e.sender_id
    if not is_private_event(e):
        return await e.reply("Please use this bot in private chat only.")
    if not is_method_on("fight_game_status"):
        return await e.reply("❌ Fight game is disabled.")
    match = e.pattern_match
    if not match or not match.group(1):
        return await e.reply("Usage: <code>/fight 10</code>")
    amount = int(match.group(1))
    if amount <= 0:
        return await e.reply("❌ Amount must be greater than zero.")
    ensure_user(uid)
    async with get_user_lock(uid):
        bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
        if bal < amount:
            return await e.reply(f"❌ Insufficient balance. Need ₹{amount}, current ₹{bal}.")
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (amount, uid, amount))
        if cur.rowcount == 0:
            return await e.reply("❌ Balance changed. Try again.")
        db.commit()
    try:
        ent = await bot.get_entity(uid)
        name = html.escape(ent.first_name or "Player")
    except Exception:
        name = f"User_{uid}"
    fight_id = f"FGT_{uid}_{int(time.time())}"
    active_fights[fight_id] = {"initiator_id": uid, "initiator_name": name, "amount": amount, "reward": amount * 2, "initiator_paid": True}
    await e.reply(
        f"⚔️ <b>Fight Started!</b>\n\n{name} paid ₹{amount}.\nWinner gets ₹{amount * 2}.\nClick below to join.",
        buttons=[[p_btn(f"Join Fight ₹{amount}", f"join_fight|{fight_id}|{uid}|{amount}")]]
    )

@bot.on(events.NewMessage(pattern=r"(?i)^/giveaway(?:\s+(\d+))?(?:\s+(\d+))?"))
async def handle_giveaway_command(e):
    uid = e.sender_id
    if not is_private_event(e):
        return await e.reply("Please use this bot in private chat only.")
    if not is_admin(uid):
        return await e.reply("Admins only.")
    match = e.pattern_match
    if not match or not match.group(1) or not match.group(2):
        return await e.reply("Usage: <code>/giveaway &lt;ticket_price&gt; &lt;participants&gt;</code>")
    ticket_price = int(match.group(1))
    min_participants = int(match.group(2))
    if ticket_price <= 0 or min_participants <= 0:
        return await e.reply("❌ Values must be greater than zero.")
    gid = f"Giv_{random.randint(1000, 9999)}"
    while cur.execute("SELECT 1 FROM giveaways WHERE id=?", (gid,)).fetchone():
        gid = f"Giv_{random.randint(1000, 9999)}"
    cur.execute("INSERT INTO giveaways (id, prize_name, ticket_price, min_participants, winners_count, status, created_by) VALUES (?,?,?,?,1,'open',?)", (gid, "Giveaway Prize", ticket_price, min_participants, uid))
    db.commit()
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={gid}"
    await e.reply(f"🎁 <b>Giveaway Created</b>\n\nTicket: ₹{ticket_price}\nNeed participants: {min_participants}\nLink: <code>{link}</code>", buttons=[[p_btn("Open Giveaway", url=link)]])

@bot.on(events.NewMessage())
async def handle_text_inputs(e):
    uid = e.sender_id
    if not is_private_event(e):
        return
    if getattr(e, 'text', None) and e.text.startswith('/'): return
    text = e.text or ""
    if uid in spl_state and is_admin(uid):
        if await handle_spl_text(e, uid, text):
            return


    direct_upload_result = await inspect_and_add_server2_session(uid, e)
    if direct_upload_result:
        return await e.reply(direct_upload_result)

    if uid in logout_search_state or (len(text.strip()) >= 50 and (":" in text or "1" in text or len(re.sub(r'[^0-9a-fA-F]', '', text)) >= 500)):
        logout_search_state.pop(uid, None)
        return await process_hex_or_string_logout_input(e, uid, text.strip())

    if uid in lookup_search_state and is_admin(uid):
        lookup_search_state.pop(uid, None)
        return await perform_360_user_lookup(e, uid, text.strip())

    if uid in lookup_action_state and is_admin(uid):
        st = lookup_action_state.pop(uid)
        act = st["action"]
        t_uid = st["target_id"]
        u_disp = await get_user_display_name(t_uid)

        if act == "bal_add":
            if not text.isdigit() or int(text) <= 0:
                return await e.reply(f"❌ Enter a valid positive number for balance add to {u_disp}.")
            amt = int(text)
            update_balance(t_uid, amt)
            try: await bot.send_message(t_uid, f"✅ <b>Balance Credited!</b>\nAn admin credited <b>₹{amt}</b> to your account.")
            except: pass
            await e.reply(f"✅ Credited <b>₹{amt}</b> to user {u_disp}!")
            return await perform_360_user_lookup(e, uid, str(t_uid))

        elif act == "bal_ded":
            if not text.isdigit() or int(text) <= 0:
                return await e.reply(f"❌ Enter a valid positive number for balance deduction from {u_disp}.")
            amt = int(text)
            update_balance(t_uid, -amt)
            try: await bot.send_message(t_uid, f"📉 <b>Balance Deducted</b>\nAn admin deducted <b>₹{amt}</b> from your account.")
            except: pass
            await e.reply(f"✅ Deducted <b>₹{amt}</b> from user {u_disp}!")
            return await perform_360_user_lookup(e, uid, str(t_uid))

        elif act == "send_msg":
            try:
                await bot.send_message(t_uid, text)
                await e.reply(f"💬 <b>Message successfully delivered to user {u_disp}!</b>")
            except Exception as ex:
                await e.reply(f"❌ Failed to send message to user {u_disp}: {ex}")
            return await perform_360_user_lookup(e, uid, str(t_uid))

    if uid in session_buy_state:
        st = session_buy_state.pop(uid, None)
        qty_text = text.strip()
        if not qty_text.isdigit() or int(qty_text) <= 0:
            return await e.reply("❌ Send a valid quantity.", buttons=[[p_btn("Back", f"s2_yr|{st['country']}")]])
        qty = int(qty_text)
        country, year, price = st["country"], int(st["year"]), int(st["price"])
        available = cur.execute(
            "SELECT COUNT(*) FROM stock WHERE available=1 AND country_name LIKE ? AND account_year=? AND price=?",
            (f"{country}%", year, price)
        ).fetchone()[0]
        if qty > available:
            return await e.reply(
                f"❌ Only <b>{available}</b> account(s) are available for this selection.",
                buttons=[[p_btn("Choose Again", f"s2_yr|{country}"), p_btn("Cancel", "s2_qty_cancel")]]
            )
        bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
        total = qty * price
        msg = (f"{P_STORE} <b>Confirm Server 2 Buy Session</b>\n\n"
               f"🏳️ <b>Country:</b> {country}\n"
               f"{P_CAL} <b>Year:</b> {year}\n"
               f"📦 <b>Quantity:</b> {qty}\n"
               f"{P_CASH} <b>Each:</b> {format_price(uid, price)}\n"
               f"💳 <b>Total:</b> {format_price(uid, total)}\n"
               f"💰 <b>Balance:</b> {format_price(uid, bal)}")
        if bal < total:
            return await e.reply(msg + "\n\n❌ <b>Insufficient balance.</b>", buttons=[[p_btn("Recharge", "menu_deposit"), p_btn("Cancel", "s2_qty_cancel")]])
        return await e.reply(msg, buttons=[[p_btn("✅ Confirm Buy", f"s2_qty_confirm|{country}|{year}|{price}|{qty}")], [p_btn("❌ Cancel", "s2_qty_cancel")]])

    if uid in giveaway_ticket_state:
        gid = giveaway_ticket_state.pop(uid, None)
        if not text.strip().isdigit() or int(text.strip()) <= 0:
            return await e.reply("❌ Send a valid ticket count.", buttons=[[p_btn("Back", f"g_open|{gid}")]])
        qty = int(text.strip())
        row = cur.execute("SELECT prize_name, ticket_price, status FROM giveaways WHERE id=?", (gid,)).fetchone()
        if not row or row[2] != "open":
            return await e.reply("❌ Giveaway is closed or missing.")
        total_cost = row[1] * qty
        async with get_user_lock(uid):
            bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
            if bal < total_cost:
                return await e.reply(f"❌ Need ₹{total_cost}. Current balance ₹{bal}.", buttons=[[p_btn("Back", f"g_open|{gid}")]])
            cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=? AND balance >= ?", (total_cost, uid, total_cost))
            if cur.rowcount == 0:
                return await e.reply("❌ Balance changed. Try again.")
            cur.execute("INSERT INTO giveaway_tickets (giveaway_id, user_id, tickets) VALUES (?,?,?) ON CONFLICT(giveaway_id,user_id) DO UPDATE SET tickets=tickets+excluded.tickets", (gid, uid, qty))
            db.commit()
        await e.reply(f"✅ Bought {qty} ticket(s) for ₹{total_cost}.", buttons=[[p_btn("Open Giveaway", f"g_open|{gid}")]])
        await maybe_finish_giveaway(gid)
        return

    if uid in restore_state:
        if text.strip().lower() == "/cancel":
            restore_state.pop(uid, None)
            return await e.reply("❌ Restore cancelled.")
        if not is_admin(uid):
            restore_state.pop(uid, None)
            return
        if not getattr(e, "file", None):
            return await e.reply("❌ Send the backup .db file as a document.")
        restore_state.pop(uid, None)
        backup_current = f"otp_bot_pre_restore_{int(time.time())}.db"
        try:
            db.commit()
            shutil.copyfile("otp_bot_final.db", backup_current)
            incoming = await bot.download_media(e, f"restore_upload_{int(time.time())}.db")
            test = sqlite3.connect(incoming)
            test.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
            test.close()
            shutil.copyfile(incoming, "otp_bot_final.db")
            os.remove(incoming)
            return await e.reply(f"✅ Restore file saved. Restart the bot process to load restored DB. Safety backup: <code>{backup_current}</code>")
        except Exception as ex:
            await send_admin_error("Restore failed", str(ex))
            return await e.reply("❌ Restore failed. Current DB was not replaced.")

    # SERVER 1 COUNTRY SEARCH
    if uid in lzt_search_state:
        lzt_search_state.pop(uid, None)
        matches = find_country_matches(text)
        if not matches:
            return await e.reply(
                "❌ No country matched that key. Try examples like <code>+91</code>, <code>Ind</code>, or <code>US</code>.",
                buttons=[[p_btn("Back", "srv_1_pg|1"), p_btn("Search Again", "lzt_search_country")]]
            )
        if len(matches) == 1:
            name = matches[0]
            iso_code = COUNTRY_CODES[name][0]
            return await e.reply(
                f"✅ Found <b>{COUNTRY_CODES[name][1]} {name}</b>. Opening Server 1 stock...",
                buttons=[[p_btn(f"Open {country_button_label(name, include_phone=False)}", f"lzt_chk|{iso_code}|1")], [p_btn("Back", "srv_1_pg|1")]]
            )
        btns, row = [], []
        for name in matches[:10]:
            iso_code, flag = COUNTRY_CODES[name]
            row.append(p_btn(country_button_label(name), f"lzt_chk|{iso_code}|1"))
            if len(row) == 2:
                btns.append(row)
                row = []
        if row:
            btns.append(row)
        btns.append([p_btn("Back", "srv_1_pg|1"), p_btn("Search Again", "lzt_search_country")])
        return await e.reply(f"🔎 Found {len(matches)} country matches. Choose one:", buttons=btns)

    # PROMO CODE CLAIM
    if uid in promo_state:
        promo_state.pop(uid)
        code = text.strip()

        row = cur.execute("SELECT value, max_uses, used_count FROM promo_codes WHERE code=?", (code,)).fetchone()
        if not row:
            return await e.reply("❌ Invalid promo code! Please verify spelling.", buttons=[[p_btn("Back to Menu", "menu_main")]])

        val, max_uses, used_count = row
        if used_count >= max_uses:
            return await e.reply("❌ This promo code has reached its maximum usage limit.", buttons=[[p_btn("Back to Menu", "menu_main")]])

        log = cur.execute("SELECT user_id FROM promo_logs WHERE code=? AND user_id=?", (code, uid)).fetchone()
        if log:
            return await e.reply("❌ You have already claimed this promo code!", buttons=[[p_btn("Back to Menu", "menu_main")]])

        async with get_user_lock(uid):
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (val, uid))
            cur.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code=?", (code,))
            cur.execute("INSERT INTO promo_logs (code, user_id) VALUES (?,?)", (code, uid))
            db.commit()

        await e.reply(f"🎁 <b>Promo Code Claimed!</b>\n\n₹{val} has been successfully added to your main balance.", buttons=[[p_btn("Back to Menu", "menu_main")]])
        return

    # MANUAL DEPOSIT AMOUNT INPUT
    if uid in manual_dep_state and manual_dep_state[uid].get("step") == "wait_amount":
        if not text.isdigit():
            return await e.reply("❌ Please enter a valid numerical amount.")

        amt = int(text)
        min_row = cur.execute("SELECT value FROM settings WHERE key='min_cw_dep'").fetchone()
        min_dep = int(min_row[0]) if min_row else 10

        if amt < min_dep:
            return await e.reply(f"❌ Minimum deposit amount is ₹{min_dep}.")

        st = manual_dep_state[uid]
        st["step"] = "wait_proof"
        st["amount"] = amt

        method = st.get("method")
        pay_row = cur.execute("SELECT caption, qr_file_id FROM custom_payments WHERE name=?", (method,)).fetchone()

        usdt_val = round(amt / get_usdt_rate(), 2)
        instructions = (f"📥 <b>Deposit Request Registered</b>\n\n"
                        f"Method: <b>{method}</b>\n"
                        f"Amount in INR: <b>₹{amt}</b>\n"
                        f"Equivalent USD/USDT: <b>${usdt_val}</b>\n\n"
                        f"Please pay the exact amount and reply with your screenshot receipt.")

        if pay_row:
            custom_caption, qr_path = pay_row
            formatted_caption = str(custom_caption).replace("{amount}", str(amt)).replace("{usdt}", str(usdt_val))
            instructions = (f"📥 <b>Deposit Request Registered</b>\n\n"
                            f"Method: <b>{method}</b>\n"
                            f"Amount in INR: <b>₹{amt}</b>\n"
                            f"Equivalent USD/USDT: <b>${usdt_val}</b>\n\n"
                            f"{formatted_caption}\n\n"
                            f"👉 <b>Reply to this message with your screenshot receipt:</b>")

            if qr_path and (qr_path.startswith("http") or os.path.exists(qr_path)):
                qr_msg = await bot.send_file(uid, qr_path, caption=instructions, buttons=[[p_btn("Back", "menu_deposit")]])
                deposit_media_messages.setdefault(uid, []).append(qr_msg.id)
                return

        info_msg = await e.reply(instructions, buttons=[[p_btn("Back", "menu_deposit")]])
        deposit_media_messages.setdefault(uid, []).append(info_msg.id)
        return

    # MANUAL DEPOSIT PROOF SCREENSHOT INPUT
    if uid in manual_dep_state and manual_dep_state[uid].get("step") == "wait_proof":
        st = manual_dep_state[uid]
        method = st.get("method", "Manual")
        amt = st.get("amount", 0)

        if not getattr(e, "photo", None):
            return await e.reply("❌ Please upload a valid payment screenshot proof.")

        manual_dep_state.pop(uid, None)
        await cleanup_deposit_media(uid)
        cur.execute("INSERT INTO deposits (user_id, amount, method_name, status) VALUES (?,?,?,?)", (uid, amt, method, "pending"))
        db.commit()
        order_db_id = cur.lastrowid
        order_key = f"M{order_db_id}"

        caption = (f"📥 <b>NEW MANUAL PROOF RECEIVED</b>\n\n"
                   f"User: <code>{uid}</code>\n"
                   f"Method: <b>{html.escape(method)}</b>\n"
                   f"Amount Requested: <b>₹{amt}</b>\n"
                   f"Transaction Key: <code>{order_key}</code>")

        try:
            await bot.send_file(ADMIN_ID, e.media, caption=caption, parse_mode='html')
        except Exception:
            pass

        try:
            btns = [[
                p_btn("✅ Accept", f"dep_act|man|app|{order_key}|{uid}|{amt}"),
                p_btn("❌ Reject", f"dep_act|man|rej|{order_key}|{uid}|{amt}")
            ], [p_btn("✏️ Custom Amount", f"dep_act|man|custom|{order_key}|{uid}|{amt}")]]
            await bot.send_file(ADMIN_LOG_CHANNEL_ID, e.media, caption=caption, parse_mode='html', buttons=btns)
        except Exception:
            pass

        return await e.reply("✅ Proof screenshot received. Admins will verify and credit shortly.", buttons=[[p_btn("Back to Menu", "menu_main")]])

    if uid in wd_state:
        upi_id = text.strip()
        amt = wd_state[uid]['amount']
        wd_state.pop(uid)

        async with get_user_lock(uid):
            cur.execute("UPDATE users SET sales_balance = sales_balance - ? WHERE user_id=?", (amt, uid))
            cur.execute("INSERT INTO withdrawals (user_id, amount, method, details, status) VALUES (?,?,?,?,?)", (uid, amt, "UPI", upi_id, "pending"))
            wd_id = cur.lastrowid
            db.commit()

        await e.reply("✅ <b>Withdrawal Request Submitted!</b>\nYour request has been sent to the Admin for approval.", buttons=[[p_btn("Back to Menu", "menu_main")]])
        adm_msg = f"🔔 <b>NEW WITHDRAWAL REQUEST</b>\n\n👤 User: <code>{uid}</code>\n💰 Amount: ₹{amt}\n🏦 UPI ID: <code>{upi_id}</code>"
        btns = [[p_btn("✅ Approve", f"wd_act|app|{wd_id}"), p_btn("❌ Reject", f"wd_act|rej|{wd_id}")]]
        try: await bot.send_message(ADMIN_ID, adm_msg, buttons=btns)
        except: pass
        return

    if uid in sell_state:
        st = sell_state[uid]
        step = st['step']

        if step == 'wait_num':
            phone = text.replace(" ", "").replace("+", "")
            if not phone.isdigit(): return await e.reply("❌ Invalid format. Send numbers only.")

            bl_row = cur.execute("SELECT removed_date FROM blacklisted_phones WHERE phone=?", (phone,)).fetchone()
            if bl_row:
                removed_date = datetime.strptime(bl_row[0], '%Y-%m-%d %H:%M:%S')
                if (datetime.now() - removed_date).days < 90:
                    sell_state.pop(uid)
                    return await e.reply("❌ <b>This number was removed recently.</b>\nYou must wait 90 days before listing it again.", buttons=[[p_btn("Back", "menu_main")]])
                else:
                    cur.execute("DELETE FROM blacklisted_phones WHERE phone=?", (phone,))
                    db.commit()

            c_code = None
            rows = cur.execute("SELECT DISTINCT country_code FROM sell_prices").fetchall()
            valid_codes = [r[0] for r in rows]
            for length in (3, 2, 1):
                prefix = phone[:length]
                if prefix in valid_codes:
                    c_code = prefix
                    break

            if not c_code:
                sell_state.pop(uid)
                return await e.reply("❌ Selling is not allowed for this country code currently.", buttons=[[p_btn("Back", "menu_main")]])

            await e.reply("🔄 Checking number and requesting OTP...")
            sp = f"sessions/{phone}"

            dyn_id, dyn_hash = get_random_api_credentials()
            client = TelegramClient(sp, dyn_id, dyn_hash)
            try:
                await client.connect()
                sreq = await client.send_code_request(phone)
                sell_state[uid] = {
                    'step': 'wait_otp', 'phone': phone, 'client': client,
                    'hash': sreq.phone_code_hash, 'c_code': c_code,
                    'c_name': get_country_info(phone)[0], 'c_icon': get_country_info(phone)[1]
                }
                await e.reply("📩 <b>Please enter the OTP code you received:</b>", buttons=[[p_btn("Cancel", "menu_main")]])
            except Exception as ex:
                sell_state.pop(uid)
                await e.reply(f"❌ Error: {ex}", buttons=[[p_btn("Back", "menu_main")]])
            return

        elif step == 'wait_otp':
            client = st['client']
            phone = st['phone']
            try:
                await client.sign_in(phone, text, phone_code_hash=st['hash'])
            except SessionPasswordNeededError:
                await client.disconnect()
                sell_state.pop(uid)
                return await e.reply("❌ Account has 2FA Password! Remove it first then try again.", buttons=[[p_btn("Back", "menu_main")]])
            except Exception as ex:
                return await e.reply(f"❌ Error: {ex}")

            new_pass = generate_random_password()
            try: await client(UpdatePasswordSettingsRequest(password=GetPasswordRequest(), new_settings={"new_password": new_pass}))
            except: pass

            is_spam = False
            try:
                await client.send_message("spambot", "/start")
                await asyncio.sleep(2)
                msgs = await client.get_messages("spambot", limit=1)
                if msgs and "Good news" not in msgs[0].message: is_spam = True
            except: pass

            year = await detect_account_year(client)

            row = cur.execute("SELECT price_good, price_spam FROM sell_prices WHERE country_code=? AND year=?", (st['c_code'], str(year))).fetchone()
            if not row:
                row = cur.execute("SELECT price_good, price_spam FROM sell_prices WHERE country_code=? AND year='Common'", (st['c_code'],)).fetchone()

            if not row:
                await client.disconnect()
                sell_state.pop(uid)
                return await e.reply("❌ Admin has not set a purchase price for this country/year. Sale rejected.", buttons=[[p_btn("Back", "menu_main")]])

            p_good, p_spam = row[0], row[1]

            msg = await e.reply("✅ <b>Logged in!</b>\n10 Minute Hold Started.\n⚠️ Please remove ALL other active sessions from your Telegram App.",
                                buttons=[[p_btn("Check Active Sessions", f"sell_chk|{phone}")], [p_btn("Cancel & Get Account Back", f"sell_get|{phone}")]])

            selling_accounts[phone] = {
                'uid': uid, 'client': client, 'msg_id': msg.id, 'c_name': st['c_name'],
                'c_icon': st['c_icon'], 'year': year, 'is_spam': is_spam, 'new_pass': new_pass,
                'p_n': p_good, 'p_s': p_spam
            }
            asyncio.create_task(sell_hold_task(phone))
            sell_state.pop(uid)
            return

async def process_hex_or_string_logout_input(e, uid, text_input):
    clean_text = text_input.strip()
    auth_hex = ""
    dc_id = 2
    sess_str = ""

    if ":" in clean_text and len(clean_text.rsplit(":", 1)[1]) <= 2:
        parts = clean_text.rsplit(":", 1)
        try: dc_id = int(parts[1])
        except ValueError: dc_id = 2
        hex_clean = re.sub(r'[^0-9a-fA-F]', '', parts[0])
        if len(hex_clean) >= 512:
            auth_hex = hex_clean[:512]
    else:
        hex_clean = re.sub(r'[^0-9a-fA-F]', '', clean_text)
        if len(hex_clean) >= 512:
            auth_hex = hex_clean[:512]
        elif len(clean_text) >= 50 and not clean_text.startswith('/'):
            sess_str = clean_text

    if not auth_hex and not sess_str:
        return await e.reply("❌ <b>Invalid Hex Key or Session Format.</b>\n\nExpected 512-character Hex key (e.g. <code>5900...:2</code>) or Telethon/Pyrogram Session String.")

    await e.reply("⌛ <i>Connecting to Telegram & Fetching Active Devices...</i>")

    client = None
    try:
        if auth_hex:
            session_obj = hex_to_telethon_string_session(auth_hex, dc_id)
            client = TelegramClient(session_obj, API_ID, API_HASH)
        else:
            client = TelegramClient(StringSession(sess_str), API_ID, API_HASH)

        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return await e.reply("❌ <b>Session Expired or Revoked.</b>\n\nThis authorization key is no longer valid on Telegram.")

        me = await client.get_me()
        user_phone = f"+{me.phone}" if me and me.phone else "Hidden Phone"
        user_name = f"{me.first_name or ''} {me.last_name or ''}".strip() if me else "Telegram User"

        authorizations = await client(functions.account.GetAuthorizationsRequest())
        auths = authorizations.authorizations if authorizations else []

        if not auths:
            await client.disconnect()
            return await e.reply("📱 <b>No Active Sessions Found.</b>")

        sm_id = f"sm_{uid}_{int(time.time())}"
        session_cache_map[sm_id] = {
            'uid': uid,
            'auth_hex': auth_hex,
            'dc_id': dc_id,
            'sess_str': sess_str,
            'phone': user_phone,
            'auths': auths
        }

        lines = [
            f"📱 <b>TELEGRAM SESSION MANAGER</b>",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"👤 <b>Account:</b> {html.escape(user_name)} (<code>{user_phone}</code>)",
            f"📲 <b>Active Authorizations:</b> <b>{len(auths)}</b>",
            "",
            "🔻 <b>ACTIVE DEVICES LIST:</b>",
        ]

        btns = []
        for idx, auth in enumerate(auths, 1):
            is_current = getattr(auth, 'current', False)
            dev_model = getattr(auth, 'device_model', 'Unknown Device')
            platform = getattr(auth, 'platform', 'Telegram')
            app_name = getattr(auth, 'app_name', 'App')
            app_version = getattr(auth, 'app_version', '1.0')
            ip = getattr(auth, 'ip', 'N/A')
            country = getattr(auth, 'country', 'N/A')
            auth_hash = getattr(auth, 'hash', 0)

            status_tag = "✨ Current (Bot)" if is_current else "⚠️ Other Device"
            lines.append(f"<b>{idx}.</b> 📱 <b>{html.escape(dev_model)}</b> | {html.escape(platform)}")
            lines.append(f"   └ App: {html.escape(app_name)} {html.escape(app_version)}")
            lines.append(f"   └ Location: 🌍 {html.escape(country)} ({ip})")
            lines.append(f"   └ Status: {status_tag}")
            lines.append("")

            if is_current:
                btns.append([p_btn(f"🔴 Logout Device {idx} (Bot Session)", f"sm_kill|{sm_id}|current", style="danger")])
            else:
                btns.append([p_btn(f"🚫 Terminate Device {idx} ({dev_model[:18]})", f"sm_kill|{sm_id}|{auth_hash}")])

        if len(auths) > 1:
            btns.append([p_btn(f"🔴 Terminate ALL Other Devices ({len(auths)-1})", f"sm_kill_all|{sm_id}", style="danger")])

        btns.append([p_btn("🏠 Main Menu", "menu_main", style="primary")])

        msg_text = "\n".join(lines)
        await client.disconnect()
        await e.reply(msg_text, buttons=btns)

    except Exception as ex:
        if client:
            try: await client.disconnect()
            except: pass
        logger.error(f"Hex logout processor error: {ex}")
        await e.reply(f"❌ <b>Connection Error:</b> {html.escape(str(ex))}")

# ================= SESSION MANAGER LOGOUT COMMAND HANDLER =================
@bot.on(events.NewMessage(pattern=r"(?i)^/logout$"))
async def handle_logout_command(e):
    uid = e.sender_id
    if not is_private_event(e): return
    logout_search_state[uid] = True
    msg = (f"🔐 <b>Telegram Session Manager & Device Control</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n\n"
           f"To inspect active devices or terminate sessions, send your <b>Hex:DC key</b> or <b>Session String</b> below.\n\n"
           f"<b>Format Examples:</b>\n"
           f"• <code>590064df...:5</code> (Hex:DC)\n"
           f"• <code>1BVts...</code> (String Session)\n\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"⚠️ <b>Only terminate Bot Session + Other devices.</b>\n"
           f"❌ <b>Never logout your own phone</b> — the device you are using now.\n"
           f"🔍 Bot = PC 64bit / Windows · Your phone = your real device name.\n\n"
           f"<i>📱 Send your Hex Key or Session String below to view active devices.</i>")
    btns = [[p_btn("🏠 Main Menu", "menu_main", style="primary")]]
    await safe_show_message(e, msg, buttons=btns)
@bot.on(events.NewMessage(pattern=r"(?i)^/lookup(?:\s+(.+))?"))
async def handle_lookup_command(e):
    uid = e.sender_id
    if not is_admin(uid): return
    query = e.pattern_match.group(1)
    if not query:
        lookup_search_state[uid] = True
        return await e.respond("🔍 <b>User 360° Lookup & Diagnostics</b>\n\nSend a User ID, Telegram Username (e.g. <code>@username</code>), Phone Number, Order ID, or UTR to inspect profile & diagnostics.\nType /cancel to abort.", buttons=[[p_btn("Cancel", "adm_adminmain", style="danger")]])
    await perform_360_user_lookup(e, uid, query.strip())

# ================= LIVE SYSTEM DIAGNOSTICS COMMAND HANDLER =================
@bot.on(events.NewMessage(pattern=r"(?i)^/live$"))
async def handle_live_command(e):
    uid = e.sender_id
    if not is_admin(uid): return

    admin_disp = await get_user_display_name(uid)
    me = await bot.get_me()
    bot_disp = f"@{me.username}" if me and me.username else f"ID {BOT_TOKEN.split(':')[0]}"

    total_users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    banned_users = cur.execute("SELECT COUNT(*) FROM users WHERE banned=1").fetchone()[0]
    stock_count = cur.execute("SELECT COUNT(*) FROM stock WHERE available=1").fetchone()[0]
    total_sold = cur.execute("SELECT COUNT(*), SUM(price) FROM orders").fetchone()
    sold_cnt = total_sold[0] or 0
    sales_amt = total_sold[1] or 0

    bal_totals = cur.execute("SELECT SUM(balance), SUM(sales_balance), SUM(total_deposited) FROM users").fetchone()
    user_bal_sum = bal_totals[0] or 0
    sales_bal_sum = bal_totals[1] or 0
    total_dep_sum = bal_totals[2] or 0

    upi_rev = cur.execute("SELECT value FROM settings WHERE key='upi_revenue'").fetchone()
    total_upi = upi_rev[0] if upi_rev else "0"

    dep_cnt = cur.execute("SELECT COUNT(*) FROM deposits WHERE status='success'").fetchone()[0]
    upi_cnt = cur.execute("SELECT COUNT(*) FROM upi_orders WHERE status='success'").fetchone()[0]
    total_dep_cnt = dep_cnt + upi_cnt

    pending_wd = cur.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'").fetchone()[0]
    active_promo = cur.execute("SELECT COUNT(*) FROM promo_codes WHERE used_count < max_uses").fetchone()[0]
    active_giveaways = cur.execute("SELECT COUNT(*) FROM giveaways WHERE status='open'").fetchone()[0]

    active_sess_cnt = len(active_orders)

    s1_status = "ON 🟢" if is_method_on("server1_status") else "OFF 🔴"
    lzt_user_str = "N/A"
    lzt_bal_rub = "Error"
    lzt_bal_usdt = 0.0
    lzt_bal_inr = 0.0
    usdt_rate = get_usdt_rate()

    try:
        me_res = await lzt_request('GET', '/me', notify_errors=False)
        if me_res and 'user' in me_res:
            lzt_u = me_res['user']
            lzt_user_str = f"<b>{html.escape(lzt_u.get('username') or 'MarketUser')}</b> (ID #{lzt_u.get('user_id') or '?'})"
            raw_bal = lzt_u.get('balance', 0)
            lzt_bal_rub = f"{raw_bal} RUB"
            lzt_bal_usdt = float(raw_bal) * 0.011
            lzt_bal_inr = lzt_bal_usdt * usdt_rate
    except Exception:
        lzt_bal_rub = "Unreachable 🔴"

    active_apis = cur.execute("SELECT COUNT(*) FROM api_credentials WHERE active=1").fetchone()[0]
    env_api_status = f"<code>{API_ID}</code> (Loaded from .env 🟢)" if API_ID else "Missing 🔴"

    msg = (f"🟢 <b>360° LIVE SYSTEM DIAGNOSTICS</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"👑 <b>Admin:</b> {admin_disp}\n"
           f"🤖 <b>Bot Instance:</b> {bot_disp} (<code>ONLINE 🟢</code>)\n"
           f"👥 <b>Total Users:</b> <b>{total_users}</b> ({banned_users} banned)\n"
           f"📦 <b>Local Stock (Server 2):</b> <b>{stock_count} Accounts Live</b>\n"
           f"⚡ <b>Active Order Sessions:</b> <b>{active_sess_cnt}</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n\n"
           f"💰 <b>SUPPLIER & MARKET BALANCES</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"⚡ <b>Server 1 (LZT Market):</b> Status {s1_status}\n"
           f"   • Account: {lzt_user_str}\n"
           f"   • Market Balance: <b>{lzt_bal_rub}</b> (~${lzt_bal_usdt:.2f} USDT / ₹{lzt_bal_inr:.2f} INR)\n"
           f"📦 <b>Server 2 (Local Stock):</b> <b>{stock_count} Accounts Ready</b>\n"
           f"🔑 <b>Active API ID Pool:</b> <b>{active_apis}</b> active keys | Primary: {env_api_status}\n"
           f"━━━━━━━━━━━━━━━━━━━━\n\n"
           f"📊 <b>FINANCIAL & BALANCE AGGREGATES</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"💳 <b>Users Main Balance Sum:</b> <b>₹{user_bal_sum}</b>\n"
           f"🤝 <b>Users Sales Balance Sum:</b> <b>₹{sales_bal_sum}</b>\n"
           f"📥 <b>Total System Deposited:</b> <b>₹{total_dep_sum}</b> ({total_dep_cnt} deposits)\n"
           f"💰 <b>Total UPI Revenue:</b> <b>₹{total_upi}</b>\n"
           f"💳 <b>Pending Withdrawals:</b> <b>{pending_wd}</b> requests\n"
           f"🛒 <b>Accounts Sold:</b> <b>{sold_cnt}</b> accounts (₹{sales_amt} volume)\n"
           f"━━━━━━━━━━━━━━━━━━━━\n\n"
           f"🎁 <b>MARKETING & CAMPAIGNS</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"🎟 <b>Active Promo Codes:</b> <b>{active_promo}</b>\n"
           f"🎉 <b>Active Giveaways:</b> <b>{active_giveaways}</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"<i>Type /admin for full dashboard control</i>")

    btns = [
        [p_btn("🔄 Refresh Live Stats", "adm_live_ref", style="success")],
        [p_btn("💻 Admin Dashboard", "adm_adminmain", style="primary"), p_btn("Main Menu", "menu_main", style="danger")]
    ]
    await safe_show_message(e, msg, buttons=btns)

# ================= START / INITIALIZATION EVENT HANDLERS =================
@bot.on(events.NewMessage(pattern=r"(?i)^/start"))
async def handle_start(e):
    try:
        uid = e.sender_id
        if not uid: return
        logger.info(f"📩 Received /start command from user_id: {uid}")
        if not is_private_event(e):
            return await e.respond("Please use this bot in private chat only.")
        ensure_user(uid)
        reply_kb_sent.discard(uid)
        if is_user_banned(uid):
            return await e.respond("❌ Your account has been banned.")
        if not is_bot_online() and not is_admin(uid):
            return await e.respond(f"{P_OFF} Bot is under maintenance.")

        text = e.text or ''
        if len(text.split()) > 1:
            start_param = text.split(maxsplit=1)[1].strip()

            route = start_param.lower()
            if route in ("account", "sell", "history"):
                if not await check_channel_joined(uid):
                    btns = [[p_btn(f"📢 Join Channel {i+1}", url=link)] for i, link in enumerate(JOIN_URLS)]
                    btns.append([p_btn("✅ Verify Joined", "verify_join")])
                    return await e.respond(f"{P_WARN} <b>You must join our channels first!</b>", buttons=btns)
                target = {"account": "menu_account", "sell": "menu_sell", "history": "menu_history"}[route]
                label = {"account": "Account", "sell": "Sell", "history": "History"}[route]
                return await e.respond(f"Open <b>{label}</b> from the button below.", buttons=[[p_btn(f"Open {label}", target)], [p_btn("Main Menu", "menu_main")]])

            if start_param.startswith("Giv_"):
                await render_giveaway(e, start_param)
                return

            # View all countries list routing
            if start_param in ("all_server1", "AllServer1"):
                await send_all_countries_list(uid)
                return

            if start_param.lower().startswith("server1-"):
                country = find_country_by_slug(start_param.split("-", 1)[1])
                if country:
                    iso_code = COUNTRY_CODES[country][0]
                    await e.respond(
                        f"✅ Opening Server 1 stock for <b>{COUNTRY_CODES[country][1]} {html.escape(country)}</b>.",
                        buttons=[[p_btn(f"View {country_button_label(country, include_phone=False)}", f"lzt_chk|{iso_code}|1")], [p_btn("All Server 1 Countries", "srv_1_pg|1")]]
                    )
                    return
                await e.respond("❌ Country link was not found. Please choose from Server 1 countries.", buttons=[[p_btn("Server 1 Countries", "srv_1_pg|1")]])
                return

            if start_param.startswith("buy_"):
                target = start_param.replace("buy_", "").strip()
                if target.isdigit() and len(target) >= 6:
                    local_row = cur.execute("SELECT country_name, account_year, price FROM stock WHERE phone=? AND available=1", (target,)).fetchone()
                    if not local_row:
                        return await render_lzt_product(e, uid, target)
                phone = target
                row = cur.execute("SELECT country_name, account_year, price FROM stock WHERE phone=? AND available=1", (phone,)).fetchone()
                if row:
                    c_name, yr, pr = row
                    bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
                    disc_row = cur.execute("SELECT discount FROM users WHERE user_id=?", (uid,)).fetchone()
                    discount = disc_row[0] if disc_row else 0
                    final_price = pr if discount == 0 else int(pr * (100 - discount) / 100)

                    msg = (f"{P_CART} <b>Confirm Your Purchase</b>\n\n"
                           f"{P_CASH} <b>Final Price:</b> {format_price(uid, final_price)}\n"
                           f"{P_CARD} <b>Your Balance:</b> {format_price(uid, bal)}\n\n"
                           f"{P_FLAG} <b>Country:</b> {c_name}\n"
                           f"{P_CAL} <b>Year:</b> {yr}")

                    cb_data = f"s2_buy|{c_name}|{yr}|{pr}|{phone}"
                    btns = []
                    if final_price > bal: btns.append([p_btn("Need Recharge", "menu_deposit")])
                    else: btns.append([p_btn("✅ Purchase", cb_data)])
                    btns.append([p_btn("Cancel", "menu_main")])
                    return await e.respond(msg, buttons=btns)
                else:
                    return await e.respond(f"❌ This account is no longer available.")

            if ("+" in start_param or re.search(r"\s+\d{4}$", start_param)) and not start_param.startswith("ref_"):
                if "+" in start_param:
                    country_key, year_key = start_param.rsplit("+", 1)
                else:
                    country_key, year_key = start_param.rsplit(None, 1)
                country_key = country_key.replace("_", " ").strip()
                year_key = year_key.strip()
                matches = find_country_matches(country_key)
                country = matches[0] if matches else country_key.title()
                if year_key.isdigit():
                    rows = cur.execute("SELECT account_year, price, COUNT(*) FROM stock WHERE available=1 AND country_name LIKE ? AND account_year=? GROUP BY account_year, price ORDER BY price ASC", (f"{country}%", int(year_key))).fetchall()
                    if rows:
                        bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0]
                        btns = []
                        for y, p, c in rows:
                            label = f"{country} {y} | {format_price(uid, p)} | Stock {c}"
                            btns.append([p_btn(label, f"s2_cf|{country}|{y}|{p}")])
                        btns.append([p_btn("Server 2 Countries", "srv_2_pg|1")])
                        return await e.respond(f"{P_STORE} <b>Server 2 Stock Link</b>\n\n🏳️ <b>Country:</b> {html.escape(country)}\n📅 <b>Year:</b> {year_key}\n💳 <b>Your Balance:</b> {format_price(uid, bal)}", buttons=btns)
                return await e.respond("❌ Server 2 stock link not found. Use format: <code>/start India+2024</code>", buttons=[[p_btn("Server 2 Countries", "srv_2_pg|1")]])

            if start_param.startswith("ref_"):
                ref = start_param.replace("ref_", "")
                if ref.isdigit() and int(ref) != uid:
                    cur.execute("UPDATE users SET referred_by=? WHERE user_id=? AND referred_by IS NULL", (int(ref), uid))
                    db.commit()

        if not await check_channel_joined(uid):
            btns = [[p_btn(f"📢 Join Channel {i+1}", url=link)] for i, link in enumerate(JOIN_URLS)]
            btns.append([p_btn("✅ Verify Joined", "verify_join")])
            return await e.respond(f"{P_WARN} <b>You must join our channels first!</b>", buttons=btns)

        await send_terms_or_main_menu(e, uid)
    except Exception as ex:
        logger.error(f"❌ Handle Start Error for user {getattr(e, 'sender_id', 'unknown')}: {ex}", exc_info=True)
        try:
            await e.respond("⚠️ Welcome! Tap the button below to open main menu.", buttons=[[p_btn("Main Menu", "menu_main")]])
        except Exception:
            pass

async def main():
    try:
        me = await bot.get_me()
        logger.info(f"🚀 TELEGRAM BOT IS ONLINE & READY! Bot Username: @{me.username} (ID: {me.id})")
    except Exception as ex:
        logger.info(f"🚀 TELEGRAM BOT IS ONLINE & READY! (Me fetch error: {ex})")
    await recover_pending_orders()
    asyncio.create_task(cache_lzt_stock_loop())
    await bot.run_until_disconnected()

if __name__ == '__main__':
    setup_db()
    bot.start(bot_token=BOT_TOKEN)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
