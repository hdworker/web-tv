# Frontend

Web-интерфейс платформы: расписание, таблица видео, управление загрузкой,
логи и просмотр транскриптов.

Стек: React 19, Vite, Ant Design 6, axios.

## Запуск

```bash
npm install
npm run dev
```

Интерфейс откроется на `http://localhost:5173`. Запросы `/api` проксируются на
backend `http://localhost:8000` (см. `vite.config.js`), поэтому backend должен
быть запущен заранее.

## Сборка и проверка

```bash
npm run build
npm run lint
npm run preview
```

`dist/` и `node_modules/` не коммитятся.
