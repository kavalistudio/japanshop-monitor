# JapanShop Cloud Monitor

Это облачный сторож для JapanShop LT.

## Что он делает

- Работает в GitHub Actions, поэтому ваш компьютер может быть выключен.
- Каждые 5 минут напрямую запрашивает Hostinger eCommerce API магазина.
- Не использует Google и HTML-витрину.
- Сравнивает стабильные `prod_<ULID>` ID.
- Стартовая контрольная точка уже выставлена на:
  `prod_01M0J3BB8W341TW3RQEQ4NFP2D` — Vintage Akabeko.
- При появлении ID новее контрольного отправляет push через ntfy.
- После успешного уведомления сам обновляет `state.json`, чтобы не дублировать сообщение.
- Если API временно не отвечает, ничего не ломает и пробует снова на следующем запуске.

## Что понадобится

1. Бесплатный аккаунт GitHub.
2. Бесплатное приложение ntfy на телефоне **или** подписка через веб-интерфейс ntfy.
3. Один секретный случайный topic, например `japanshop-7f3c9a1e...`.

Важно: topic в ntfy фактически работает как пароль. Делайте его длинным и непредсказуемым.

## Установка

### 1. Создайте новый PRIVATE репозиторий GitHub

Например: `japanshop-monitor`.

### 2. Загрузите в корень репозитория содержимое этой папки

Должны получиться:
- `monitor.py`
- `state.json`
- `.github/workflows/japanshop.yml`

### 3. Создайте ntfy topic

Придумайте длинное случайное имя. Подпишитесь на него в приложении ntfy или в веб-интерфейсе ntfy.

### 4. Добавьте topic как GitHub Secret

В репозитории:
`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Name:
`NTFY_TOPIC`

Value:
ваш секретный topic.

### 5. Разрешите GitHub Actions записывать изменения

В репозитории:
`Settings` → `Actions` → `General` → `Workflow permissions`

Выберите:
`Read and write permissions`

Сохраните.

### 6. Запустите тест вручную

`Actions` → `JapanShop API monitor` → `Run workflow`

Если новых ID нет, уведомления не будет — это нормально.

## Как проверить push отдельно

Откройте в браузере:
`https://ntfy.sh/ВАШ_TOPIC`

Или используйте приложение ntfy и подпишитесь на тот же topic.

## Частота

GitHub разрешает scheduled workflows с минимальным интервалом 5 минут. Фактический запуск иногда может немного задерживаться из-за очереди GitHub Actions.

## Остановка

В `.github/workflows/japanshop.yml` можно удалить/закомментировать блок `schedule`, либо отключить Actions для репозитория.
