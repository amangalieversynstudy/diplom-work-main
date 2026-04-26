import docker
from requests.exceptions import ReadTimeout

# ЗАЩИТА: Максимальный размер вывода в байтах (около 50 КБ)
MAX_OUTPUT_SIZE = 50 * 1024 

def execute_python_code(code: str, timeout: int = 5) -> dict:
    """
    Выполняет Python-код в полностью изолированном микро-контейнере.
    """
    try:
        # Подключаемся к Docker-демону
        client = docker.from_env()
    except Exception as e:
        return {"status": "error", "output": f"Docker недоступен: {str(e)}"}

    container = None
    try:
        # Запускаем код в изолированном alpine-контейнере
        container = client.containers.run(
            image="python:3.11-alpine",
            command=["python", "-c", code],
            detach=True,           
            mem_limit="128m",      
            network_mode="none",   # Отключаем интернет
        )

        # Ждем завершения с жестким таймаутом
        result = container.wait(timeout=timeout)
        
        # Получаем логи в виде сырых байтов
        raw_logs = container.logs(stdout=True, stderr=True)
        
        # ЗАЩИТА ОТ ПЕРЕПОЛНЕНИЯ ПАМЯТИ
        if len(raw_logs) > MAX_OUTPUT_SIZE:
            raw_logs = raw_logs[:MAX_OUTPUT_SIZE] + b"\n\n... [ВЫВОД ОБРЕЗАН: Слишком много данных] ..."
            
        # Декодируем безопасно, игнорируя битые символы
        logs = raw_logs.decode("utf-8", errors="replace")
        
        if result.get("StatusCode", 0) == 0:
            return {"status": "success", "output": logs}
        else:
            return {"status": "error", "output": logs}

    except ReadTimeout:
        if container:
            container.kill()
        return {"status": "error", "output": f"Timeout: Код выполнялся дольше {timeout} секунд и был прерван."}
    except Exception as e:
        return {"status": "error", "output": f"Ошибка песочницы: {str(e)}"}
    finally:
        if container:
            try:
                container.remove(force=True)
            except:
                pass