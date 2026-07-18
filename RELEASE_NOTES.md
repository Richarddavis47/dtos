# DTOS v0.8.1

- Moved Sleeper synchronization, caching, and freshness checks into `services/sleeper.py`.
- Centralized runtime settings in `config.py`.
- Reduced `main.py` to a stable Render ASGI entry point.
- Preserved every existing route and page in `dtos_app.py`.
