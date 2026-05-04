# 📚 Справочник команд Zapret Optimizer

Полный список всех доступных команд с описанием, параметрами и примерами использования.

---

## 🚀 Быстрый старт

```cmd
:: 1. Инициализация (проверка окружения)
zapret-optimizer.exe init

:: 2. Запуск оптимизации (3 цикла)
zapret-optimizer.exe optimize

:: 3. Запуск лучшей конфигурации
zapret-optimizer.exe run-best
```

---

## 📋 Основные команды

### `init`
Проверка окружения и инициализация.

**Что проверяет:**
- Наличие прав администратора
- Наличие zapret в системе
- Наличие curl для тестирования
- Создание необходимых директорий

**Пример:**
```cmd
zapret-optimizer.exe init
```

---

### `optimize`
Запуск 3-цикловой оптимизации конфигураций.

**Процесс:**
1. **Цикл 1**: Тестирование базовых конфигураций
2. **Цикл 2**: Мутация лучших (изменение параметров)
3. **Цикл 3**: Комбинирование лучших из разных стратегий

**Автоматические улучшения:**
- При равном score выбирает конфиг с меньшим пингом

**Параметры:**
| Параметр | Описание |
|----------|----------|
| `--sites-file <файл>` | Кастомный список сайтов для тестирования |

**Результат:** `optimizer_state.json` с рейтингом всех протестированных конфигураций.

**Примеры:**
```cmd
:: Стандартная оптимизация
zapret-optimizer.exe optimize

:: С кастомным списком сайтов
zapret-optimizer.exe optimize --sites-file my_sites.txt
```

---

### `run-best`
Запуск лучшей найденной конфигурации.

**Требования:**
- Выполнена команда `optimize`
- Существует файл `results.json`

**Пример:**
```cmd
zapret-optimizer.exe run-best
```

---

### `status`
Показать текущий статус оптимизации.

**Выводит:**
- Прогресс по циклам
- Количество протестированных конфигураций
- Текущий лучший результат
- Общий прогресс в процентах

**Пример:**
```cmd
zapret-optimizer.exe status
```

---

### `list`
Вывести список всех протестированных конфигураций, отсортированных по рейтингу.

**Колонки вывода:**
| Колонка | Описание |
|---------|----------|
| `Rank` | Позиция в рейтинге |
| `Name` | Имя конфигурации |
| `Score` | Процент успешных тестов (0-100) |
| `Tests` | Пройдено/Всего тестов |
| `Ping` | Средний пинг (мс) |
| `Cyc` | Цикл генерации (1, 2 или 3) |

**Сортировка:**
1. По убыванию Score
2. При равном Score — по возрастанию Ping (меньше = лучше)

**Пример:**
```cmd
zapret-optimizer.exe list
```

**Пример вывода:**
```
=== All Tested Configs (by score) ===
Rank  Name                    Score   Tests   Ping      Cyc
------------------------------------------------------------
1     combo_general_mut_3     98.5    15/15   45ms      3   *
2     mutant_general_5        98.5    15/15   78ms      2
3     general                 96.0    14/15   52ms      1
```

* `*` — отмечен текущий лучший конфиг

---

### `compare`
Сравнить две конфигурации (показать отличия).

**Параметры:**
- `config1` — путь к первой конфигурации
- `config2` — путь ко второй конфигурации

**Пример:**
```cmd
zapret-optimizer.exe compare cycle-1/general.bat cycle-2/mutant_general_1.bat
```

---

## 🌐 Telegram Proxy (tg-ws-proxy)

### `install-proxy`
Проверка и установка tg-ws-proxy.

**Действия:**
- Проверка наличия `TgWsProxy_windows.exe`
- Автоматическая загрузка при отсутствии
- Проверка работоспособности

**Пример:**
```cmd
zapret-optimizer.exe install-proxy
```

---

### `start-proxy`
Запуск tg-ws-proxy.

**Опции:**
| Опция | Описание | По умолчанию |
|-------|----------|--------------|
| `--port` | Порт для прокси | 1443 |
| `--host` | Хост для прокси | 127.0.0.1 |

**Примеры:**
```cmd
:: Запуск с настройками по умолчанию
zapret-optimizer.exe start-proxy

:: Запуск на порту 8080
zapret-optimizer.exe start-proxy --port 8080

:: Запуск на всех интерфейсах
zapret-optimizer.exe start-proxy --host 0.0.0.0 --port 8080
```

---

### `stop-proxy`
Остановка tg-ws-proxy.

**Пример:**
```cmd
zapret-optimizer.exe stop-proxy
```

---

### `status-proxy`
Показать статус tg-ws-proxy.

**Выводит:**
- Статус (запущен/остановлен)
- Порт и хост
- Ссылку для подключения в Telegram
- Секрет (если настроен)

**Пример:**
```cmd
zapret-optimizer.exe status-proxy
```

---

### `configure-proxy`
Настройка параметров tg-ws-proxy.

**Опции:**
| Опция | Описание |
|-------|----------|
| `--port` | Установить порт |
| `--secret` | Установить кастомный секрет |

**Примеры:**
```cmd
:: Настройка порта
zapret-optimizer.exe configure-proxy --port 8080

:: Настройка секрета
zapret-optimizer.exe configure-proxy --secret mysecret123

:: Настройка порта и секрета
zapret-optimizer.exe configure-proxy --port 8080 --secret mysecret123
```

---

### `test-telegram`
Проверка подключения к Telegram через прокси.

**Тестирует:**
- Доступность порта прокси
- Корректность ответа прокси

**Пример:**
```cmd
zapret-optimizer.exe test-telegram
```

---

## 🔐 WARP (Cloudflare + AmneziaVPN)

### `warp-generate`
Генерация конфигурационного файла WARP для AmneziaVPN.

**Опции:**
| Опция | Описание | Варианты | По умолчанию |
|-------|----------|----------|--------------|
| `--method` | Метод генерации | `api`, `fallback` | `api` |

**Методы:**
- **`api`** — Регистрация через Cloudflare API (получение реальных ключей)
- **`fallback`** — Локальная генерация с известными endpoint'ами WARP

**Файлы:**
- `warp.conf` — конфигурация AmneziaVPN (AmneziaWG)
- `warp_state.json` — данные регистрации и ключи

**Примеры:**
```cmd
:: Генерация через API
zapret-optimizer.exe warp-generate --method api

:: Генерация fallback (если API недоступен)
zapret-optimizer.exe warp-generate --method fallback
```

**Использование:**
Сгенерированный `warp.conf` импортируйте в AmneziaVPN:
1. Откройте AmneziaVPN
2. Добавьте конфигурацию → Файл конфигурации → Выберите `warp.conf`
3. ⚠️ **ВАЖНО:** В настройках подключения включите **"Обфускацию WireGuard"**
4. Подключитесь — обфускация обходит DPI блокировки

---

## 📦 Управление зависимостями

### `deps-status`
Показать статус всех зависимостей.

**Проверяет:**
- `TgWsProxy_windows.exe` — Telegram proxy
- `zapret/` — папка с zapret

**Выводит:**
- [OK] — зависимость установлена
- [MISSING] — зависимость отсутствует

**Пример:**
```cmd
zapret-optimizer.exe deps-status
```

---

### `download-deps`
Загрузка отсутствующих зависимостей.

**Опции:**
| Опция | Описание |
|-------|----------|
| `--proxy-only` | Скачать только tg-ws-proxy |
| `--zapret-only` | Скачать только zapret |
| `--force` | Перезаписать существующие файлы |

**Что скачивается:**
- ✅ `TgWsProxy_windows.exe` — с GitHub releases
- ✅ `zapret/` — с GitHub (Flowseal/zapret-discord-youtube)

**Примеры:**
```cmd
:: Скачать все зависимости
zapret-optimizer.exe download-deps

:: Скачать только tg-ws-proxy
zapret-optimizer.exe download-deps --proxy-only

:: Скачать только zapret
zapret-optimizer.exe download-deps --zapret-only

:: Принудительно перезаписать
zapret-optimizer.exe download-deps --force
```

---

## 🛠️ Глобальные опции

Эти опции работают с любой командой:

| Опция | Описание | Пример |
|-------|----------|--------|
| `--base-dir` | Базовая директория для файлов | `--base-dir D:\zapret` |

**Пример:**
```cmd
zapret-optimizer.exe init --base-dir D:\zapret
zapret-optimizer.exe optimize --base-dir D:\zapret
```

---

## 📊 Типичные сценарии использования

### Сценарий 1: Полная настройка с нуля
```cmd
:: 1. Инициализация
zapret-optimizer.exe init

:: 2. Загрузка зависимостей
zapret-optimizer.exe download-deps

:: 3. Оптимизация (длительный процесс)
zapret-optimizer.exe optimize

:: 4. Запуск лучшей конфигурации
zapret-optimizer.exe run-best
```

### Сценарий 2: Использование Telegram Proxy
```cmd
:: 1. Установка прокси
zapret-optimizer.exe install-proxy

:: 2. Запуск прокси
zapret-optimizer.exe start-proxy

:: 3. Получение ссылки для подключения
zapret-optimizer.exe status-proxy

:: 4. Клик по ссылке в Telegram → Настройки → Данные и накопления → Прокси → Добавить прокси

:: 5. Проверка соединения
zapret-optimizer.exe test-telegram
```

### Сценарий 3: WARP + Zapret
```cmd
:: 1. Генерация WARP конфига
zapret-optimizer.exe warp-generate --method api

:: 2. Подключение WARP через AmneziaVPN (импорт warp.conf)

:: 3. Запуск оптимизации zapret
zapret-optimizer.exe optimize
zapret-optimizer.exe run-best
```

### Сценарий 4: Сравнение конфигураций
```cmd
:: После оптимизации смотрим список
zapret-optimizer.exe list

:: Сравниваем топ-2
zapret-optimizer.exe compare cycle-3/combo_general_fake_tls.bat cycle-2/mutant_general_5.bat
```

### Сценарий 5: Кастомные сайты для тестирования
```cmd
:: Создаем файл my_sites.txt:
:: Yandex = "https://ya.ru"
:: VK = "https://vk.com"
:: MySite = "https://example.com"

:: Запускаем оптимизацию с кастомным списком
zapret-optimizer.exe optimize --sites-file my_sites.txt
```

---

## ❗ Коды выхода

| Код | Значение |
|-----|----------|
| `0` | Успешное выполнение |
| `1` | Ошибка выполнения |
| `130` | Прервано пользователем (Ctrl+C) |

---

## 💡 Полезные советы

1. **Всегда начинайте с `init`** — это проверит ваше окружение
2. **Оптимизация занимает время** — типично 10-30 минут в зависимости от количества сайтов
3. **Используйте `list`** после оптимизации, чтобы увидеть все результаты
4. **WARP конфиг** можно использовать отдельно от zapret — они не конфликтуют
5. **Telegram Proxy** работает независимо от zapret и WARP

---

## 🔗 Ссылки

- [Основной README](./README.md)
- [Репозиторий zapret](https://github.com/flowseal/zapret-discord-youtube)
- [Репозиторий tg-ws-proxy](https://github.com/Flowseal/tg-ws-proxy)
