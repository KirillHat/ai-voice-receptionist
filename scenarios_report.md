# Scenario report

- target: **in-process TestClient**
- scenarios: **32**, passed: **32**, failed: **0**
- average latency per scenario: **1489 ms**

## Summary

| # | scenario | result | turns | intent | name | party | datetime | label |
|---|---|---|---|---|---|---|---|---|
| 1 | `en_birthday_reservation_complimentary_tiramisu` | ✅ | 4 | private_event | Emily | 4 | 2026-05-09T20:00-07:00 | WARM |
| 2 | `en_change_existing_reservation` | ✅ | 2 | reservation | Olivia | — | — | — |
| 3 | `en_directions_question` | ✅ | 1 | general | — | — | — | — |
| 4 | `en_full_booking_one_phrase` | ✅ | 2 | reservation | Sarah | 4 | 2026-05-07T20:00-07:00 | WARM |
| 5 | `en_gluten_free_pizza_unavailable` | ✅ | 1 | general | — | — | — | — |
| 6 | `en_kids_high_chair_request` | ✅ | 3 | reservation | Daniel | 2 | 2026-05-07T19:00-07:00 | WARM |
| 7 | `en_late_night_thursday_reservation` | ✅ | 3 | reservation | Lucas | 2 | 2026-05-07T00:00-07:00 | WARM |
| 8 | `en_menu_dish_lookup` | ✅ | 1 | general | — | — | — | — |
| 9 | `en_pdr_capacity_question` | ✅ | 1 | private_event | — | — | — | — |
| 10 | `en_private_event_small_warm_label` | ✅ | 4 | private_event | Sophia | 5 | 2026-05-08T19:00-07:00 | WARM |
| 11 | `en_reservation_happy_path` | ✅ | 3 | reservation | Alex | 4 | 2026-05-07T20:00-07:00 | WARM |
| 12 | `en_reservation_with_allergy_note` | ✅ | 3 | reservation | John | 2 | 2026-05-07T20:00-07:00 | WARM |
| 13 | `en_smoking_question` | ✅ | 1 | general | — | — | — | — |
| 14 | `en_takeout` | ✅ | 3 | takeout | Daniel | — | — | WARM |
| 15 | `en_wifi_faq` | ✅ | 1 | general | — | — | — | — |
| 16 | `es_dress_code_question` | ✅ | 1 | general | — | — | — | — |
| 17 | `es_reservation` | ✅ | 3 | reservation | Maria | 2 | 2026-05-07T21:00-07:00 | WARM |
| 18 | `es_takeout` | ✅ | 3 | takeout | Carlos | — | — | WARM |
| 19 | `faq_dj_in_russian` | ✅ | 1 | general | — | — | 2026-05-06T19:00-07:00 | — |
| 20 | `faq_valet_parking` | ✅ | 1 | general | — | — | — | — |
| 21 | `large_party_needs_manager_approval` | ✅ | 4 | private_event | Maria | 15 | 2026-05-08T19:00-07:00 | HOT |
| 22 | `regression_explicit_date_must_be_captured` | ✅ | 4 | reservation | Кирилл | 4 | 2026-05-09T19:00-07:00 | — |
| 23 | `regression_no_internal_field_echo` | ✅ | 3 | reservation | Sarah | 2 | 2026-05-07T20:00-07:00 | WARM |
| 24 | `regression_no_repeated_uvazhaemy_kirill` | ✅ | 5 | reservation | Кирилл | 2 | 2026-05-07T20:00-07:00 | WARM |
| 25 | `regression_party_not_overwritten_by_llm` | ✅ | 4 | reservation | Игорь | 2 | 2026-05-08T20:00-07:00 | WARM |
| 26 | `regression_seven_oclock_must_not_become_party_size` | ✅ | 3 | reservation | Кирилл | — | 2026-05-06T19:00-07:00 | — |
| 27 | `ru_birthday_reservation` | ✅ | 5 | private_event | Анна | 6 | 2026-05-06T20:00-07:00 | WARM |
| 28 | `ru_hours_question` | ✅ | 1 | general | — | — | 2026-05-06T19:00-07:00 | — |
| 29 | `ru_menu_dessert_question` | ✅ | 1 | general | — | — | — | — |
| 30 | `ru_no_idea_for_time_must_not_be_locked` | ✅ | 4 | reservation | Андрей | 2 | — | — |
| 31 | `ru_reservation_simple_digit` | ✅ | 5 | reservation | Игорь | 4 | 2026-05-06T20:00-07:00 | WARM |
| 32 | `ru_reservation_with_language_switch` | ✅ | 6 | reservation | Кирилл | 4 | 2026-05-07T20:00-07:00 | WARM |

## Transcripts

### 1. `en_birthday_reservation_complimentary_tiramisu` — ✅ PASS

- 👤 _en-US_: Hi, I want to book a table for my birthday dinner
  - 🤖 Hello! I'd be happy to help with your birthday dinner. Could I get your name, please?
- 👤 _en-US_: I'm Emily
  - 🤖 Hi Emily, happy early birthday! How many guests are you planning to invite for your dinner?
- 👤 _en-US_: Saturday at eight, party of four
  - 🤖 Just to confirm: a private event for 4 guests on May 9 at 8 PM under Emily. Is that correct?
- 👤 _en-US_: Yes, that's correct
  - 🤖 Thank you, Emily. I have your private event for 4 guests on May 9 at 8 PM noted — our team will confirm shortly.

  _captured_: intent=`private_event` name=`Emily` party=`4` datetime=`2026-05-09T20:00-07:00` status=`qualified` label=`WARM`

### 2. `en_change_existing_reservation` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to change my existing reservation from seven pm to eight pm
  - 🤖 Hi there, I'd be happy to help with that change. May I have your name, please?
- 👤 _en-US_: This is Olivia
  - 🤖 Hi Olivia, how many guests will be joining you?

  _captured_: intent=`reservation` name=`Olivia` party=`None` datetime=`None` status=`in_progress` label=`None`

### 3. `en_directions_question` — ✅ PASS

- 👤 _en-US_: Where are you located?
  - 🤖 We are located at two fifty seven North Canon Drive in Beverly Hills, California.

  _captured_: intent=`general` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 4. `en_full_booking_one_phrase` — ✅ PASS

- 👤 _en-US_: Hi, I'd like a table for four people tomorrow at eight pm, my name is Sarah
  - 🤖 Just to confirm: a reservation for 4 guests on May 7 at 8 PM under Sarah. Is that correct?
- 👤 _en-US_: Yes, that's correct
  - 🤖 Thank you, Sarah. I have your reservation for 4 guests on May 7 at 8 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`Sarah` party=`4` datetime=`2026-05-07T20:00-07:00` status=`qualified` label=`WARM`

### 5. `en_gluten_free_pizza_unavailable` — ✅ PASS

- 👤 _en-US_: Do you have gluten free pizza dough?
  - 🤖 Unfortunately, gluten free pizza dough is not available at this location.

  _captured_: intent=`general` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 6. `en_kids_high_chair_request` — ✅ PASS

- 👤 _en-US_: I'd like a reservation for two adults and one child tomorrow at seven pm, do you have a high chair?
  - 🤖 Thanks for choosing us! Could I get the name for the reservation, please?
- 👤 _en-US_: My name is Daniel
  - 🤖 Just to confirm: a reservation for 2 guests on May 7 at 7 PM under Daniel. Is that correct?
- 👤 _en-US_: Yes, that's correct
  - 🤖 Thank you, Daniel. I have your reservation for 2 guests on May 7 at 7 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`Daniel` party=`2` datetime=`2026-05-07T19:00-07:00` status=`qualified` label=`WARM`

### 7. `en_late_night_thursday_reservation` — ✅ PASS

- 👤 _en-US_: Can I get a table at midnight on Thursday for two
  - 🤖 Thanks for calling Novikov Beverly Hills. I can help with that reservation for two at midnight on Thursday. May I have your name, please?
- 👤 _en-US_: My name is Lucas
  - 🤖 Just to confirm: a reservation for 2 guests on May 7 at 12 AM under Lucas. Is that correct?
- 👤 _en-US_: Yes, that's correct
  - 🤖 Thank you, Lucas. I have your reservation for 2 guests on May 7 at 12 AM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`Lucas` party=`2` datetime=`2026-05-07T00:00-07:00` status=`qualified` label=`WARM`

### 8. `en_menu_dish_lookup` — ✅ PASS

- 👤 _en-US_: Do you have a tomahawk steak?
  - 🤖 Yes, we serve Bistecca Tomahawk 45oz.

  _captured_: intent=`general` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 9. `en_pdr_capacity_question` — ✅ PASS

- 👤 _en-US_: How big is your private dining room?
  - 🤖 Our private dining room accommodates up to fourteen guests comfortably. Our team would be glad to coordinate the details.

  _captured_: intent=`private_event` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 10. `en_private_event_small_warm_label` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to plan a private event for five guests
  - 🤖 Hello, I'd be happy to help with that. May I have your name, please?
- 👤 _en-US_: This is Sophia
  - 🤖 One moment. Hi, Sophia. Could you let me know when you're planning to hold the event?
- 👤 _en-US_: Friday at seven pm
  - 🤖 Just to confirm: a private event for 5 guests on May 8 at 7 PM under Sophia. Is that correct?
- 👤 _en-US_: Yes, that's correct
  - 🤖 Thank you, Sophia. I have your private event for 5 guests on May 8 at 7 PM noted — our team will confirm shortly.

  _captured_: intent=`private_event` name=`Sophia` party=`5` datetime=`2026-05-08T19:00-07:00` status=`qualified` label=`WARM`

### 11. `en_reservation_happy_path` — ✅ PASS

- 👤 _en-US_: Hi, I'd like a reservation for four guests tomorrow at 8 pm
  - 🤖 Absolutely, we can help with that reservation for four tomorrow at 8 pm. Could I have your name, please?
- 👤 _en-US_: My name is Alex
  - 🤖 Just to confirm: a reservation for 4 guests on May 7 at 8 PM under Alex. Is that correct?
- 👤 _en-US_: Yes, that's correct
  - 🤖 Thank you, Alex. I have your reservation for 4 guests on May 7 at 8 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`Alex` party=`4` datetime=`2026-05-07T20:00-07:00` status=`qualified` label=`WARM`

### 12. `en_reservation_with_allergy_note` — ✅ PASS

- 👤 _en-US_: I'd like a reservation tomorrow at eight pm for two
  - 🤖 Hello! Thanks for calling Novikov Beverly Hills. May I have your name for the reservation?
- 👤 _en-US_: My name is John, and I have a nut allergy
  - 🤖 Some safer options include Babaganoush, Baby Calamari, Espellette Pepper & Tartar Sauce, Baked Aubergine Parmigiana, Beef Carpaccio, Parmesan Cheese & Rocket Salad, and Beef Ossobuco, Saffron Risotto & Lemon Zest. Please flag the allergy to our team — the chef will confirm preparations.
- 👤 _en-US_: Yes, that's correct
  - 🤖 Thank you, John. I have your reservation for 2 guests on May 7 at 8 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`John` party=`2` datetime=`2026-05-07T20:00-07:00` status=`qualified` label=`WARM`

### 13. `en_smoking_question` — ✅ PASS

- 👤 _en-US_: Can I smoke at your restaurant?
  - 🤖 Smoking is permitted only to the right of the entrance, where a designated ashtray is located. It is not permitted at the front of the restaurant or on the patio. Vaping is prohibited indoors and on the patio.

  _captured_: intent=`general` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 14. `en_takeout` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to place an order for takeout
  - 🤖 Hi there! Could I get your name to start the order?
- 👤 _en-US_: My name is Daniel
  - 🤖 Just to confirm: a takeout order under Daniel. Is that correct?
- 👤 _en-US_: Yes, that's correct
  - 🤖 Thank you, Daniel. I have your takeout order noted — our team will confirm shortly.

  _captured_: intent=`takeout` name=`Daniel` party=`None` datetime=`None` status=`qualified` label=`WARM`

### 15. `en_wifi_faq` — ✅ PASS

- 👤 _en-US_: Do you have wifi for guests?
  - 🤖 Our guest wifi network is named Novikov Guest.

  _captured_: intent=`general` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 16. `es_dress_code_question` — ✅ PASS

- 👤 _es-US_ [→ es-US]: Hola, ¿cuál es el código de vestir del restaurante?
  - 🤖 Nuestro código de vestimenta es elegante y refinado. Le pedimos amablemente evitar ropa deportiva, de playa, sudaderas con capucha, pantalones cortos y gorras.

  _captured_: intent=`general` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 17. `es_reservation` — ✅ PASS

- 👤 _es-US_ [→ es-US]: Hola, una reserva para dos personas mañana a las nueve
  - 🤖 ¡Hola! Claro, ¿puedo saber su nombre para completar la reserva?
- 👤 _es-US_: Me llamo Maria
  - 🤖 Para confirmar: una reserva para 2 personas el 7 de mayo a las 9 de la noche a nombre de Maria. ¿Es correcto?
- 👤 _es-US_: Sí, correcto
  - 🤖 Gracias, Maria. He anotado su reserva para 2 personas el 7 de mayo a las 9 de la noche — nuestro equipo le confirmará en breve.

  _captured_: intent=`reservation` name=`Maria` party=`2` datetime=`2026-05-07T21:00-07:00` status=`qualified` label=`WARM`

### 18. `es_takeout` — ✅ PASS

- 👤 _es-US_ [→ es-US]: Hola, quisiera ordenar comida para llevar
  - 🤖 ¡Hola! Claro, puedo ayudarte con eso. ¿Me podrías decir tu nombre, por favor?
- 👤 _es-US_: Me llamo Carlos
  - 🤖 Para confirmar: un pedido para llevar a nombre de Carlos. ¿Es correcto?
- 👤 _es-US_: Sí, correcto
  - 🤖 Gracias, Carlos. He anotado su pedido para llevar — nuestro equipo le confirmará en breve.

  _captured_: intent=`takeout` name=`Carlos` party=`None` datetime=`None` status=`qualified` label=`WARM`

### 19. `faq_dj_in_russian` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: У вас сегодня будет диджей
  - 🤖 Диджей у нас по четвергам, пятницам и субботам вечером, а также во время воскресного ланча.

  _captured_: intent=`general` name=`None` party=`None` datetime=`2026-05-06T19:00-07:00` status=`in_progress` label=`None`

### 20. `faq_valet_parking` — ✅ PASS

- 👤 _en-US_: Is there valet parking?
  - 🤖 Yes, valet parking is available for seventeen dollars. We do not validate.

  _captured_: intent=`general` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 21. `large_party_needs_manager_approval` — ✅ PASS

- 👤 _en-US_: Hi, I'd like to book a private event for fifteen people
  - 🤖 Hi there, thanks for reaching out. Could I get your name, please?
- 👤 _en-US_: This is Maria
  - 🤖 Hi Maria, when were you thinking of hosting your event?
- 👤 _en-US_: Next Friday at seven
  - 🤖 Just to confirm: a private event for 15 guests on May 8 at 7 PM under Maria. Is that correct?
- 👤 _en-US_: Yes, that's correct
  - 🤖 Thank you, Maria. I have your private event for 15 guests on May 8 at 7 PM noted — our team will confirm shortly.

  _captured_: intent=`private_event` name=`Maria` party=`15` datetime=`2026-05-08T19:00-07:00` status=`qualified` label=`HOT`

### 22. `regression_explicit_date_must_be_captured` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик на 9 мая
  - 🤖 Разумеется, Здравствуйте! Для какого количества гостей бронируем?
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 Скажите, пожалуйста, сколько человек будет в вашей компании?
- 👤 _ru-RU_: На четверых
  - 🤖 Уточняю: бронь на 4 гостей на 9 мая в 7 вечера на имя Кирилл. Всё верно?
- 👤 _ru-RU_: В семь вечера
  - 🤖 Уточняю: бронь на 4 гостей на 9 мая в 7 вечера на имя Кирилл. Всё верно?

  _captured_: intent=`reservation` name=`Кирилл` party=`4` datetime=`2026-05-09T19:00-07:00` status=`awaiting_confirmation` label=`None`

### 23. `regression_no_internal_field_echo` — ✅ PASS

- 👤 _en-US_: I'd like a reservation for two tomorrow at eight pm
  - 🤖 Hi there! Could I get your name for the reservation?
- 👤 _en-US_: I am Sarah
  - 🤖 Just to confirm: a reservation for 2 guests on May 7 at 8 PM under Sarah. Is that correct?
- 👤 _en-US_: Yes, that's correct
  - 🤖 Thank you, Sarah. I have your reservation for 2 guests on May 7 at 8 PM noted — our team will confirm shortly.

  _captured_: intent=`reservation` name=`Sarah` party=`2` datetime=`2026-05-07T20:00-07:00` status=`qualified` label=`WARM`

### 24. `regression_no_repeated_uvazhaemy_kirill` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Здравствуйте, я бы хотел забронировать столик
  - 🤖 Здравствуйте! С удовольствием помогу вам с бронированием. На какое имя сделать резерв?
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 На сколько человек будет бронирование?
- 👤 _ru-RU_: Нас будет двое
  - 🤖 На какое время вы хотели бы забронировать столик?
- 👤 _ru-RU_: Завтра в восемь вечера
  - 🤖 Уточняю: бронь на 2 гостей на 7 мая в 8 вечера на имя Кирилл. Всё верно?
- 👤 _ru-RU_: Да, всё верно
  - 🤖 Спасибо, Кирилл. Я записала вашу бронь на 2 гостей на 7 мая в 8 вечера. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`reservation` name=`Кирилл` party=`2` datetime=`2026-05-07T20:00-07:00` status=`qualified` label=`WARM`

### 25. `regression_party_not_overwritten_by_llm` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик на двух человек
  - 🤖 Здравствуйте! Рада помочь с бронированием. На какое число и время вы бы хотели забронировать столик?
- 👤 _ru-RU_: Меня зовут Игорь
  - 🤖 Одну секунду, пожалуйста.Какую дату и время вам удобно забронировать?
- 👤 _ru-RU_: 8 мая в восемь вечера
  - 🤖 Уточняю: бронь на 2 гостей на 8 мая в 8 вечера на имя Игорь. Всё верно?
- 👤 _ru-RU_: Да, всё верно
  - 🤖 Спасибо, Игорь. Я записала вашу бронь на 2 гостей на 8 мая в 8 вечера. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`reservation` name=`Игорь` party=`2` datetime=`2026-05-08T20:00-07:00` status=`qualified` label=`WARM`

### 26. `regression_seven_oclock_must_not_become_party_size` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик
  - 🤖 Здравствуйте! Рада помочь с бронированием. На какое имя записать столик?
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 Сколько человек будет в вашей компании, Кирилл?
- 👤 _ru-RU_: В семь часов вечера
  - 🤖 Скажите, пожалуйста, сколько человек будет в вашей компании?

  _captured_: intent=`reservation` name=`Кирилл` party=`None` datetime=`2026-05-06T19:00-07:00` status=`in_progress` label=`None`

### 27. `ru_birthday_reservation` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Здравствуйте, я бы хотел отметить день рождения у вас в ресторане
  - 🤖 Здравствуйте! Поможем организовать. Как вас зовут?
- 👤 _ru-RU_: Меня зовут Анна
  - 🤖 Скажите, пожалуйста, на сколько человек планируете мероприятие?
- 👤 _ru-RU_: Нас будет шестеро
  - 🤖 На какое число и время планируете мероприятие?
- 👤 _ru-RU_: В субботу в восемь вечера
  - 🤖 Уточняю: частное мероприятие на 6 гостей на 6 мая в 8 вечера на имя Анна. Всё верно?
- 👤 _ru-RU_: Да, всё верно
  - 🤖 Спасибо, Анна. Я записала ваше частное мероприятие на 6 гостей на 6 мая в 8 вечера. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`private_event` name=`Анна` party=`6` datetime=`2026-05-06T20:00-07:00` status=`qualified` label=`WARM`

### 28. `ru_hours_question` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Во сколько вы открыты сегодня
  - 🤖 Мы открыты с одиннадцати утра на ланч и до одиннадцати вечера на ужин. По четвергам, пятницам и субботам у нас работает поздний ужин до часа ночи.

  _captured_: intent=`general` name=`None` party=`None` datetime=`2026-05-06T19:00-07:00` status=`in_progress` label=`None`

### 29. `ru_menu_dessert_question` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Какие у вас десерты?
  - 🤖 Из этой категории у нас, например: Apple Tarte, Assorted Fruit Bowl With Whipped Cream, Cannoli, Caramel Ice Cream, Cigara Novikov и Classic Creme Brulee. Полный выбор покажет команда при подтверждении.

  _captured_: intent=`general` name=`None` party=`None` datetime=`None` status=`in_progress` label=`None`

### 30. `ru_no_idea_for_time_must_not_be_locked` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Я хотел бы забронировать столик
  - 🤖 Одну секунду, пожалуйста.Подскажите, пожалуйста, ваше полное имя для брони.
- 👤 _ru-RU_: Меня зовут Андрей
  - 🤖 Одну секунду, пожалуйста.На сколько гостей оформить заявку?
- 👤 _ru-RU_: Нас будет двое
  - 🤖 На какое время хотите забронировать столик?
- 👤 _ru-RU_: Не знаю, как получится
  - 🤖 Конечно, Андрей. На какое время хотели бы забронировать столик?

  _captured_: intent=`reservation` name=`Андрей` party=`2` datetime=`None` status=`in_progress` label=`None`

### 31. `ru_reservation_simple_digit` — ✅ PASS

- 👤 _ru-RU_ [→ ru-RU]: Здравствуйте, я бы хотел забронировать столик
  - 🤖 Здравствуйте! Сколько человек будет в вашей компании?
- 👤 _ru-RU_: Меня зовут Игорь
  - 🤖 Сколько человек будет в вашей компании?
- 👤 _ru-RU_: Нас будет четверо
  - 🤖 На какое число и время хотите забронировать столик?
- 👤 _ru-RU_: Сегодня в восемь вечера
  - 🤖 Уточняю: бронь на 4 гостей на 6 мая в 8 вечера на имя Игорь. Всё верно?
- 👤 _ru-RU_: Да, всё верно
  - 🤖 Спасибо, Игорь. Я записала вашу бронь на 4 гостей на 6 мая в 8 вечера. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`reservation` name=`Игорь` party=`4` datetime=`2026-05-06T20:00-07:00` status=`qualified` label=`WARM`

### 32. `ru_reservation_with_language_switch` — ✅ PASS

- 👤 _en-US_ [→ ru-RU]: Hi, could you speak Russian please
  - 🤖 Здравствуйте! Конечно, можем говорить по-русски. Могу я узнать ваше имя?
- 👤 _ru-RU_: Я хотел бы забронировать столик
  - 🤖 Конечно, с удовольствием помогу с бронированием. На какое число и время планируете?
- 👤 _ru-RU_: Меня зовут Кирилл
  - 🤖 Конечно, Кирилл. Сколько человек планируете?
- 👤 _ru-RU_: На четверых
  - 🤖 Разумеется, На какое время хотите столик?
- 👤 _ru-RU_: Завтра в восемь вечера
  - 🤖 Уточняю: бронь на 4 гостей на 7 мая в 8 вечера на имя Кирилл. Всё верно?
- 👤 _ru-RU_: Да, всё верно
  - 🤖 Спасибо, Кирилл. Я записала вашу бронь на 4 гостей на 7 мая в 8 вечера. Наша команда скоро свяжется для подтверждения.

  _captured_: intent=`reservation` name=`Кирилл` party=`4` datetime=`2026-05-07T20:00-07:00` status=`qualified` label=`WARM`
