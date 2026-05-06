# Scenario report

- target: **in-process TestClient**
- scenarios: **30**, passed: **30**, failed: **0**
- average latency per scenario: **1587 ms**

## Summary

| # | scenario | result | turns | intent | name | party | datetime | label |
|---|---|---|---|---|---|---|---|---|
| 1 | `en_birthday_reservation_complimentary_tiramisu` | ✅ | 3 | private_event | Emily | 4 | 2026-05-09T04:00-07:00 | WARM |
| 2 | `en_change_existing_reservation` | ✅ | 2 | reservation | Olivia | — | — | — |
| 3 | `en_directions_question` | ✅ | 1 | — | — | — | — | — |
| 4 | `en_full_booking_one_phrase` | ✅ | 1 | reservation | Sarah | 4 | 2026-05-07T16:00-07:00 | WARM |
| 5 | `en_gluten_free_pizza_unavailable` | ✅ | 1 | — | — | — | — | — |
| 6 | `en_kids_high_chair_request` | ✅ | 2 | reservation | Daniel | 2 | 2026-05-07T13:00-07:00 | WARM |
| 7 | `en_late_night_thursday_reservation` | ✅ | 2 | reservation | Lucas | 2 | 2026-05-07T14:00-07:00 | WARM |
| 8 | `en_pdr_capacity_question` | ✅ | 1 | — | — | — | — | — |
| 9 | `en_private_event_small_warm_label` | ✅ | 3 | private_event | Sophia | 5 | 2026-05-08T19:00-07:00 | WARM |
| 10 | `en_reservation_happy_path` | ✅ | 2 | reservation | Alex | 4 | 2026-05-07T20:00-07:00 | WARM |
| 11 | `en_reservation_with_allergy_note` | ✅ | 2 | reservation | John | 2 | 2026-05-07T14:00-07:00 | WARM |
| 12 | `en_smoking_question` | ✅ | 1 | — | — | — | — | — |
| 13 | `en_takeout` | ✅ | 2 | takeout | Daniel | — | — | WARM |
| 14 | `en_wifi_faq` | ✅ | 1 | — | — | — | — | — |
| 15 | `es_dress_code_question` | ✅ | 1 | — | — | — | — | — |
| 16 | `es_reservation` | ✅ | 2 | reservation | Maria | 2 | 2026-05-07T02:00-07:00 | WARM |
| 17 | `es_takeout` | ✅ | 2 | takeout | Carlos | — | — | WARM |
| 18 | `faq_dj_in_russian` | ✅ | 1 | — | — | — | — | — |
| 19 | `faq_valet_parking` | ✅ | 1 | — | — | — | — | — |
| 20 | `large_party_needs_manager_approval` | ✅ | 3 | private_event | Maria | 15 | 2026-05-08T07:00-07:00 | HOT |
| 21 | `regression_explicit_date_must_be_captured` | ✅ | 4 | reservation | Кирилл | 4 | 2026-05-09T09:00-07:00 | WARM |
| 22 | `regression_no_internal_field_echo` | ✅ | 2 | reservation | Sarah | 2 | 2026-05-07T14:00-07:00 | WARM |
| 23 | `regression_no_repeated_uvazhaemy_kirill` | ✅ | 4 | reservation | Кирилл | 2 | 2026-05-07T20:00-07:00 | WARM |
| 24 | `regression_party_not_overwritten_by_llm` | ✅ | 3 | reservation | Игорь | 2 | 2026-05-08T20:00-07:00 | WARM |
| 25 | `regression_seven_oclock_must_not_become_party_size` | ✅ | 3 | reservation | Кирилл | — | 2026-05-06T19:00-07:00 | — |
| 26 | `ru_birthday_reservation` | ✅ | 4 | private_event | Анна | 6 | 2026-05-06T20:00-07:00 | WARM |
| 27 | `ru_hours_question` | ✅ | 1 | — | — | — | — | — |
| 28 | `ru_no_idea_for_time_must_not_be_locked` | ✅ | 4 | reservation | Андрей | 2 | — | — |
| 29 | `ru_reservation_simple_digit` | ✅ | 4 | reservation | Игорь | 4 | 2026-05-06T20:00-07:00 | WARM |
| 30 | `ru_reservation_with_language_switch` | ✅ | 5 | reservation | Кирилл | 4 | 2026-05-07T20:00-07:00 | WARM |

## Transcripts

### 1. `en_birthday_reservation_complimentary_tiramisu` — ✅ PASS

- 👤 _en-US_: Hi, I want to book a table for my birthday dinner
  - 🤖 One moment, please.May I get your full name for the booking note?
- 👤 _en-US_: I'm Emily
  - 🤖 Hi Emily, happy to help with your birthday dinner. How many guests will be joining you?
- 👤 _en-US_: Saturday at eight, party of four
  - 🤖 Thank you, Emily. I have your private event for 4 guests on May 9 at 4 AM noted — our team will confirm shortly.

  _captured_: intent=`private_event` name=`Emily` party=`4` datetime=`2026-05-09T04:00-07:00` status=`qualified` label=`WARM`

### 2. `en_change_existing_reservation` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to change my existing reservation from seven pm to eight pm
  - 🤖 One moment, please.May I get your full name for the booking note?
- 👤 _en-US_: This is Olivia
  - 🤖 One moment. Hi Olivia! How many guests will be joining you?

  _captured_: intent=`reservation` name=`Olivia` party=`None` datetime=`None` status=`in_progress` label=`None`

### 3. `en_directions_question` — ✅ PASS

- 👤 _en-US_: Where are you located?
  - 🤖 We are located at two fifty seven North Canon Drive in Beverly Hills, California.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 4. `en_full_booking_one_phrase` — ✅ PASS

- 👤 _en-US_: Hi, I'd like a table for four people tomorrow at eight pm, my name is Sarah
  - 🤖 Thank you, Sarah. I have your reservation for 4 guests on May 7 at 4 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`Sarah` party=`4` datetime=`2026-05-07T16:00-07:00` status=`qualified` label=`WARM`

### 5. `en_gluten_free_pizza_unavailable` — ✅ PASS

- 👤 _en-US_: Do you have gluten free pizza dough?
  - 🤖 Unfortunately, gluten free pizza dough is not available at this location.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 6. `en_kids_high_chair_request` — ✅ PASS

- 👤 _en-US_: I'd like a reservation for two adults and one child tomorrow at seven pm, do you have a high chair?
  - 🤖 Of course, we can arrange for a high chair. May I have your name for the reservation?
- 👤 _en-US_: My name is Daniel
  - 🤖 Thank you, Daniel. I have your reservation for 2 guests on May 7 at 1 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`Daniel` party=`2` datetime=`2026-05-07T13:00-07:00` status=`qualified` label=`WARM`

### 7. `en_late_night_thursday_reservation` — ✅ PASS

- 👤 _en-US_: Can I get a table at midnight on Thursday for two
  - 🤖 One moment, please.May I get your full name for the booking note?
- 👤 _en-US_: My name is Lucas
  - 🤖 Thank you, Lucas. I have your reservation for 2 guests on May 7 at 2 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`Lucas` party=`2` datetime=`2026-05-07T14:00-07:00` status=`qualified` label=`WARM`

### 8. `en_pdr_capacity_question` — ✅ PASS

- 👤 _en-US_: How big is your private dining room?
  - 🤖 Our private dining room accommodates up to fourteen guests comfortably. Our team would be glad to coordinate the details.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 9. `en_private_event_small_warm_label` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to plan a private event for five guests
  - 🤖 One moment, please.May I get your full name for the booking note?
- 👤 _en-US_: This is Sophia
  - 🤖 One moment, please.What date and time should I note?
- 👤 _en-US_: Friday at seven pm
  - 🤖 Thank you, Sophia. I have your private event for 5 guests on May 8 at 7 PM noted — our team will confirm shortly.

  _captured_: intent=`private_event` name=`Sophia` party=`5` datetime=`2026-05-08T19:00-07:00` status=`qualified` label=`WARM`

### 10. `en_reservation_happy_path` — ✅ PASS

- 👤 _en-US_: Hi, I'd like a reservation for four guests tomorrow at 8 pm
  - 🤖 One moment, please.May I get your full name for the booking note?
- 👤 _en-US_: My name is Alex
  - 🤖 Thank you, Alex. I have your reservation for 4 guests on May 7 at 8 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`Alex` party=`4` datetime=`2026-05-07T20:00-07:00` status=`qualified` label=`WARM`

### 11. `en_reservation_with_allergy_note` — ✅ PASS

- 👤 _en-US_: I'd like a reservation tomorrow at eight pm for two
  - 🤖 One moment, please.May I get your full name for the booking note?
- 👤 _en-US_: My name is John, and I have a nut allergy
  - 🤖 Thank you, John. I have your reservation for 2 guests on May 7 at 2 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`John` party=`2` datetime=`2026-05-07T14:00-07:00` status=`qualified` label=`WARM`

### 12. `en_smoking_question` — ✅ PASS

- 👤 _en-US_: Can I smoke at your restaurant?
  - 🤖 Smoking is permitted only to the right of the entrance, where a designated ashtray is located. It is not permitted at the front of the restaurant or on the patio. Vaping is prohibited indoors and on the patio.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 13. `en_takeout` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to place an order for takeout
  - 🤖 One moment, please.May I get your full name for the booking note?
- 👤 _en-US_: My name is Daniel
  - 🤖 Thank you, Daniel. I have your takeout order noted — our team will confirm shortly.

  _captured_: intent=`takeout` name=`Daniel` party=`None` datetime=`None` status=`qualified` label=`WARM`

### 14. `en_wifi_faq` — ✅ PASS

- 👤 _en-US_: Do you have wifi for guests?
  - 🤖 Our guest wifi network is named Novikov Guest.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 15. `es_dress_code_question` — ✅ PASS

- 👤 _es-US_ [→ es-US]: Hola, ¿cuál es el código de vestir del restaurante?
  - 🤖 Nuestro código de vestimenta es elegante y refinado. Le pedimos amablemente evitar ropa deportiva, de playa, sudaderas con capucha, pantalones cortos y gorras.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 16. `es_reservation` — ✅ PASS

- 👤 _es-US_ [→ es-US]: Hola, una reserva para dos personas mañana a las nueve
  - 🤖 Un momento, por favor.¿Me comparte su nombre completo para la reserva?
- 👤 _es-US_: Me llamo Maria
  - 🤖 Gracias, Maria. He anotado su reserva para 2 personas el 7 de mayo a las 2 de la noche — nuestro equipo le confirmará en breve.

  _captured_: intent=`reservation` name=`Maria` party=`2` datetime=`2026-05-07T02:00-07:00` status=`qualified` label=`WARM`

### 17. `es_takeout` — ✅ PASS

- 👤 _es-US_ [→ es-US]: Hola, quisiera ordenar comida para llevar
  - 🤖 Un momento, por favor.¿Me comparte su nombre completo para la reserva?
- 👤 _es-US_: Me llamo Carlos
  - 🤖 Gracias, Carlos. He anotado su pedido para llevar — nuestro equipo le confirmará en breve.

  _captured_: intent=`takeout` name=`Carlos` party=`None` datetime=`None` status=`qualified` label=`WARM`

### 18. `faq_dj_in_russian` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: У вас сегодня будет диджей
  - 🤖 Диджей у нас по четвергам, пятницам и субботам вечером, а также во время воскресного ланча.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 19. `faq_valet_parking` — ✅ PASS

- 👤 _en-US_ [→ en-US]: Is there valet parking?
  - 🤖 Yes, valet parking is available for seventeen dollars. We do not validate.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 20. `large_party_needs_manager_approval` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to book a private event for fifteen people
  - 🤖 Hello, thanks for calling us. Could I have your name, please?
- 👤 _en-US_: This is Maria
  - 🤖 One moment, please.What date and time should I note?
- 👤 _en-US_: Next Friday at seven
  - 🤖 Thank you, Maria. I have your private event for 15 guests on May 8 at 7 AM noted — our team will confirm shortly.

  _captured_: intent=`private_event` name=`Maria` party=`15` datetime=`2026-05-08T07:00-07:00` status=`qualified` label=`HOT`

### 21. `regression_explicit_date_must_be_captured` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик на 9 мая
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?
- 👤 _ru-RU_: На четверых
  - 🤖 Спасибо, Кирилл. Я записала вашу бронь на 4 гостей на 9 мая в 9 утра. Наша команда скоро свяжется для подтверждения.
- 👤 _ru-RU_: В семь вечера
  - 🤖 Спасибо, Кирилл. Я записала вашу бронь на 4 гостей на 9 мая в 9 утра. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`reservation` name=`Кирилл` party=`4` datetime=`2026-05-09T09:00-07:00` status=`qualified` label=`WARM`

### 22. `regression_no_internal_field_echo` — ✅ PASS

- 👤 _en-US_ [→ en-US]: I'd like a reservation for two tomorrow at eight pm
  - 🤖 Hello! I'd be happy to help with your reservation for two tomorrow at eight pm. May I have your name, please?
- 👤 _en-US_: I am Sarah
  - 🤖 Thank you, Sarah. I have your reservation for 2 guests on May 7 at 2 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`Sarah` party=`2` datetime=`2026-05-07T14:00-07:00` status=`qualified` label=`WARM`

### 23. `regression_no_repeated_uvazhaemy_kirill` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Здравствуйте, я бы хотел забронировать столик
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?
- 👤 _ru-RU_: Нас будет двое
  - 🤖 Одну секунду, пожалуйста.Какую дату и время вам удобно забронировать?
- 👤 _ru-RU_: Завтра в восемь вечера
  - 🤖 Спасибо, Кирилл. Я записала вашу бронь на 2 гостей на 7 мая в 8 вечера. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`reservation` name=`Кирилл` party=`2` datetime=`2026-05-07T20:00-07:00` status=`qualified` label=`WARM`

### 24. `regression_party_not_overwritten_by_llm` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик на двух человек
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Игорь
  - 🤖 Одну секунду, пожалуйста.Какую дату и время вам удобно забронировать?
- 👤 _ru-RU_: 8 мая в восемь вечера
  - 🤖 Спасибо, Игорь. Я записала вашу бронь на 2 гостей на 8 мая в 8 вечера. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`reservation` name=`Игорь` party=`2` datetime=`2026-05-08T20:00-07:00` status=`qualified` label=`WARM`

### 25. `regression_seven_oclock_must_not_become_party_size` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?
- 👤 _ru-RU_: В семь часов вечера
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?

  _captured_: intent=`reservation` name=`Кирилл` party=`None` datetime=`2026-05-06T19:00-07:00` status=`in_progress` label=`None`

### 26. `ru_birthday_reservation` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Здравствуйте, я бы хотел отметить день рождения у вас в ресторане
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Анна
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?
- 👤 _ru-RU_: Нас будет шестеро
  - 🤖 Одну секунду, пожалуйста.Какую дату и время вам удобно забронировать?
- 👤 _ru-RU_: В субботу в восемь вечера
  - 🤖 Спасибо, Анна. Я записала ваше частное мероприятие на 6 гостей на 6 мая в 8 вечера. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`private_event` name=`Анна` party=`6` datetime=`2026-05-06T20:00-07:00` status=`qualified` label=`WARM`

### 27. `ru_hours_question` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Во сколько вы открыты сегодня
  - 🤖 Мы открыты с одиннадцати утра на ланч и до одиннадцати вечера на ужин. По четвергам, пятницам и субботам у нас работает поздний ужин до часа ночи.

  _captured_: intent=`None` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 28. `ru_no_idea_for_time_must_not_be_locked` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Андрей
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?
- 👤 _ru-RU_: Нас будет двое
  - 🤖 Одну секунду, пожалуйста.Какую дату и время вам удобно забронировать?
- 👤 _ru-RU_: Не знаю, как получится
  - 🤖 Одну секунду, пожалуйста.Какую дату и время вам удобно забронировать?

  _captured_: intent=`reservation` name=`Андрей` party=`2` datetime=`None` status=`in_progress` label=`None`

### 29. `ru_reservation_simple_digit` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Здравствуйте, я бы хотел забронировать столик
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Игорь
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?
- 👤 _ru-RU_: Нас будет четверо
  - 🤖 Одну секунду, пожалуйста.Какую дату и время вам удобно забронировать?
- 👤 _ru-RU_: Сегодня в восемь вечера
  - 🤖 Спасибо, Игорь. Я записала вашу бронь на 4 гостей на 6 мая в 8 вечера. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`reservation` name=`Игорь` party=`4` datetime=`2026-05-06T20:00-07:00` status=`qualified` label=`WARM`

### 30. `ru_reservation_with_language_switch` — ✅ PASS

- 👤 _en-US_ [→ ru-RU]: Hi, could you speak Russian please
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Я хотел бы забронировать столик
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?
- 👤 _ru-RU_: На четверых
  - 🤖 Одну секунду, пожалуйста.Какую дату и время вам удобно забронировать?
- 👤 _ru-RU_: Завтра в восемь вечера
  - 🤖 Спасибо, Кирилл. Я записала вашу бронь на 4 гостей на 7 мая в 8 вечера. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`reservation` name=`Кирилл` party=`4` datetime=`2026-05-07T20:00-07:00` status=`qualified` label=`WARM`
