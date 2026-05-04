# ⚡ Zapret Config Optimizer

> Автоматический подбор оптимальных конфигураций [zapret](https://github.com/flowseal/zapret-discord-youtube) для обхода блокировок DPI.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Windows](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://microsoft.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 🚀 Быстрый старт

```cmd
:: 1. Скачайте zapret-optimizer.exe и положите рядом с папкой zapret
:: 2. Инициализация
zapret-optimizer.exe init

:: 3. Запуск оптимизации (~10-30 минут)
zapret-optimizer.exe optimize

:: 4. Запуск лучшей конфигурации
zapret-optimizer.exe run-best
```

---

## 📦 Установка

### Вариант 1: Готовый EXE (рекомендуется)

1. Скачайте `zapret-optimizer.exe` из [Releases](../../releases)
2. Поместите файл рядом с папкой `zapret` (или рядом с `zapret-win-bundle`)
3. Готово!

### Вариант 2: Из исходников

```cmd
git clone https://github.com/yourusername/zapret-optimizer.git
cd zapret-optimizer
pip install -r requirements.txt
python main.py init
```

### Требования

- **Windows 10/11** (с правами администратора)
- **[zapret](https://github.com/flowseal/zapret-discord-youtube)** — должна быть папка `zapret/` рядом с программой
- **curl** — для тестирования доступности сайтов (обычно предустановлен)

---

## ✨ Что делает эта программа?

**Zapret** — мощный инструмент для обхода DPI-блокировок, но подбор оптимальных параметров требует экспериментов. Этот оптимизатор автоматизирует процесс:

### Алгоритм оптимизации (3 цикла)

```
┌─────────────────────────────────────────────────────────────┐
│  ЦИКЛ 1: Базовое тестирование                               │
│  └─ Тестируем все стандартные стратегии zapret              │
│  └─ Сохраняем результаты в results.json                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  ЦИКЛ 2: Мутация лучших                                     │
│  └─ Берем топ-3 стратегии из цикла 1                        │
│  └─ Создаем варианты с измененными параметрами              │
│  └─ Тестируем мутации                                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  ЦИКЛ 3: Комбинирование                                     │
│  └─ Объединяем лучшие стратегии из разных циклов            │
│  └─ Тестируем гибридные конфигурации                        │
│  └─ Выбираем абсолютного чемпиона                           │
└─────────────────────────────────────────────────────────────┘
```

### Особенности

- ✅ **Автоматический подбор** — не нужно вручную перебирать параметры
- ✅ **Мутации** — ищет оптимальные значения TTL, порты, флаги
- ✅ **Комбинирование** — смешивает лучшие стратегии
- ✅ **Рейтинговая система** — объективная оценка по проценту доступных сайтов
- ✅ **Сравнение** — наглядное сравнение разных конфигураций

---

## 📚 Доступные команды

Программа предоставляет **18 команд** для полного цикла работы:

### 🎯 Основные
| Команда | Описание |
|---------|----------|
| `init` | Проверка окружения и инициализация |
| `optimize` | Запуск 3-цикловой оптимизации |
| `run-best` | Запуск лучшей конфигурации |
| `status` | Статус оптимизации |
| `list` | Список всех конфигураций по рейтингу |
| `compare` | Сравнение двух конфигураций |

### 🌐 Telegram Proxy
| Команда | Описание |
|---------|----------|
| `install-proxy` | Установка tg-ws-proxy |
| `start-proxy` | Запуск прокси |
| `stop-proxy` | Остановка прокси |
| `status-proxy` | Статус прокси |
| `configure-proxy` | Настройка параметров |
| `test-telegram` | Тест соединения |

### 🔐 WARP (AmneziaVPN)
| Команда | Описание |
|---------|----------|
| `warp-generate` | Генерация WARP конфига для AmneziaVPN |

### 🚀 Автозапуск
| Команда | Описание |
|---------|----------|
| `install-service` | Установить автозапуск лучшего конфига |
| `uninstall-service` | Удалить автозапуск |
| `service-status` | Проверить статус автозапуска |

### 📦 Зависимости
| Команда | Описание |
|---------|----------|
| `deps-status` | Статус зависимостей |
| `download-deps` | Загрузка зависимостей |

---

## 📖 Документация

**Подробный справочник всех команд с примерами:**

👉 **[COMMANDS.md](./COMMANDS.md)** — полная документация по всем командам, параметрам и сценариям использования

---

## 🎯 Примеры использования

### Пример 1: Оптимизация и запуск

```cmd
:: Инициализация
zapret-optimizer.exe init

:: Оптимизация (займет 10-30 минут)
:: Автоматически использует домены из zapret/lists/list-general.txt
zapret-optimizer.exe optimize

:: Или с кастомным списком сайтов:
zapret-optimizer.exe optimize --sites-file my_sites.txt

:: Смотрим результаты (с ping и скоростью скачивания)
zapret-optimizer.exe list

:: Запускаем лучшую
zapret-optimizer.exe run-best

:: Устанавливаем автозапуск (будет стартовать при входе в Windows)
zapret-optimizer.exe install-service

:: Проверяем статус автозапуска
zapret-optimizer.exe service-status
```

### Пример 2: Telegram Proxy

```cmd
:: Установка и запуск
zapret-optimizer.exe install-proxy
zapret-optimizer.exe start-proxy --port 8080

:: Получаем ссылку для подключения
zapret-optimizer.exe status-proxy
:: tg://proxy?server=127.0.0.1&port=8080&secret=...

:: Кликаем ссылку в Telegram → настраиваем прокси
:: Проверяем соединение
zapret-optimizer.exe test-telegram
```

### Пример 3: WARP (Cloudflare + AmneziaVPN)

```cmd
:: Генерируем конфиг для AmneziaVPN
zapret-optimizer.exe warp-generate --method api

:: Файл warp.conf создается в текущей папке
:: Импортируем в AmneziaVPN:
:: 1. Добавить конфигурацию → Файл конфигурации → выбрать warp.conf
:: 2. Включить "Обфускацию WireGuard" в настройках подключения!

:: Для другого устройства — сгенерировать новый конфиг:
zapret-optimizer.exe warp-generate --method api --force
```

### Пример 4: Сравнение конфигураций

```cmd
:: Посмотреть топ
zapret-optimizer.exe list

:: Сравнить #1 и #2
zapret-optimizer.exe compare cycle-3/combo_general_fake_tls.bat cycle-2/mutant_general_5.bat
```

---

## 🔧 Как это работает?

### Структура конфигураций

```
cycle-1/              # Первый цикл — базовые стратегии
  ├── general.bat
  ├── fake_tls.bat
  └── ...

cycle-2/              # Второй цикл — мутации лучших
  ├── mutant_general_1.bat
  ├── mutant_general_2.bat
  └── ...

cycle-3/              # Третий цикл — комбинации
  ├── combo_general_fake_tls.bat
  └── ...

results.json          # Рейтинг всех конфигураций
```

### Система рейтинга

Каждая конфигурация оценивается по формуле:

```
Score = (Доступных сайтов / Всего сайтов) × 100%
```

Сайты для тестирования настраиваются в `sites.txt` (по умолчанию: YouTube, Discord, и др.)

---

## ⚠️ Важные замечания

1. **Требуются права администратора** — zapret модифицирует системный фильтр WinDivert
2. **Закройте другие VPN** — они могут конфликтовать с zapret
3. **Оптимизация занимает время** — 10-30 минут в зависимости от количества сайтов
4. **Первый запуск `optimize` может быть медленным** — скачиваются и проверяются зависимости

---

## 🧩 Автоматическая загрузка зависимостей

```cmd
:: Проверить что установлено
zapret-optimizer.exe deps-status

:: Скачать всё автоматически
zapret-optimizer.exe download-deps

:: Только tg-ws-proxy
zapret-optimizer.exe download-deps --proxy-only

:: Только zapret
zapret-optimizer.exe download-deps --zapret-only
```

**Что скачивается:**
- ✅ `TgWsProxy_windows.exe` — Telegram proxy
- ✅ `zapret/` — файлы zapret из репозитория Flowseal

**Что НЕ скачивается (требуется вручную):**
- ⚠️ Сам `zapret-optimizer.exe` — скачайте из Releases

---

## 🛠️ Устранение неполадок

### "zapret not found"

Поместите папку `zapret` рядом с `zapret-optimizer.exe`:

```
D:\Zapret\
  ├── zapret-optimizer.exe
  └── zapret\
       ├── winws.exe
       └── ...
```

### "Admin rights required"

Запустите от имени администратора:
- Правый клик → "Запуск от имени администратора"

### Оптимизация работает медленно

Это нормально — программа тестирует множество конфигураций:
- Цикл 1: ~10-20 конфигураций
- Цикл 2: ~30 мутаций
- Цикл 3: ~10 комбинаций

Итого: ~50+ тестов с паузами между ними.

### Где результаты?

```
results.json          # JSON с рейтингом
best_config.txt       # Путь к лучшей конфигурации
cycle-*/              # Сгенерированные .bat файлы
```

---

## 🤝 Вклад в проект

Приветствуются:
- 🐛 Bug reports
- 💡 Feature requests
- 📖 Документация
- 🔧 Pull requests

---

## 📄 Лицензия

MIT License — свободное использование, модификация и распространение.

---

## 🔗 Полезные ссылки

- **[📚 Полный справочник команд](./COMMANDS.md)**
- [zapret](https://github.com/flowseal/zapret-discord-youtube)
- [tg-ws-proxy](https://github.com/Flowseal/tg-ws-proxy)

---

<p align="center">
  Сделано с ❤️ для свободного интернета
</p>