# Scenario report

- target: **in-process TestClient**
- scenarios: **20**, passed: **20**, failed: **0**
- average latency per scenario: **1954 ms**

## Summary

| # | scenario | result | turns | intent | name | party | datetime | label |
|---|---|---|---|---|---|---|---|---|
| 1 | `en_birthday_reservation_complimentary_tiramisu` | ✅ | 3 | private_event | Emily | 4 | 2026-05-09T04:00-07:00 | WARM |
| 2 | `en_gluten_free_pizza_unavailable` | ✅ | 1 | — | — | — | — | — |
| 3 | `en_late_night_thursday_reservation` | ✅ | 2 | reservation | Lucas | 2 | 2026-05-07T14:00-07:00 | WARM |
| 4 | `en_pdr_capacity_question` | ✅ | 1 | — | — | — | — | — |
| 5 | `en_private_event_small_warm_label` | ✅ | 3 | private_event | Sophia | 5 | 2026-05-08T19:00-07:00 | WARM |
| 6 | `en_reservation_happy_path` | ✅ | 2 | reservation | Alex | 4 | 2026-05-06T20:00-07:00 | WARM |
| 7 | `en_reservation_with_allergy_note` | ✅ | 2 | reservation | John | 2 | 2026-05-06T14:00-07:00 | WARM |
| 8 | `en_smoking_question` | ✅ | 1 | — | — | — | — | — |
| 9 | `en_takeout` | ✅ | 2 | takeout | Daniel | — | — | WARM |
| 10 | `es_dress_code_question` | ✅ | 1 | — | — | — | — | — |
| 11 | `es_reservation` | ✅ | 2 | reservation | Maria | 2 | 2026-05-06T02:00-07:00 | WARM |
| 12 | `faq_dj_in_russian` | ✅ | 1 | — | — | — | — | — |
| 13 | `faq_valet_parking` | ✅ | 1 | — | — | — | — | — |
| 14 | `large_party_needs_manager_approval` | ✅ | 3 | private_event | Maria | 15 | 2026-05-08T07:00-07:00 | HOT |
| 15 | `regression_explicit_date_must_be_captured` | ✅ | 4 | reservation | Кирилл | 4 | 2026-05-09T09:00-07:00 | WARM |
| 16 | `regression_seven_oclock_must_not_become_party_size` | ✅ | 3 | reservation | Кирилл | — | 2026-05-06T19:00-07:00 | — |
| 17 | `ru_hours_question` | ✅ | 1 | — | — | — | — | — |
| 18 | `ru_no_idea_for_time_must_not_be_locked` | ✅ | 4 | reservation | Андрей | 2 | — | — |
| 19 | `ru_reservation_simple_digit` | ✅ | 4 | reservation | Игорь | 4 | 2026-05-05T20:00-07:00 | WARM |
| 20 | `ru_reservation_with_language_switch` | ✅ | 5 | reservation | Кирилл | 4 | 2026-05-06T20:00-07:00 | WARM |

## Transcripts

### 1. `en_birthday_reservation_complimentary_tiramisu` — ✅ PASS

- 👤 _en-US_: Hi, I want to book a table for my birthday dinner
  - 🤖 Of course, happy to help with your birthday dinner. May I have your name, please?
- 👤 _en-US_: I'm Emily
  - 🤖 One moment. Hi Emily, how many guests will be joining you for your birthday dinner?
- 👤 _en-US_: Saturday at eight, party of four
  - 🤖 Hi Emily, your birthday dinner for four on Saturday, May 9th, is all set. Have a great celebration!

  _captured_: intent=`private_event` name=`Emily` party=`4` datetime=`2026-05-09T04:00-07:00` status=`qualified` label=`WARM`

### 2. `en_gluten_free_pizza_unavailable` — ✅ PASS

- 👤 _en-US_: Do you have gluten free pizza dough?
  - 🤖 Unfortunately, gluten free pizza dough is not available at this location.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 3. `en_late_night_thursday_reservation` — ✅ PASS

- 👤 _en-US_: Can I get a table at midnight on Thursday for two
  - 🤖 One moment, please.May I get your full name for the booking note?
- 👤 _en-US_: My name is Lucas
  - 🤖 One moment, please.Perfect, Lucas. I have everything noted: type reservation, party size 2, time 2026-05-07T14:00-07:00. Our team will confirm shortly.

  _captured_: intent=`reservation` name=`Lucas` party=`2` datetime=`2026-05-07T14:00-07:00` status=`qualified` label=`WARM`

### 4. `en_pdr_capacity_question` — ✅ PASS

- 👤 _en-US_: How big is your private dining room?
  - 🤖 Our private dining room accommodates up to fourteen guests comfortably. Our team would be glad to coordinate the details.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 5. `en_private_event_small_warm_label` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to plan a private event for five guests
  - 🤖 Hi there, could I get your name to start planning your event?
- 👤 _en-US_: This is Sophia
  - 🤖 Hi Sophia. Could you please let me know the date and time you'd like for your event?
- 👤 _en-US_: Friday at seven pm
  - 🤖 Got it, Sophia. Your reservation for five is set for Friday, May 8th, 2026 at 7 pm. Looking forward to having you.

  _captured_: intent=`private_event` name=`Sophia` party=`5` datetime=`2026-05-08T19:00-07:00` status=`qualified` label=`WARM`

### 6. `en_reservation_happy_path` — ✅ PASS

- 👤 _en-US_: Hi, I'd like a reservation for four guests tomorrow at 8 pm
  - 🤖 Sure, I can help with that reservation. May I have your name, please?
- 👤 _en-US_: My name is Alex
  - 🤖 Great, Alex. Your table for four is set for May 6th at 8 PM. Looking forward to having you with us. Goodbye!

  _captured_: intent=`reservation` name=`Alex` party=`4` datetime=`2026-05-06T20:00-07:00` status=`qualified` label=`WARM`

### 7. `en_reservation_with_allergy_note` — ✅ PASS

- 👤 _en-US_: I'd like a reservation tomorrow at eight pm for two
  - 🤖 Thanks for choosing Novikov Beverly Hills. May I have your name, please?
- 👤 _en-US_: My name is John, and I have a nut allergy
  - 🤖 John, your reservation for two on May 6th at 2 PM is set. We'll make a note of the nut allergy. Take care!

  _captured_: intent=`reservation` name=`John` party=`2` datetime=`2026-05-06T14:00-07:00` status=`qualified` label=`WARM`

### 8. `en_smoking_question` — ✅ PASS

- 👤 _en-US_: Can I smoke at your restaurant?
  - 🤖 Smoking is permitted only to the right of the entrance, where a designated ashtray is located. It is not permitted at the front of the restaurant or on the patio. Vaping is prohibited indoors and on the patio.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 9. `en_takeout` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to place an order for takeout
  - 🤖 Of course. Hi there, can I get your name for the order?
- 👤 _en-US_: My name is Daniel
  - 🤖 Thanks for that, Daniel. You're set for the takeout. Anything else I can help with?

  _captured_: intent=`takeout` name=`Daniel` party=`None` datetime=`None` status=`qualified` label=`WARM`

### 10. `es_dress_code_question` — ✅ PASS

- 👤 _es-US_ [→ es-US]: Hola, ¿cuál es el código de vestir del restaurante?
  - 🤖 Nuestro código de vestimenta es elegante y refinado. Le pedimos amablemente evitar ropa deportiva, de playa, sudaderas con capucha, pantalones cortos y gorras.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 11. `es_reservation` — ✅ PASS

- 👤 _es-US_ [→ es-US]: Hola, una reserva para dos personas mañana a las nueve
  - 🤖 Claro, ¿me puede dar su nombre, por favor?
- 👤 _es-US_: Me llamo Maria
  - 🤖 Perfecto, Maria. Tengo su reserva para dos personas el 6 de mayo a las 2 AM. ¡Gracias por elegirnos y que tenga un lindo día!

  _captured_: intent=`reservation` name=`Maria` party=`2` datetime=`2026-05-06T02:00-07:00` status=`qualified` label=`WARM`

### 12. `faq_dj_in_russian` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: У вас сегодня будет диджей
  - 🤖 Диджей у нас по четвергам, пятницам и субботам вечером, а также во время воскресного ланча.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 13. `faq_valet_parking` — ✅ PASS

- 👤 _en-US_ [→ en-US]: Is there valet parking?
  - 🤖 Yes, valet parking is available for seventeen dollars. We do not validate.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 14. `large_party_needs_manager_approval` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to book a private event for fifteen people
  - 🤖 Hi there, I can help with that. May I have your name, please?
- 👤 _en-US_: This is Maria
  - 🤖 Hi Maria. Could you let me know what date and time you're considering for your event?
- 👤 _en-US_: Next Friday at seven
  - 🤖 One moment, please.Perfect, Maria. I have everything noted: type private_event, party size 15, time 2026-05-08T07:00-07:00. Our team will confirm shortly.

  _captured_: intent=`private_event` name=`Maria` party=`15` datetime=`2026-05-08T07:00-07:00` status=`qualified` label=`HOT`

### 15. `regression_explicit_date_must_be_captured` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик на 9 мая
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 Кирилл, на сколько человек бронируем?
- 👤 _ru-RU_: На четверых
  - 🤖 Одну секунду, пожалуйста.Отлично, Кирилл. Я все зафиксировала. Тип запроса: reservation. Гостей: 4. Дата и время: 2026-05-09T09:00-07:00. Наша команда скоро свяжется для подтверждения.
- 👤 _ru-RU_: В семь вечера
  - 🤖 Разумеется, Записала вас на 9 мая в 19:00 на четверых. До встречи, Кирилл!

  _captured_: intent=`reservation` name=`Кирилл` party=`4` datetime=`2026-05-09T09:00-07:00` status=`qualified` label=`WARM`

### 16. `regression_seven_oclock_must_not_become_party_size` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик
  - 🤖 Здравствуйте! Как вас зовут?
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?
- 👤 _ru-RU_: В семь часов вечера
  - 🤖 На сколько персон будет ваша бронь?

  _captured_: intent=`reservation` name=`Кирилл` party=`None` datetime=`2026-05-06T19:00-07:00` status=`in_progress` label=`None`

### 17. `ru_hours_question` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Во сколько вы открыты сегодня
  - 🤖 Мы открыты с одиннадцати утра на ланч и до одиннадцати вечера на ужин. По четвергам, пятницам и субботам у нас работает поздний ужин до часа ночи.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 18. `ru_no_idea_for_time_must_not_be_locked` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик
  - 🤖 Здравствуйте! Могу узнать ваше имя?
- 👤 _ru-RU_: Меня зовут Андрей
  - 🤖 Андрей, сколько человек будет в вашей компании?
- 👤 _ru-RU_: Нас будет двое
  - 🤖 Одну секунду, пожалуйста.Какую дату и время вам удобно забронировать?
- 👤 _ru-RU_: Не знаю, как получится
  - 🤖 Когда бы вы хотели сделать резерв?

  _captured_: intent=`reservation` name=`Андрей` party=`2` datetime=`None` status=`in_progress` label=`None`

### 19. `ru_reservation_simple_digit` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Здравствуйте, я бы хотел забронировать столик
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Игорь
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?
- 👤 _ru-RU_: Нас будет четверо
  - 🤖 Одну секунду, пожалуйста.Какую дату и время вам удобно забронировать?
- 👤 _ru-RU_: Сегодня в восемь вечера
  - 🤖 Записала на четверых сегодня в восемь вечера, Игорь. До встречи!

  _captured_: intent=`reservation` name=`Игорь` party=`4` datetime=`2026-05-05T20:00-07:00` status=`qualified` label=`WARM`

### 20. `ru_reservation_with_language_switch` — ✅ PASS

- 👤 _en-US_ [→ ru-RU]: Hi, could you speak Russian please
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Я хотел бы забронировать столик
  - 🤖 Как вас зовут?
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 На сколько человек планируете бронирование, Кирилл?
- 👤 _ru-RU_: На четверых
  - 🤖 На какое число и время хотели бы забронировать?
- 👤 _ru-RU_: Завтра в восемь вечера
  - 🤖 Кирилл, столик на четверых завтра в восемь вечера забронирован. Ждём вас. Всего доброго!

  _captured_: intent=`reservation` name=`Кирилл` party=`4` datetime=`2026-05-06T20:00-07:00` status=`qualified` label=`WARM`
