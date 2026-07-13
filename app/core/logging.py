import sys
import time
import logging
from loguru import logger
from fastapi import Request

# Define a clean, high-visibility log format
LOGGING_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

def setup_logging():
    """Overrides default framework loggers to pipe all messages through Loguru."""
    # Wipe out default log handlers for native python logging
    logging.getLogger().handlers = []
    
    # Configure Loguru output to standard streams
    logger.remove()
    logger.add(sys.stdout, format=LOGGING_FORMAT, level="INFO")
    
    # Core handler to catch native logging calls and re-route them
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            frame = logging.currentframe()
            depth = 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

    # Force Uvicorn loggers to use the Loguru routing handler
    for logger_name in ("uvicorn", "uvicorn.asgi", "uvicorn.error", "uvicorn.access"):
        mod_logger = logging.getLogger(logger_name)
        mod_logger.handlers = [InterceptHandler()]
        mod_logger.propagate = False

async def log_requests_middleware(request: Request, call_next):
    """Intercepts HTTP requests to measure execution time and status outcomes."""
    start_time = time.perf_counter()
    method = request.method
    path = request.url.path
    client_host = request.client.host if request.client else "unknown"
    
    logger.info(f"Incoming request: {method} {path} from {client_host}")
    
    try:
        response = await call_next(request)
        process_time = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"Completed request: {method} {path} - Status: {response.status_code} - Latency: {process_time:.2f}ms"
        )
        return response
        
    except Exception as e:
        process_time = (time.perf_counter() - start_time) * 1000
        logger.exception(
            f"Unhandled server error: {method} {path} - Error: {str(e)} - Latency: {process_time:.2f}ms"
        )
        raise e