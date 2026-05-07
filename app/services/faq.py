"""Deterministic FAQ matcher.

Answers to the common questions documented in the Host Training Manual.
Returns a polished response in the caller's language without spending an LLM
round-trip. The matcher is intentionally conservative — when in doubt, returns
None so the caller falls through to the LLM / qualifier flow.

Wording lifted from `docs/brand_profile.md` §9.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FaqAnswer:
    topic: str
    text: str


# Canonical answers per topic and language. Wording is lifted from the
# Host Training Manual FAQ verbatim where possible.
_ANSWERS: dict[str, dict[str, str]] = {
    "hours": {
        "en-US": (
            "We are open from eleven A M for lunch through eleven P M for dinner. "
            "On Thursdays, Fridays, and Saturdays we offer late-night service "
            "until one A M."
        ),
        "es-US": (
            "Abrimos a las once de la mañana para el almuerzo hasta las once de la "
            "noche para la cena. Los jueves, viernes y sábados ofrecemos servicio "
            "hasta la una de la madrugada."
        ),
        "ru-RU": (
            "Мы открыты с одиннадцати утра на ланч и до одиннадцати вечера на ужин. "
            "По четвергам, пятницам и субботам у нас работает поздний ужин до часа ночи."
        ),
    },
    "address": {
        "en-US": (
            "We are located at two fifty seven North Canon Drive in Beverly Hills, "
            "California."
        ),
        "es-US": (
            "Estamos en el doscientos cincuenta y siete de North Canon Drive, "
            "en Beverly Hills, California."
        ),
        "ru-RU": (
            "Мы находимся по адресу двести пятьдесят семь Норт Кэнон Драйв, "
            "Беверли-Хиллз, Калифорния."
        ),
    },
    "valet": {
        "en-US": "Yes, valet parking is available for seventeen dollars. We do not validate.",
        "es-US": (
            "Sí, contamos con valet parking por diecisiete dólares. "
            "No ofrecemos validación."
        ),
        "ru-RU": (
            "Да, у нас есть валет-парковка стоимостью семнадцать долларов. "
            "Мы не предоставляем валидацию."
        ),
    },
    "private_dining": {
        "en-US": (
            "Our private dining room accommodates up to fourteen guests "
            "comfortably. Our team would be glad to coordinate the details."
        ),
        "es-US": (
            "Nuestro comedor privado acomoda cómodamente hasta catorce huéspedes. "
            "Con gusto le coordinamos los detalles."
        ),
        "ru-RU": (
            "Наш приватный зал комфортно вмещает до четырнадцати гостей. "
            "Наша команда с радостью согласует детали."
        ),
    },
    "dj": {
        "en-US": (
            "We have a D J on Thursday, Friday, and Saturday nights, "
            "and during Sunday lunch service."
        ),
        "es-US": (
            "Tenemos un D J los jueves, viernes y sábados por la noche, "
            "y durante el almuerzo del domingo."
        ),
        "ru-RU": (
            "Диджей у нас по четвергам, пятницам и субботам вечером, "
            "а также во время воскресного ланча."
        ),
    },
    "dress_code": {
        "en-US": (
            "Our dress code is smart and elegant. We kindly ask guests to refrain "
            "from sportswear, beachwear, hoodies, shorts, and hats."
        ),
        "es-US": (
            "Nuestro código de vestimenta es elegante y refinado. Le pedimos "
            "amablemente evitar ropa deportiva, de playa, sudaderas con capucha, "
            "pantalones cortos y gorras."
        ),
        "ru-RU": (
            "У нас элегантный дресс-код. Просим воздержаться от спортивной "
            "и пляжной одежды, худи, шорт и головных уборов."
        ),
    },
    "id_alcohol": {
        "en-US": (
            "Anyone who appears twenty one or younger is asked to present a "
            "valid I D before being served alcohol."
        ),
        "es-US": (
            "Cualquier huésped que aparente veintiún años o menos deberá "
            "presentar una identificación válida antes de ser servido alcohol."
        ),
        "ru-RU": (
            "Гостей, выглядящих на двадцать один год или младше, мы просим "
            "предъявить документ, удостоверяющий возраст."
        ),
    },
    "smoking": {
        "en-US": (
            "Smoking is permitted only to the right of the entrance, where a "
            "designated ashtray is located. It is not permitted at the front of "
            "the restaurant or on the patio. Vaping is prohibited indoors and on "
            "the patio."
        ),
        "es-US": (
            "Permitimos fumar únicamente a la derecha de la entrada, donde se "
            "encuentra un cenicero designado. No se permite fumar al frente del "
            "restaurante ni en la terraza. El vapeo está prohibido en interiores "
            "y en la terraza."
        ),
        "ru-RU": (
            "Курение разрешено только справа от входа, где установлена пепельница. "
            "Перед рестораном и на террасе курить запрещено. Вейпинг запрещён "
            "и в помещении, и на террасе."
        ),
    },
    "gluten_free_pasta": {
        "en-US": (
            "Yes, we offer gluten free pasta. Our chef confirms the available "
            "shape each day."
        ),
        "es-US": (
            "Sí, ofrecemos pasta sin gluten. Nuestro chef confirma el formato "
            "disponible cada día."
        ),
        "ru-RU": (
            "Да, у нас есть паста без глютена. Шеф ежедневно подтверждает, "
            "какая форма доступна."
        ),
    },
    "gluten_free_pizza": {
        "en-US": "Unfortunately, gluten free pizza dough is not available at this location.",
        "es-US": "Lamentablemente, la masa de pizza sin gluten no está disponible en este local.",
        "ru-RU": "К сожалению, теста для пиццы без глютена в этом ресторане нет.",
    },
    "birthday": {
        "en-US": (
            "Each birthday guest receives a complimentary Tiramisu by Novikov. "
            "If you would like to bring an outside cake, our team will coordinate "
            "the details in advance."
        ),
        "es-US": (
            "Cada huésped que celebra su cumpleaños recibe un Tiramisú de cortesía "
            "por parte de Novikov. Si desea traer un pastel del exterior, nuestro "
            "equipo coordinará los detalles con antelación."
        ),
        "ru-RU": (
            "Каждому имениннику мы дарим тирамису от Novikov. Если хотите принести "
            "торт со стороны, наша команда заранее согласует детали."
        ),
    },
    "opened": {
        "en-US": "Novikov Beverly Hills opened on July fourth, two thousand twenty four.",
        "es-US": "Novikov Beverly Hills abrió el cuatro de julio de dos mil veinticuatro.",
        "ru-RU": "Novikov Beverly Hills открылся четвёртого июля две тысячи двадцать четвёртого года.",
    },
    "wifi": {
        "en-US": "Our guest wifi network is named Novikov Guest.",
        "es-US": "Nuestra red wifi para huéspedes se llama Novikov Guest.",
        "ru-RU": "Наша гостевая Wi-Fi сеть называется Novikov Guest.",
    },
}


# Topic-detection patterns. The first match wins, so order matters: more
# specific topics (e.g. "private dining") are listed before generic ones
# (e.g. "hours") that share keywords.
_TOPIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "private_dining",
        (
            r"\bprivate (?:dining|room|event)\b",
            r"\bp ?d ?r\b",
            r"\bбанкет\b",
            r"\bприватн\w*\b",
            r"\bprivado\b",
        ),
    ),
    (
        "valet",
        (
            r"\bvalet\b",
            r"\bparking\b",
            r"\bпарковк\w*\b",
            r"\bвалет\b",
            r"\bestacionamiento\b",
        ),
    ),
    (
        "dj",
        (
            r"\bd ?j\b",
            r"\blive music\b",
            r"\bдиджей\b",
            r"\bмузыка\b",
            r"\bm[uú]sica en vivo\b",
        ),
    ),
    (
        "dress_code",
        (
            r"\bdress code\b",
            r"\bwear\b",
            r"\bдресс[-\s]?код\b",
            r"\bкак одеваться\b",
            r"\bvestiment\w*\b",
            r"\bc[oó]digo de vestir\b",
        ),
    ),
    (
        "id_alcohol",
        (
            r"\b(?:id|i\.d\.)\b.*\b(?:alcohol|drink)\b",
            r"\b(?:alcohol|drink)\b.*\bid\b",
            r"\bcheck (?:my )?id\b",
            r"\bвозраст\b",
        ),
    ),
    (
        "smoking",
        (
            r"\bsmok\w*\b",
            r"\bvaping?\b",
            r"\bкурить\b",
            r"\bкурени\w*\b",
            r"\bfumar\b",
            r"\bvape\w*\b",
        ),
    ),
    (
        "gluten_free_pizza",
        (
            r"\bgluten[-\s]?free\b.*\bpizza\b",
            r"\bpizza\b.*\bgluten[-\s]?free\b",
            r"\bбезглютенов\w*\b.*\bпицц\w*\b",
        ),
    ),
    (
        "gluten_free_pasta",
        (
            # Require an explicit pasta reference so the broader 'what
            # gluten-free dishes do you have?' falls through to the menu
            # listing instead of returning the narrower pasta-only answer.
            r"\bgluten[-\s]?free\b.*\bpasta\b",
            r"\bpasta\b.*\bgluten[-\s]?free\b",
            r"\bпаст\w*\b.*\bбез\s+глютен\w*\b",
            r"\bбез\s+глютен\w*\b.*\bпаст\w*\b",
            r"\bpasta\b.*\bsin\s+gluten\b",
            r"\bsin\s+gluten\b.*\bpasta\b",
        ),
    ),
    (
        "birthday",
        (
            r"\bbirthday\b",
            r"\b(?:cake|tiramisu)\b",
            r"\bдень рожден\w*\b",
            r"\bтирамису\b",
            r"\bcumpleañ\w*\b",
            r"\bpastel\b",
        ),
    ),
    (
        "opened",
        (
            r"\bwhen (?:did|do) (?:you|novikov) open\b",
            r"\bopening date\b",
            r"\bкогда (?:открылись|вы открылись|открыли)\b",
            r"\bcu[aá]ndo (?:abri\w+|inaugur\w+)\b",
        ),
    ),
    (
        "wifi",
        (
            r"\bwi[-\s]?fi\b",
            r"\bвай[-\s]?фай\b",
            r"\bинтернет\b",
            r"\bинтерн[ея]т\b",
        ),
    ),
    (
        "address",
        (
            r"\b(?:address|located|location|where are you)\b",
            r"\bкак (?:вас|до вас) найти\b",
            r"\bадрес\b",
            r"\bdirecci[oó]n\b",
            r"\bd[oó]nde est[aá]n\b",
        ),
    ),
    (
        "hours",
        (
            r"\b(?:open|opening|hours|close|closing)\b",
            r"\bwhat time\b",
            r"\b(?:lunch|dinner)\s+(?:hours|time|service)\b",
            r"\b(?:часы|во сколько)\b",
            r"\bкогда (?:открыты|закрываетесь|работаете)\b",
            r"\bhorario\b",
            r"\b(?:abren|cierran)\b",
        ),
    ),
)


def detect_topic(utterance: str) -> str | None:
    """Return the FAQ topic key the utterance is asking about, or None."""
    text = utterance.lower()
    for topic, patterns in _TOPIC_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text):
                return topic
    return None


_BOOKING_INTENT_PATTERNS = (
    r"\bi'?d like\b",
    r"\bi want(?:\s+to)?\b",
    r"\bi would like\b",
    r"\bi need\b",
    r"\bcan i (?:book|reserve|order|celebrate|host|plan|get|have)\s+(?:a\s+)?(?:table|seat|reservation|spot)\b",
    r"\b(?:book|reserve|order|schedule|celebrate|host|plan)(?:\s+a)?\b",
    r"\b(?:a\s+)?table\s+(?:for|at|by|on|tomorrow|tonight)\b",
    # Implicit booking: '<adjective> dinner/lunch/brunch for N' or
    # '<adjective> dinner ... at/tomorrow/tonight'.
    r"\b(?:dinner|lunch|brunch|breakfast|reservation)\s+for\s+\w+\b",
    r"\b\w+\s+(?:dinner|lunch|brunch)\s+(?:for|tomorrow|tonight|today|on|at)\b",
    r"\bхоч[уе]\b",
    r"\bхотел[аи]?\s+бы\b",
    r"\b(?:бы\s+)?хотел[аи]?\b",
    r"\bзабронир\w*\b",
    r"\bзаказ\w*\b",
    r"\bотмет(?:ить|им)\b",
    r"\bпровед\w*\b",
    r"\bустро(?:ить|им)\b",
    r"\bquiero\b",
    r"\bquisiera\b",
    r"\bme gustaría\b",
    r"\breservar\b",
    r"\bcelebrar\b",
    r"\borganizar\b",
)


def _looks_like_booking(utterance: str) -> bool:
    lower = utterance.lower()
    return any(re.search(pat, lower) for pat in _BOOKING_INTENT_PATTERNS)


_MENU_QUESTION_PATTERNS = (
    r"\bdo\s+you\s+(?:have|serve|offer|carry)\b",
    r"\bis\s+(?:the\s+)?\w+\s+(?:available|on\s+the\s+menu)\b",
    r"\bwhat\s+(?:kind\s+of\s+)?(?:cocktails?|desserts?|wines?|pastas?|"
    r"steaks?|salads?|appetizers?|starters?)\b",
    r"\bare\s+there\s+any\b",
    r"\bcan\s+i\s+(?:get|order|have)\b",
    r"\b(?:есть|подаёте|подаете|есть\s+ли|у\s+вас\s+есть)\b",
    r"\bкакие\s+(?:у\s+вас\s+)?(?:десерты|коктейл\w+|вин\w+|паст\w+|стейк\w+)\b",
    r"\b(?:tienen|tienes|hay|sirven|ofrecen|tiene)\b",
    r"\bqué\s+(?:postres?|cocteles?|vinos?|pastas?)\b",
)
_MENU_CATEGORY_TOKENS: dict[str, str] = {
    # query keyword (lowercase, normalized) → canonical category in menu.json
    "dessert": "Desserts",
    "desserts": "Desserts",
    "десерт": "Desserts",
    "десерты": "Desserts",
    "postre": "Desserts",
    "postres": "Desserts",
    "cocktail": "Cocktails",
    "cocktails": "Cocktails",
    "коктейл": "Cocktails",
    "cóctel": "Cocktails",
    "coctel": "Cocktails",
    "wine": "Wine List",
    "wines": "Wine List",
    "вино": "Wine List",
    "vino": "Wine List",
    "pasta": "Pasta, Risotto & Soup",
    "паста": "Pasta, Risotto & Soup",
    "salad": "Salads",
    "salads": "Salads",
    "салат": "Salads",
    "ensalada": "Salads",
    "side": "Sides",
    "sides": "Sides",
    "гарнир": "Sides",
    "appetizer": "Appetizers & Charcuterie",
    "appetizers": "Appetizers & Charcuterie",
    "starter": "Appetizers & Charcuterie",
    "starters": "Appetizers & Charcuterie",
    "закуск": "Appetizers & Charcuterie",
    "meat": "Meat",
    "steak": "Meat",
    "стейк": "Meat",
    "carne": "Meat",
    "fish": "Fish & Seafood",
    "seafood": "Fish & Seafood",
    "рыб": "Fish & Seafood",
    "pescado": "Fish & Seafood",
}
_MENU_PRICE_PHRASES = (
    "how much",
    "price",
    "cost",
    "сколько стоит",
    "цена",
    "стоимость",
    "cuánto cuesta",
    "cuanto cuesta",
    "precio",
)


def _looks_like_menu_question(utterance: str) -> bool:
    lower = utterance.lower()
    return any(re.search(pat, lower) for pat in _MENU_QUESTION_PATTERNS)


def _detect_menu_category(utterance: str) -> str | None:
    lower = utterance.lower()
    for token, canonical in _MENU_CATEGORY_TOKENS.items():
        if token in lower:
            return canonical
    return None


def _format_dish_list(items, lang: str) -> str:
    names = [it.name for it in items[:6]]
    if not names:
        return ""
    if len(names) == 1:
        joined = names[0]
    else:
        joined = ", ".join(names[:-1]) + f", and {names[-1]}"
    if lang.startswith("ru"):
        joined = ", ".join(names[:-1]) + (f" и {names[-1]}" if len(names) > 1 else names[0])
        return f"Из этой категории у нас, например: {joined}. Полный выбор покажет команда при подтверждении."
    if lang.startswith("es"):
        joined = ", ".join(names[:-1]) + (f" y {names[-1]}" if len(names) > 1 else names[0])
        return f"Por ejemplo, ofrecemos: {joined}. Nuestro equipo le compartirá la selección completa."
    return f"For example, we have {joined}. Our team can share the full selection."


_DIETARY_KEYWORDS = (
    "vegan", "vegetarian", "gluten free", "gluten-free", "halal",
)


def _looks_like_dietary_only(description: str) -> bool:
    norm = description.lower().strip(" .,;:")
    parts = [p.strip() for p in re.split(r"[,/]| and ", norm) if p.strip()]
    return bool(parts) and all(
        any(kw in p for kw in _DIETARY_KEYWORDS) for p in parts
    )


def _format_dish_confirmation(item, lang: str) -> str:
    """Confirm a dish without volunteering price — price is only quoted
    when the caller explicitly asks 'how much / сколько стоит / cuánto cuesta'."""
    name = item.name
    if lang.startswith("ru"):
        head = f"Да, у нас есть {name}"
    elif lang.startswith("es"):
        head = f"Sí, tenemos {name}"
    else:
        head = f"Yes, we serve {name}"
    if item.description and not _looks_like_dietary_only(item.description):
        head += f" — {item.description}"
    return head + "."


def _format_price_phrase(price: str, lang: str) -> str:
    """Phrase used in standalone price answers ('Tomahawk is $241')."""
    is_market = price.lower().startswith("market")
    if lang.startswith("ru"):
        return "по рыночной цене" if is_market else f"стоит {price}"
    if lang.startswith("es"):
        return "a precio de mercado" if is_market else f"cuesta {price}"
    return "at market price" if is_market else f"is {price}"


_ALLERGEN_TRIGGERS: tuple[tuple[str, str], ...] = (
    (r"\ballerg(?:y|ic)\s+to\s+(\w[\w\s-]{2,30})\b", "match"),
    (r"\bintoleran(?:t|ce)\s+(?:to|of)\s+(\w[\w\s-]{2,30})\b", "match"),
    (r"\bi\s+can'?t\s+(?:have|eat)\s+(\w[\w\s-]{2,30})\b", "match"),
    (r"\b(?:без|нет)\s+(\w[\w\s-]{2,30})\b", "match"),
    (r"\bаллерги\w*\s+на\s+(\w[\w\s-]{2,30})\b", "match"),
    (r"\bнепереносимост\w*\s+(\w[\w\s-]{2,30})\b", "match"),
    (r"\bне\s+ем\s+(\w[\w\s-]{2,30})\b", "match"),
    (r"\balerg(?:ia|ico|ica)\s+a\s+(\w[\w\s-]{2,30})\b", "match"),
    (r"\bintoleran(?:cia|te)\s+(?:a|al)\s+(\w[\w\s-]{2,30})\b", "match"),
    (r"\bsoy\s+alérgic", "spanish"),
)
_DIETARY_QUESTION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(?:any\s+|what\s+|do\s+you\s+have\s+(?:any\s+)?)?vegan\b", "vegan"),
    (r"\bvegetarian\b", "vegetarian"),
    (r"\bgluten[\s-]?free\b", "gluten_free"),
    (r"\bwithout\s+gluten\b|\bno\s+gluten\b", "gluten_free"),
    (r"\bhalal\b", "halal"),
    (r"\bвеган\w*\b", "vegan"),
    (r"\bвегетариан\w*\b", "vegetarian"),
    (r"\bбез\s+глютен\w*\b|\bбезглютен\w*\b", "gluten_free"),
    (r"\bнепереносимост\w*\s+глютен\w*\b", "gluten_free"),
    (r"\bхаляль\b", "halal"),
    (r"\bvegan[oa]s?\b", "vegan"),
    (r"\bvegetarian[oa]s?\b", "vegetarian"),
    (r"\bsin\s+gluten\b", "gluten_free"),
)


def _detect_allergen(utterance: str) -> str | None:
    """Map a free-form allergy phrase to a canonical allergen key."""
    lower = utterance.lower()
    aliases = {
        "nut": "nuts", "nuts": "nuts", "peanut": "nuts", "peanuts": "nuts",
        "tree nut": "nuts", "tree nuts": "nuts", "almonds": "nuts",
        "walnuts": "nuts", "hazelnuts": "nuts", "pistachio": "nuts",
        "frutos secos": "nuts", "nuez": "nuts", "nueces": "nuts",
        "орех": "nuts", "орехи": "nuts", "арахис": "nuts",
        "shellfish": "shellfish", "seafood": "shellfish",
        "shrimp": "shellfish", "lobster": "shellfish", "crab": "shellfish",
        "marisco": "shellfish", "mariscos": "shellfish", "camarón": "shellfish",
        "морепродукт": "shellfish", "креветк": "shellfish",
        "lactose": "dairy", "dairy": "dairy", "milk": "dairy",
        "cheese": "dairy", "lácteo": "dairy", "lacteo": "dairy",
        "leche": "dairy", "молоч": "dairy", "лактоз": "dairy",
        "gluten": "gluten", "wheat": "gluten", "глютен": "gluten",
        "trigo": "gluten", "пшениц": "gluten",
        "fish": "fish", "рыб": "fish", "pescado": "fish",
        "egg": "egg", "eggs": "egg", "яйц": "egg", "huevo": "egg",
    }
    for pattern, _ in _ALLERGEN_TRIGGERS:
        m = re.search(pattern, lower)
        if not m or not m.groups():
            continue
        target = m.group(1)
        for alias, canonical in aliases.items():
            if alias in target:
                return canonical
    # Fallback: keyword anywhere in utterance, but only if 'allerg'/'аллерг' near.
    if re.search(r"\ballerg\w*\b|аллерги|alérgic", lower):
        for alias, canonical in aliases.items():
            if alias in lower:
                return canonical
    return None


def _detect_dietary_question(utterance: str) -> str | None:
    lower = utterance.lower()
    for pattern, tag in _DIETARY_QUESTION_PATTERNS:
        if re.search(pattern, lower):
            return tag
    return None


def _format_allergen_safe_list(items, allergen: str, lang: str) -> str:
    names = [it.name for it in items[:5]]
    if not names:
        if lang.startswith("ru"):
            return (
                "Пожалуйста, сообщите наш команде об аллергии — шеф подберёт безопасные варианты."
            )
        if lang.startswith("es"):
            return (
                "Por favor, infórmele a nuestro equipo sobre la alergia — el chef preparará opciones seguras."
            )
        return (
            "Please let our team know about the allergy — our chef will tailor safe options for you."
        )
    if lang.startswith("ru"):
        joined = ", ".join(names[:-1]) + (f" и {names[-1]}" if len(names) > 1 else names[0])
        return (
            f"Из безопасных опций, например: {joined}. "
            "Обязательно предупредите хостес — шеф уточнит детали по кухне."
        )
    if lang.startswith("es"):
        joined = ", ".join(names[:-1]) + (f" y {names[-1]}" if len(names) > 1 else names[0])
        return (
            f"Algunas opciones seguras: {joined}. "
            "Por favor, avise al equipo — el chef confirmará los detalles."
        )
    joined = ", ".join(names[:-1]) + (f", and {names[-1]}" if len(names) > 1 else names[0])
    return (
        f"Some safer options include {joined}. "
        "Please flag the allergy to our team — the chef will confirm preparations."
    )


def _format_dietary_list(items, tag: str, lang: str) -> str:
    names = [it.name for it in items[:5]]
    if not names:
        if lang.startswith("ru"):
            return "Уточню у нашей команды — мы подберём подходящие варианты."
        if lang.startswith("es"):
            return "Confirmaré con nuestro equipo las opciones disponibles."
        return "Let me confirm with our team what we can offer."
    label_map = {
        "vegan": ("vegan", "веганских", "veganas"),
        "vegetarian": ("vegetarian", "вегетарианских", "vegetarianas"),
        "gluten_free": ("gluten-free", "без глютена", "sin gluten"),
        "halal": ("halal", "халяль", "halal"),
    }
    label_en, label_ru, label_es = label_map[tag]
    if lang.startswith("ru"):
        joined = ", ".join(names[:-1]) + (f" и {names[-1]}" if len(names) > 1 else names[0])
        return f"Из {label_ru} вариантов: {joined}. Полный список покажет команда."
    if lang.startswith("es"):
        joined = ", ".join(names[:-1]) + (f" y {names[-1]}" if len(names) > 1 else names[0])
        return f"Opciones {label_es}: {joined}. Nuestro equipo le mostrará la lista completa."
    joined = ", ".join(names[:-1]) + (f", and {names[-1]}" if len(names) > 1 else names[0])
    return f"Our {label_en} options include {joined}. Our team can share the full list."


def _menu_answer(utterance: str, lang: str) -> FaqAnswer | None:
    from app.services import menu as menu_service

    # 0. Allergy / dietary takes priority over generic menu questions.
    allergen = _detect_allergen(utterance)
    if allergen:
        safe = menu_service.safe_for_allergen(allergen, limit=6)
        return FaqAnswer(
            topic=f"menu_allergen_{allergen}",
            text=_format_allergen_safe_list(safe, allergen, lang),
        )
    dietary_tag = _detect_dietary_question(utterance)
    if dietary_tag:
        items = menu_service.list_dietary(dietary_tag, limit=6)
        return FaqAnswer(
            topic=f"menu_dietary_{dietary_tag}",
            text=_format_dietary_list(items, dietary_tag, lang),
        )

    lower = utterance.lower()
    is_price_question = any(phrase in lower for phrase in _MENU_PRICE_PHRASES)

    # 1. Pricing question with a concrete dish in it: try to quote the price
    #    we have on file. Fall back to deferring only when we have no match.
    if is_price_question:
        hit = menu_service.has_item(utterance)
        if hit and hit.price:
            price_phrase = _format_price_phrase(hit.price, lang)
            text = f"{hit.name} {price_phrase}."
            return FaqAnswer(topic=f"menu_price_{hit.slug}", text=text)
        if lang.startswith("ru"):
            text = "Цены наша команда уточнит при подтверждении брони."
        elif lang.startswith("es"):
            text = "Nuestro equipo le compartirá los precios al confirmar la reserva."
        else:
            text = "Our team will share pricing when we confirm your reservation."
        return FaqAnswer(topic="menu_price_deferred", text=text)

    if not _looks_like_menu_question(utterance):
        return None

    # 2. Try specific dish first — exact-name and high-overlap matches win
    #    over category fallbacks ('do you have a tomahawk steak' → Tomahawk,
    #    not the generic Meat list).
    hit = menu_service.has_item(utterance)
    if hit:
        from app.services.menu import _normalize, _tokens

        q_tokens = _tokens(utterance)
        n_tokens = _tokens(hit.name)
        generic = {
            "steak", "pasta", "fish", "salad", "wine", "cocktail",
            "dessert", "desserts", "side", "sides", "appetizer", "starter",
            "meat", "soup", "pizza", "drink", "drinks", "bread", "sauce",
        }
        distinctive = (q_tokens & n_tokens) - generic
        strong = bool(q_tokens) and (
            _normalize(hit.name) in _normalize(utterance)
            or n_tokens.issubset(q_tokens)
            or len(q_tokens & n_tokens) >= 2
            or any(len(tok) >= 5 for tok in distinctive)
        )
        if strong:
            text = _format_dish_confirmation(hit, lang)
            return FaqAnswer(topic=f"menu_item_{hit.slug}", text=text)

    # 3. Category questions: 'what desserts do you have?'
    canonical = _detect_menu_category(utterance)
    if canonical:
        dishes = menu_service.list_category(canonical, limit=6)
        if dishes:
            return FaqAnswer(
                topic=f"menu_category_{canonical.lower()}",
                text=_format_dish_list(dishes, lang),
            )

    # 4. Weak single-token dish hit as last resort.
    if hit:
        text = _format_dish_confirmation(hit, lang)
        return FaqAnswer(topic=f"menu_item_{hit.slug}", text=text)

    return None


def match_faq(utterance: str, lang: str = "en-US") -> FaqAnswer | None:
    """Return a canonical FAQ answer if the utterance matches a known topic.

    The agent should call this *before* invoking the qualifier when no booking
    intent has been captured yet. If a topic matches, the answer should be
    spoken back, then the conversation can return to qualifying the call.

    If the caller's utterance carries a clear booking intent ('I'd like',
    'хочу забронировать', 'quisiera reservar'), we skip FAQ matching even
    when a topic surface-matches — the caller wants to *book* a private
    event, not learn the PDR capacity.
    """
    if _looks_like_booking(utterance):
        return None
    # Allergy questions take priority over any topic — they're high-stakes
    # and the canonical FAQ has nothing precise for arbitrary allergies.
    if _detect_allergen(utterance):
        menu_hit = _menu_answer(utterance, lang)
        if menu_hit:
            return menu_hit
    topic = detect_topic(utterance)
    if topic is not None:
        bundle = _ANSWERS[topic]
        text = bundle.get(lang) or bundle["en-US"]
        return FaqAnswer(topic=topic, text=text)
    return _menu_answer(utterance, lang)


__all__ = ["FaqAnswer", "match_faq", "detect_topic"]
