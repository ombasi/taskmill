"""
IP-based language detection + simple translations.
Missing keys fall back to English.
"""
from __future__ import annotations

from flask import request, session, g

# Country code (ISO) -> preferred language code
COUNTRY_LANG = {
    # Priority regions you specified
    "DE": "de",  # Germany -> German
    "AT": "de",
    "CH": "de",  # default German; FR/IT regions still often use de UI
    "RW": "rw",  # Rwanda -> Kinyarwanda
    "UG": "en",  # Uganda -> English (Luganda available as lg)
    "KE": "sw",  # Kenya -> Kiswahili
    "TZ": "sw",  # Tanzania
    "CD": "sw",  # Congo (DRC) - Swahili widely used in east
    "CG": "fr",  # Congo-Brazzaville often French
    "BI": "sw",
    # Europe
    "FR": "fr", "BE": "fr", "LU": "fr",
    "NL": "nl",
    "ES": "es", "MX": "es", "AR": "es", "CO": "es", "CL": "es", "PE": "es",
    "PT": "pt", "BR": "pt", "AO": "pt", "MZ": "pt",
    "IT": "it",
    "PL": "pl",
    "RU": "ru",
    "TR": "tr",
    "SE": "sv", "NO": "nb", "DK": "da", "FI": "fi",
    "GR": "el",
    "RO": "ro",
    "CZ": "cs",
    "HU": "hu",
    "UA": "uk",
    # Middle East / Asia / Africa
    "SA": "ar", "AE": "ar", "EG": "ar", "MA": "ar", "DZ": "ar", "IQ": "ar",
    "CN": "zh", "TW": "zh", "HK": "zh",
    "JP": "ja",
    "KR": "ko",
    "IN": "hi",
    "PK": "ur",
    "ID": "id",
    "MY": "ms",
    "TH": "th",
    "VN": "vi",
    "PH": "en",
    "NG": "en", "GH": "en", "ZA": "en", "ZM": "en", "ZW": "en",
    "US": "en", "GB": "en", "CA": "en", "AU": "en", "IE": "en", "NZ": "en",
    "SS": "en",
    "ET": "en",
    "SN": "fr", "CI": "fr", "CM": "fr", "ML": "fr", "BF": "fr",
}

LANG_NAMES = {
    "en": "English",
    "de": "Deutsch",
    "sw": "Kiswahili",
    "lg": "Luganda",
    "rw": "Kinyarwanda",
    "fr": "Français",
    "es": "Español",
    "pt": "Português",
    "ar": "العربية",
    "zh": "中文",
    "hi": "हिन्दी",
    "nl": "Nederlands",
    "it": "Italiano",
    "tr": "Türkçe",
    "ru": "Русский",
    "pl": "Polski",
    "ja": "日本語",
    "ko": "한국어",
    "id": "Bahasa Indonesia",
    "vi": "Tiếng Việt",
    "th": "ไทย",
    "uk": "Українська",
    "sv": "Svenska",
    "ur": "اردو",
}

# Core UI strings — add keys as needed; unknown keys return English
# Keep keys short and stable
TRANSLATIONS = {
    "en": {
        "app_name": "Taskmill",
        "nav_dashboard": "Dashboard",
        "nav_tasks": "Tasks",
        "nav_wallet": "Wallet",
        "nav_history": "History",
        "nav_membership": "Membership",
        "nav_profile": "Profile",
        "nav_support": "Support",
        "nav_chat": "Chat",
        "nav_logout": "Logout",
        "nav_login": "Sign in",
        "nav_register": "Register",
        "welcome_back": "Welcome back",
        "sign_in": "Sign in",
        "sign_in_subtitle": "Sign in to your Taskmill account",
        "username_or_email": "Username or email",
        "password": "Password",
        "remember_me": "Remember me",
        "forgot_password": "Forgot password?",
        "no_account": "No account?",
        "create_one": "Create one",
        "create_account": "Create account",
        "full_name": "Full name",
        "username": "Username",
        "email": "Email",
        "phone": "Phone",
        "country": "Country",
        "referral_code": "Referral code",
        "referral_required": "A valid referral code is required to create an account.",
        "confirm_password": "Confirm password",
        "accept_terms": "I agree to the Terms & Conditions",
        "submit": "Submit",
        "cancel": "Cancel",
        "deposit": "Deposit",
        "withdraw": "Withdraw",
        "balance": "Balance",
        "available_balance": "Available balance",
        "pending": "Pending",
        "completed": "Done",
        "tasks": "Tasks",
        "combo": "Combo",
        "combo_hold": "Escrow hold",
        "deposit_to_continue": "Deposit to continue",
        "product_review": "Product review",
        "submit_review": "Submit review",
        "commission": "Commission",
        "price": "Price",
        "support": "Support",
        "about": "About",
        "faq": "FAQs",
        "terms": "Terms & Conditions",
        "language": "Language",
        "auto_language": "Auto (from location)",
        "save": "Save",
        "loading": "Loading…",
        "success": "Success",
        "error": "Error",
        "warning": "Warning",
        "onboard_welcome": "Quick start",
        "faq_title": "Frequently asked questions",
        "about_title": "About Taskmill",
        "terms_title": "Terms & Conditions",
        "contact_title": "Contact us",
        "status_title": "System status",
        "membership_title": "Choose your tier",
        "hold_timeline": "Hold timeline",
        "stuck_users": "Stuck users",
    },
    "de": {
        "app_name": "Taskmill",
        "nav_dashboard": "Übersicht",
        "nav_tasks": "Aufgaben",
        "nav_wallet": "Geldbörse",
        "nav_history": "Verlauf",
        "nav_membership": "Mitgliedschaft",
        "nav_profile": "Profil",
        "nav_support": "Support",
        "nav_chat": "Chat",
        "nav_logout": "Abmelden",
        "nav_login": "Anmelden",
        "nav_register": "Registrieren",
        "welcome_back": "Willkommen zurück",
        "sign_in": "Anmelden",
        "sign_in_subtitle": "Melden Sie sich bei Ihrem Taskmill-Konto an",
        "username_or_email": "Benutzername oder E-Mail",
        "password": "Passwort",
        "remember_me": "Angemeldet bleiben",
        "forgot_password": "Passwort vergessen?",
        "no_account": "Kein Konto?",
        "create_one": "Jetzt erstellen",
        "create_account": "Konto erstellen",
        "full_name": "Vollständiger Name",
        "username": "Benutzername",
        "email": "E-Mail",
        "phone": "Telefon",
        "country": "Land",
        "referral_code": "Empfehlungscode",
        "referral_required": "Ein gültiger Empfehlungscode ist erforderlich.",
        "confirm_password": "Passwort bestätigen",
        "accept_terms": "Ich akzeptiere die Nutzungsbedingungen",
        "submit": "Absenden",
        "cancel": "Abbrechen",
        "deposit": "Einzahlen",
        "withdraw": "Auszahlen",
        "balance": "Saldo",
        "available_balance": "Verfügbares Guthaben",
        "pending": "Ausstehend",
        "completed": "Erledigt",
        "tasks": "Aufgaben",
        "combo": "Combo",
        "combo_hold": "Sperrbetrag",
        "deposit_to_continue": "Einzahlen um fortzufahren",
        "product_review": "Produktbewertung",
        "submit_review": "Bewertung absenden",
        "commission": "Provision",
        "price": "Preis",
        "support": "Support",
        "about": "Über uns",
        "faq": "FAQ",
        "terms": "Nutzungsbedingungen",
        "language": "Sprache",
        "auto_language": "Auto (nach Standort)",
        "save": "Speichern",
        "loading": "Lädt…",
        "success": "Erfolg",
        "error": "Fehler",
        "warning": "Warnung",
        "faq_title": "Häufig gestellte Fragen",
        "about_title": "Über Taskmill",
        "terms_title": "Nutzungsbedingungen",
        "contact_title": "Kontakt",
        "status_title": "Systemstatus",
        "membership_title": "Wähle deinen Tarif",
    },
    "sw": {
        "app_name": "Taskmill",
        "nav_dashboard": "Dashibodi",
        "nav_tasks": "Kazi",
        "nav_wallet": "Pochi",
        "nav_history": "Historia",
        "nav_membership": "Uanachama",
        "nav_profile": "Wasifu",
        "nav_support": "Msaada",
        "nav_chat": "Gumzo",
        "nav_logout": "Toka",
        "nav_login": "Ingia",
        "nav_register": "Jisajili",
        "welcome_back": "Karibu tena",
        "sign_in": "Ingia",
        "sign_in_subtitle": "Ingia kwenye akaunti yako ya Taskmill",
        "username_or_email": "Jina la mtumiaji au barua pepe",
        "password": "Nenosiri",
        "remember_me": "Nikumbuke",
        "forgot_password": "Umesahau nenosiri?",
        "no_account": "Huna akaunti?",
        "create_one": "Fungua sasa",
        "create_account": "Fungua akaunti",
        "full_name": "Jina kamili",
        "username": "Jina la mtumiaji",
        "email": "Barua pepe",
        "phone": "Simu",
        "country": "Nchi",
        "referral_code": "Msimbo wa rufaa",
        "referral_required": "Msimbo halali wa rufaa unahitajika.",
        "confirm_password": "Thibitisha nenosiri",
        "accept_terms": "Ninakubali Sheria na Masharti",
        "submit": "Wasilisha",
        "cancel": "Ghairi",
        "deposit": "Weka pesa",
        "withdraw": "Toa pesa",
        "balance": "Salio",
        "available_balance": "Salio linalopatikana",
        "pending": "Inasubiri",
        "completed": "Imekamilika",
        "tasks": "Kazi",
        "combo": "Combo",
        "combo_hold": "Kizuizi cha salio",
        "deposit_to_continue": "Weka pesa ili uendelee",
        "product_review": "Ukaguzi wa bidhaa",
        "submit_review": "Wasilisha ukaguzi",
        "commission": "Kamisheni",
        "price": "Bei",
        "support": "Msaada",
        "about": "Kuhusu",
        "faq": "Maswali",
        "terms": "Sheria na Masharti",
        "language": "Lugha",
        "auto_language": "Otomatiki (kutoka eneo)",
        "save": "Hifadhi",
        "loading": "Inapakia…",
        "success": "Imefanikiwa",
        "error": "Hitilafu",
        "warning": "Onyo",
        "faq_title": "Maswali yanayoulizwa mara kwa mara",
        "about_title": "Kuhusu Taskmill",
        "terms_title": "Sheria na Masharti",
        "contact_title": "Wasiliana nasi",
        "status_title": "Hali ya mfumo",
        "membership_title": "Chagua kiwango chako",
    },
    "lg": {
        "app_name": "Taskmill",
        "nav_dashboard": "Dashiboodi",
        "nav_tasks": "Emirimu",
        "nav_wallet": "Ensawo",
        "nav_history": "Ebyafaayo",
        "nav_membership": "Obw'ennanyini",
        "nav_profile": "Ebikukwatako",
        "nav_support": "Obuyambi",
        "nav_chat": "Yogera",
        "nav_logout": "Fuluma",
        "nav_login": "Yingira",
        "nav_register": "Wewandiise",
        "welcome_back": "Tusanyukidde n'okudda",
        "sign_in": "Yingira",
        "sign_in_subtitle": "Yingira ku akawunti yo ku Taskmill",
        "username_or_email": "Erinnya ly'omukozesa oba email",
        "password": "Akasumuluzo",
        "remember_me": "Nzijukiranga",
        "forgot_password": "Werabidde akasumuluzo?",
        "no_account": "Tolina akawunti?",
        "create_one": "Kola emu",
        "create_account": "Kola akawunti",
        "full_name": "Amanya gonna",
        "username": "Erinnya ly'omukozesa",
        "email": "Email",
        "phone": "Ssimu",
        "country": "Ensi",
        "referral_code": "Koodi y'okuyita",
        "referral_required": "Koodi y'okuyita ey'amazima yeetaagisa.",
        "confirm_password": "Kakasa akasumuluzo",
        "accept_terms": "Nzikiriza amateeka n'enkola",
        "submit": "Weereza",
        "cancel": "Sazaamu",
        "deposit": "Teeka ssente",
        "withdraw": "Ggyawo ssente",
        "balance": "Obusigire",
        "available_balance": "Ssente eziriwo",
        "pending": "Zirindirira",
        "completed": "Zikoleddwa",
        "tasks": "Emirimu",
        "combo": "Combo",
        "combo_hold": "Okukwata ssente",
        "deposit_to_continue": "Teeka ssente okusobola okugenda mu maaso",
        "product_review": "Okukebera ekintu",
        "submit_review": "Weereza okukebera",
        "commission": "Commission",
        "price": "Omuwendo",
        "support": "Obuyambi",
        "about": "Ebikwata kuffe",
        "faq": "Ebibuuzo",
        "terms": "Amateeka n'enkola",
        "language": "Olulimi",
        "auto_language": "Awatali kweroboza (okuva mu kifo)",
        "save": "Tereka",
        "loading": "Kikola…",
        "success": "Kiwedde bulungi",
        "error": "Kiremya",
        "warning": "Okulabula",
    },
    "rw": {
        "app_name": "Taskmill",
        "nav_dashboard": "Imbonerahamwe",
        "nav_tasks": "Imirimo",
        "nav_wallet": "Igipapuro cy'amafaranga",
        "nav_history": "Amateka",
        "nav_membership": "Ubunyamuryango",
        "nav_profile": "Umwirondoro",
        "nav_support": "Ubufasha",
        "nav_chat": "Ikiganiro",
        "nav_logout": "Sohoka",
        "nav_login": "Injira",
        "nav_register": "Iyandikishe",
        "welcome_back": "Murakaza neza nanone",
        "sign_in": "Injira",
        "sign_in_subtitle": "Injira muri konti yawe ya Taskmill",
        "username_or_email": "Izina cyangwa imeri",
        "password": "Ijambo ry'ibanga",
        "remember_me": "Unyibuke",
        "forgot_password": "Wibagiwe ijambo ry'ibanga?",
        "no_account": "Nta konti ufite?",
        "create_one": "Fungura",
        "create_account": "Fungura konti",
        "full_name": "Amazina yose",
        "username": "Izina ry'ukoresha",
        "email": "Imeri",
        "phone": "Telefone",
        "country": "Igihugu",
        "referral_code": "Kode yo kwiyamamaza",
        "referral_required": "Kode yemewe yo kwiyamamaza irakenewe.",
        "confirm_password": "Emeza ijambo ry'ibanga",
        "accept_terms": "Nemera amabwiriza n'amasezerano",
        "submit": "Ohereza",
        "cancel": "Hagarika",
        "deposit": "Shyiramo amafaranga",
        "withdraw": "Kuramo amafaranga",
        "balance": "Asigaye",
        "available_balance": "Amafaranga ahari",
        "pending": "Bitegereje",
        "completed": "Byarangiye",
        "tasks": "Imirimo",
        "combo": "Combo",
        "combo_hold": "Gufata amafaranga",
        "deposit_to_continue": "Shyiramo amafaranga kugira ngo ukomeze",
        "product_review": "Isuzuma ry'igicuruzwa",
        "submit_review": "Ohereza isuzuma",
        "commission": "Komisiyo",
        "price": "Igiciro",
        "support": "Ubufasha",
        "about": "Ibyerekeye",
        "faq": "Ibibazo",
        "terms": "Amabwiriza",
        "language": "Ururimi",
        "auto_language": "Automatic (ahantu)",
        "save": "Bika",
        "loading": "Biratunganywa…",
        "success": "Byagenze neza",
        "error": "Ikosa",
        "warning": "Iburira",
    },
    "fr": {
        "app_name": "Taskmill",
        "nav_dashboard": "Tableau de bord",
        "nav_tasks": "Tâches",
        "nav_wallet": "Portefeuille",
        "nav_history": "Historique",
        "nav_membership": "Abonnement",
        "nav_profile": "Profil",
        "nav_support": "Assistance",
        "nav_chat": "Discussion",
        "nav_logout": "Déconnexion",
        "nav_login": "Connexion",
        "nav_register": "S'inscrire",
        "welcome_back": "Bon retour",
        "sign_in": "Se connecter",
        "sign_in_subtitle": "Connectez-vous à votre compte Taskmill",
        "username_or_email": "Nom d'utilisateur ou e-mail",
        "password": "Mot de passe",
        "remember_me": "Se souvenir de moi",
        "forgot_password": "Mot de passe oublié ?",
        "no_account": "Pas de compte ?",
        "create_one": "Créer un compte",
        "create_account": "Créer un compte",
        "full_name": "Nom complet",
        "username": "Nom d'utilisateur",
        "email": "E-mail",
        "phone": "Téléphone",
        "country": "Pays",
        "referral_code": "Code de parrainage",
        "referral_required": "Un code de parrainage valide est requis.",
        "confirm_password": "Confirmer le mot de passe",
        "accept_terms": "J'accepte les conditions générales",
        "submit": "Envoyer",
        "cancel": "Annuler",
        "deposit": "Dépôt",
        "withdraw": "Retrait",
        "balance": "Solde",
        "available_balance": "Solde disponible",
        "pending": "En attente",
        "completed": "Terminé",
        "tasks": "Tâches",
        "combo": "Combo",
        "combo_hold": "Retenue",
        "deposit_to_continue": "Déposer pour continuer",
        "product_review": "Avis produit",
        "submit_review": "Envoyer l'avis",
        "commission": "Commission",
        "price": "Prix",
        "support": "Assistance",
        "about": "À propos",
        "faq": "FAQ",
        "terms": "Conditions",
        "language": "Langue",
        "auto_language": "Auto (selon la localisation)",
        "save": "Enregistrer",
        "loading": "Chargement…",
        "success": "Succès",
        "error": "Erreur",
        "warning": "Avertissement",
    },
    "es": {
        "nav_dashboard": "Panel", "nav_tasks": "Tareas", "nav_wallet": "Billetera",
        "nav_history": "Historial", "nav_membership": "Membresía", "nav_profile": "Perfil",
        "nav_support": "Soporte", "nav_logout": "Salir", "nav_login": "Iniciar sesión",
        "welcome_back": "Bienvenido de nuevo", "sign_in": "Iniciar sesión",
        "password": "Contraseña", "deposit": "Depósito", "withdraw": "Retirar",
        "balance": "Saldo", "submit": "Enviar", "cancel": "Cancelar",
        "language": "Idioma", "support": "Soporte", "about": "Acerca de", "faq": "Preguntas",
    },
    "pt": {
        "nav_dashboard": "Painel", "nav_tasks": "Tarefas", "nav_wallet": "Carteira",
        "nav_history": "Histórico", "nav_membership": "Associação", "nav_profile": "Perfil",
        "nav_support": "Suporte", "nav_logout": "Sair", "nav_login": "Entrar",
        "welcome_back": "Bem-vindo de volta", "sign_in": "Entrar",
        "password": "Senha", "deposit": "Depósito", "withdraw": "Sacar",
        "balance": "Saldo", "submit": "Enviar", "cancel": "Cancelar",
        "language": "Idioma", "support": "Suporte", "about": "Sobre", "faq": "Perguntas",
    },
    "ar": {
        "nav_dashboard": "لوحة التحكم", "nav_tasks": "المهام", "nav_wallet": "المحفظة",
        "nav_history": "السجل", "nav_membership": "العضوية", "nav_profile": "الملف",
        "nav_support": "الدعم", "nav_logout": "خروج", "nav_login": "تسجيل الدخول",
        "welcome_back": "مرحبًا بعودتك", "sign_in": "تسجيل الدخول",
        "password": "كلمة المرور", "deposit": "إيداع", "withdraw": "سحب",
        "balance": "الرصيد", "submit": "إرسال", "cancel": "إلغاء",
        "language": "اللغة", "support": "الدعم", "about": "حول", "faq": "الأسئلة",
    },
    "zh": {
        "nav_dashboard": "仪表盘", "nav_tasks": "任务", "nav_wallet": "钱包",
        "nav_history": "历史", "nav_membership": "会员", "nav_profile": "个人资料",
        "nav_support": "支持", "nav_logout": "退出", "nav_login": "登录",
        "welcome_back": "欢迎回来", "sign_in": "登录",
        "password": "密码", "deposit": "充值", "withdraw": "提现",
        "balance": "余额", "submit": "提交", "cancel": "取消",
        "language": "语言", "support": "支持", "about": "关于", "faq": "常见问题",
    },
    "nl": {
        "nav_dashboard": "Dashboard", "nav_tasks": "Taken", "nav_wallet": "Portemonnee",
        "nav_history": "Geschiedenis", "nav_membership": "Lidmaatschap", "nav_profile": "Profiel",
        "nav_support": "Support", "nav_logout": "Uitloggen", "nav_login": "Inloggen",
        "welcome_back": "Welkom terug", "sign_in": "Inloggen",
        "password": "Wachtwoord", "deposit": "Storten", "withdraw": "Opnemen",
        "balance": "Saldo", "submit": "Verzenden", "cancel": "Annuleren",
        "language": "Taal", "support": "Support", "about": "Over", "faq": "FAQ",
    },
    "hi": {
        "nav_dashboard": "डैशबोर्ड", "nav_tasks": "कार्य", "nav_wallet": "वॉलेट",
        "nav_history": "इतिहास", "nav_membership": "सदस्यता", "nav_profile": "प्रोफ़ाइल",
        "nav_support": "सहायता", "nav_logout": "लॉग आउट", "nav_login": "साइन इन",
        "welcome_back": "वापसी पर स्वागत है", "sign_in": "साइन इन",
        "password": "पासवर्ड", "deposit": "जमा", "withdraw": "निकासी",
        "balance": "शेष", "submit": "जमा करें", "cancel": "रद्द करें",
        "language": "भाषा", "support": "सहायता", "about": "परिचय", "faq": "प्रश्न",
    },
}


def lang_from_country_code(code: str | None) -> str:
    if not code:
        return "en"
    return COUNTRY_LANG.get(code.upper(), "en")


def detect_lang_from_ip(ip: str | None) -> str:
    if not ip:
        return "en"
    try:
        from utils.location import detect_location
        loc = detect_location(ip)
        if not loc:
            return "en"
        return lang_from_country_code(loc.get("countryCode"))
    except Exception:
        return "en"


def resolve_language() -> str:
    """Session override > cookie > IP geo > English."""
    forced = session.get("lang")
    if forced and forced in LANG_NAMES:
        return forced
    cookie = request.cookies.get("tm_lang")
    if cookie and cookie in LANG_NAMES:
        return cookie
    try:
        from utils.location import get_client_ip
        return detect_lang_from_ip(get_client_ip(request))
    except Exception:
        return "en"


def translate(key: str, lang: str | None = None) -> str:
    try:
        lang = lang or getattr(g, "lang", None) or "en"
        table = TRANSLATIONS.get(lang) or {}
        if key in table:
            return table[key]
        return TRANSLATIONS.get("en", {}).get(key, key)
    except Exception:
        return key


def t(key: str, **_kwargs) -> str:
    return translate(key)


def available_languages():
    # Prefer fully translated packs first
    order = ["en", "de", "sw", "lg", "rw", "fr", "es", "pt", "ar", "zh", "nl", "hi", "it", "tr", "ru", "pl", "ja", "ko", "id", "vi", "th", "uk", "sv", "ur"]
    out = []
    for code in order:
        if code in LANG_NAMES:
            out.append({"code": code, "name": LANG_NAMES[code]})
    for code, name in LANG_NAMES.items():
        if code not in {x["code"] for x in out}:
            out.append({"code": code, "name": name})
    return out


def init_i18n(app):
    @app.before_request
    def _set_lang():
        g.lang = resolve_language()

    @app.context_processor
    def _inject_i18n():
        lang = getattr(g, "lang", None) or resolve_language()
        return {
            "t": translate,
            "lang": lang,
            "languages": available_languages(),
            "lang_name": LANG_NAMES.get(lang, lang),
        }

    @app.route("/set-language/<code>")
    def set_language(code):
        from flask import redirect, request as req
        code = (code or "en").lower()
        if code == "auto":
            session.pop("lang", None)
            resp = redirect(req.referrer or "/")
            resp.delete_cookie("tm_lang")
            return resp
        if code not in LANG_NAMES:
            code = "en"
        session["lang"] = code
        resp = redirect(req.referrer or "/")
        resp.set_cookie("tm_lang", code, max_age=60 * 60 * 24 * 365)
        return resp
