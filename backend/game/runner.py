import docker
from requests.exceptions import ReadTimeout

def execute_python_code(code: str, timeout: int = 5) -> dict:
    """
    Выполняет Python-код в полностью изолированном микро-контейнере.
    """
    try:
        # Явно указываем путь к сокету
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
        logs = container.logs(stdout=True, stderr=True).decode("utf-8")
        
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