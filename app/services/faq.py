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
            r"\bgluten[-\s]?free\b",
            r"\bбез глютена\b",
            r"\bбезглютенов\w*\b",
            r"\bsin gluten\b",
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
    r"\bcan i (?:book|reserve|order|celebrate|host|plan)\b",
    r"\b(?:book|reserve|order|schedule|celebrate|host|plan)(?:\s+a)?\b",
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
    topic = detect_topic(utterance)
    if topic is None:
        return None
    bundle = _ANSWERS[topic]
    text = bundle.get(lang) or bundle["en-US"]
    return FaqAnswer(topic=topic, text=text)


__all__ = ["FaqAnswer", "match_faq", "detect_topic"]
