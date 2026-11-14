import logging
from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from config import config
from contextlib import asynccontextmanager

from api.schedule import router as schedule_router
from api.main import router as videos_router

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
    force=True
)
logger = logging.getLogger(__name__)

# @app.on_event("startup")
# async def startup_event():
#     logger.info("=" * 50)
#     logger.info(f"Backend запущен в {'DEV' if config.dev else 'PROD'} режиме")
#     logger.info(f"Логирование запросов: {'включено' if config.log_requests else 'выключено'}")
#     logger.info(f"Логирование ответов: {'включено' if config.log_responses else 'выключено'}")
#     logger.info("=" * 50)
# Refactoring for lifespan patter
@asynccontextmanager
async def lifespan(app: FastAPI):
    # стартап код
    logger.info("=" * 50)
    logger.info(f"Backend запущен в {'DEV' if config.dev else 'PROD'} режиме")
    logger.info(f"Логирование запросов: {'включено' if config.log_requests else 'выключено'}")
    logger.info(f"Логирование ответов: {'включено' if config.log_responses else 'выключено'}")
    logger.info("=" * 50)
    yield
    # shutdown код
    logger.info("Backend остановлен")

app = FastAPI(
    title="UN Video Platform API",
    description="API для работы с видео ООН: получение расписания, загрузка, транскрипции",
    version="1.0.0",
    lifespan=lifespan
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    logger.info("=" * 60)
    logger.info(f"[REQUEST] {request.method} {request.url.path}")
    logger.info(f"[CLIENT] IP: {client_ip}, UA: {user_agent}")
    
    if request.query_params:
        logger.info(f"[QUERY] {dict(request.query_params)}")
    
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.body()
            if body:
                try:
                    body_str = body.decode("utf-8")
                    if len(body_str) > 200:
                        body_str = body_str[:200] + "..."
                    logger.info(f"[BODY] {body_str}")
                except:
                    logger.info(f"[BODY] <binary data, {len(body)} bytes>")
        except:
            pass
    
    response = await call_next(request)
    
    logger.info(f"[RESPONSE] {request.method} {request.url.path} -> {response.status_code}")
    logger.info("=" * 60)
    
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(schedule_router)
app.include_router(videos_router)


@app.get("/")
def root(response: Response):
    html = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>UN Video Platform API</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; line-height: 1.6; }
            h1 { color: #2563eb; border-bottom: 2px solid #2563eb; padding-bottom: 10px; }
            h2 { color: #1e40af; margin-top: 30px; }
            .endpoint { background: #f8fafc; border-radius: 8px; padding: 15px; margin: 10px 0; border-left: 4px solid #2563eb; }
            .method { display: inline-block; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-right: 10px; }
            .get { background: #22c55e; color: white; }
            .post { background: #3b82f6; color: white; }
            code { background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-size: 14px; }
            .url { color: #7c3aed; font-weight: 500; }
            .description { color: #64748b; margin-top: 5px; }
        </style>
    </head>
    <body>
        <h1>📺 UN Video Platform API</h1>
        <p>Версия: <strong>1.0.0</strong></p>
        
        <h2>📅 Расписание</h2>
        <div class="endpoint">
            <span class="method get">GET</span>
            <code class="url">/api/schedule/{date}</code>
            <p class="description">Получить видео за конкретную дату (формат: YYYY-MM-DD)</p>
            <p><strong>Пример:</strong> <code>/api/schedule/2026-02-26</code></p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code class="url">/api/schedule?start_date=<date>&end_date=<date></code>
            <p class="description">Получить видео за период</p>
            <p><strong>Пример:</strong> <code>/api/schedule?start_date=2026-02-24&end_date=2026-02-28</code></p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <code class="url">/api/schedule/save</code>
            <p class="description">Сохранить расписание в базу данных</p>
            <p><strong>Пример:</strong> <code>/api/schedule/save?start_date=2026-02-24&end_date=2026-02-26</code></p>
        </div>
        
        <h2>🎬 Видео</h2>
        <div class="endpoint">
            <span class="method get">GET</span>
            <code class="url">/api/videos</code>
            <p class="description">Список всех видео в базе</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code class="url">/api/videos/{id}</code>
            <p class="description">Получить видео по ID</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <code class="url">/api/videos</code>
            <p class="description">Добавить новое видео</p>
        </div>
        
        <h2>📋 OpenAPI документация</h2>
        <p><a href="/docs">/docs</a> - Swagger UI</p>
        <p><a href="/redoc">/redoc</a> - ReDoc</p>
    </body>
    </html>
    """
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return html


if __name__ == "__main__":
    import socket
    import uvicorn
    
    def find_free_port(start_port=8000, max_attempts=10):
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue
        return start_port
    
    port = find_free_port()
    host = "127.0.0.1"
    
    print("\n" + "=" * 50)
    print("UN Video Platform API запущен:")
    print(f"  http://localhost:{port}")
    print(f"  http://127.0.0.1:{port}")
    print(f"  http://<ваш-ip>:{port}")
    print("=" * 50)
    print("\nЭндпоинты:")
    print(f"  GET /api/schedule/{{date}}")
    print(f"  GET /api/schedule?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD")
    print(f"  GET /api/videos")
    print(f"  POST /api/schedule/save?start_date=...&end_date=...")
    print("=" * 50 + "\n")
    
    uvicorn.run(app, host=host, port=port, log_config=None)
