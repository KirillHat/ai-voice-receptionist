# Real-call analysis

- analyzed: **6** calls (>= 15s)
- total issues flagged: **2**
- prod URL: https://ai-voice-production-eb9e.up.railway.app

## Summary

| # | date | dur | result | intent | name | party | datetime | issues |
|---|---|---|---|---|---|---|---|---|
| 1 | Tue, 05 May 2026 21:09:33 | 54s | ⚠️ | — | — | — | — | 1 |
| 2 | Tue, 05 May 2026 20:44:36 | 22s | ✅ | — | — | — | — | 0 |
| 3 | Tue, 05 May 2026 20:25:24 | 71s | ⚠️ | — | — | — | — | 1 |
| 4 | Tue, 05 May 2026 16:51:57 | 50s | ✅ | — | — | — | — | 0 |
| 5 | Tue, 05 May 2026 16:34:28 | 117s | ✅ | — | — | — | — | 0 |
| 6 | Tue, 05 May 2026 16:18:46 | 100s | ✅ | — | — | — | — | 0 |

- prod URL: https://ai-voice-production-eb9e.up.railway.app


## 1. CA1f887e280ace45a116279950e57bbb06 — ⚠️

- date: Tue, 05 May 2026 21:09:33
- duration: 54s
- recording: `RE20f8c86e0ce4d3103524466edfb7ba31`
- captured: _(call session not found in prod DB — likely lost on container restart)_

### Issues

- ⚠️ Caller said the agent misheard them — likely field captured wrong

### Whisper transcript

```
Good evening. Thank you for calling Novikov Beverly Hills. How may I help you? Could you speak Russian? Конечно, могу говорить по-русски. Как я могу вам помочь? Я хотел бы забронировать столик на 9 мая. Как вас зовут? Меня зовут Кирилл. Кирилл, когда вы хотели бы прийти? В 7 часов вечера. Разумеется, Кирилл. Ваша бронь на 7 человек на 6 мая в 7 вечера подтверждена. Хорошего дня. Я не говорил 7 вечера, а 7 человек. Спасибо, Кирилл. У вас забронировано на 7 человек 6 мая на 7 вечера.
```

## 2. CAd102d5321aa35844fe98a261271d2820 — ✅

- date: Tue, 05 May 2026 20:44:36
- duration: 22s
- recording: `REc2db058b7f77465be297ebdec3c2e003`
- captured: _(call session not found in prod DB — likely lost on container restart)_

_No issues detected._

### Whisper transcript

```
Hello.
```

## 3. CAef8127f0aa619056132f41f418a17fc8 — ⚠️

- date: Tue, 05 May 2026 20:25:24
- duration: 71s
- recording: `RE5134ae8f095fbac974eef1d44e6744b4`
- captured: _(call session not found in prod DB — likely lost on container restart)_

### Issues

- ⚠️ Holding phrase repeated 3+ times — LLM probably stalled

### Whisper transcript

```
Good evening. Thank you for calling Novikov Beverly Hills. How may I help you? Can you speak Russian? Одну секунду, пожалуйста. Подскажите, пожалуйста, ваше полное имя для брони. Kirill. Kirill. Одну секунду, пожалуйста. Какую дату и время вам удобно забронировать? 8 мая. Одну секунду, пожалуйста. Какую дату и время вам удобно забронировать? 8 мая, в 8 вечера. Одну секунду, пожалуйста. Отлично, Kirill. Я все зафиксировала. Тип запроса – General. Гостей – 8. Дата и время – 2026-05-06-08007. Наша команда скоро свяжется для подтверждения.
```

## 4. CA4c10a0349253ff867328cf50e04d8982 — ✅

- date: Tue, 05 May 2026 16:51:57
- duration: 50s
- recording: `REb15b2c3036ecbd7a003e2abeadcdd619`
- captured: _(call session not found in prod DB — likely lost on container restart)_

_No issues detected._

### Whisper transcript

```
Good evening. Thank you for calling Novikov Beverly Hills. How may I help you? Thank you for calling. May I have your name, please? Speak Russian, please. Пожалуйста. Когда вы планируете посетить наш ресторан? Я планирую посетить 8 мая. Пожалуйста, подтвердите. На какое время вы планируете посетить нас 8 мая? В 8 вечера. Пожалуйста, уточните. На какую дату вы хотите сделать резервирование на 8 вечера? В 8 мая. Какое время вам подходит для резервации на 8 мая?
```

## 5. CA5da70a7aaca5765adc951c16d01f22de — ✅

- date: Tue, 05 May 2026 16:34:28
- duration: 117s
- recording: `RE77c3239684ef2322a7b3e20d6920ecd1`
- captured: _(call session not found in prod DB — likely lost on container restart)_

_No issues detected._

### Whisper transcript

```
Добрый вечер. Спасибо, что звонили из Беверли-Хиллз. Как могу помочь вам? Можете говорить по-русски, пожалуйста? Конечно, я могу говорить по-русски. Как я могу помочь вам сегодня? Я хотел бы забронировать столик на двух человек. Благодарю вас за звонок. Как вас зовут? Чтобы я мог оформить вашу бронь. Меня зовут Кирилл. Здравствуйте, Кирилл. Какое время вы планируете посетить наш ресторан? Я планирую посетить его завтра в 8 часов вечера. Уважаемый Кирилл, благодарю вас за информацию. Могу я уточнить, на какую дату вы планируете сделать резервирование на 8 часов вечера? Давайте на 8 мая. Уважаемый Кирилл, позвольте уточнить, на какое время вы планируете забронировать столик на 8 мая? На 8 вечера. Уважаемый Кирилл, для оформления резервации на 8 человек могу уточнить, на какую дату вы планируете посетить наш ресторан? Там ошибка, я говорил на двух человек. Уважаемый Кирилл, позвольте уточнить время вашей брони. Когда вы планируете посетить наш ресторан? 8 вечера. Уважаемый Кирилл, благодарю вас за информацию. Могу я уточнить дату вашей резервации на 8 вечера? 8 мая. Уважаемый Кирилл, позвольте уточнить, на какое время вы планируете сделать резервирование на 8 мая? 8 вечера. Уважаемый Кирилл...
```

## 6. CA1d1d14249e64d00bc3805142abc14711 — ✅

- date: Tue, 05 May 2026 16:18:46
- duration: 100s
- recording: `RE4a5bd0025a9aeebf9be68644a7241150`
- captured: _(call session not found in prod DB — likely lost on container restart)_

_No issues detected._

### Whisper transcript

```
Good evening. Thank you for calling Novikov Beverly Hills. How may I help you? May I have your name, please? My name is Kirill. Thank you for calling, Kirill. May I ask when you would like to make your reservation? I would like reservation for two person. May I inquire about the date and time you would prefer for your reservation? I would like reservation on 10 May for two people. May I have the date and time you would like to make a reservation for, please? May 10. May I have the date and time you would like to make your reservation for, Kirill? 10 PM. Thank you, Kirill. I have noted your reservation for two at 10 PM. We look forward to welcoming you. Can I speak Russian or Italian? Certainly, Kirill. We can assist you in English, but let me check with my manager regarding language options for your reservation. Thank you. My pleasure, Kirill. We look forward to welcoming you at 10 PM.
```