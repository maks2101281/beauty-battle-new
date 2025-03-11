import threading
import time
import requests
import logging
import os
import random
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class KeepAliveService:
    """Улучшенный сервис keep-alive для предотвращения засыпания бота на Render"""
    
    def __init__(self):
        self.render_url = os.environ.get('RENDER_EXTERNAL_URL')
        self.is_running = False
        self.stats = {
            'total_pings': 0,
            'successful_pings': 0,
            'failed_pings': 0,
            'last_successful_ping': None,
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'errors': []
        }
        self.thread = None
        self.ping_urls = []
        
    def setup(self):
        """Настраивает параметры сервиса keep-alive"""
        if not self.render_url:
            logger.warning("RENDER_EXTERNAL_URL не настроен. Keep-alive не будет работать корректно.")
            # Используем резервный URL, если RENDER_EXTERNAL_URL не настроен
            self.render_url = "https://your-app.onrender.com"
        
        # Проверяем, что URL заканчивается на '/'
        if not self.render_url.endswith('/'):
            self.render_url += '/'
        
        # Настраиваем несколько URL для пинга с разными путями
        self.ping_urls = [
            f"{self.render_url}ping",  # Основной ping endpoint
            f"{self.render_url}",      # Корневой маршрут
            # Можно добавить дополнительные пути, если они есть в вашем приложении
        ]
        
        logger.info(f"Keep-alive настроен для URL: {self.render_url}")
        return self
    
    def _do_ping(self, url):
        """Выполняет один ping-запрос и возвращает результат"""
        try:
            # Добавляем случайный параметр, чтобы избежать кэширования
            random_param = f"?nocache={random.randint(10000, 99999)}"
            full_url = f"{url}{random_param}"
            
            # Отправляем запрос с таймаутом
            response = requests.get(full_url, timeout=10)
            
            # Проверяем статус ответа
            if response.status_code == 200:
                return True, None
            else:
                return False, f"Неожиданный статус: {response.status_code}"
                
        except requests.RequestException as e:
            return False, str(e)
        except Exception as e:
            return False, f"Неизвестная ошибка: {str(e)}"
    
    def _keep_alive_task(self):
        """Основная функция, выполняющая периодические пинги"""
        logger.info("Keep-alive поток запущен")
        
        while self.is_running:
            self.stats['total_pings'] += 1
            ping_success = False
            
            # Пробуем все URL из списка, пока один не сработает
            for url in self.ping_urls:
                success, error = self._do_ping(url)
                
                if success:
                    ping_success = True
                    self.stats['successful_pings'] += 1
                    self.stats['last_successful_ping'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Логируем успешные пинги, но не каждый раз
                    if self.stats['successful_pings'] % 6 == 0:  # примерно раз в час при 10-минутном интервале
                        uptime = datetime.now() - datetime.strptime(self.stats['start_time'], '%Y-%m-%d %H:%M:%S')
                        hours, remainder = divmod(uptime.seconds, 3600)
                        minutes, _ = divmod(remainder, 60)
                        logger.info(
                            f"Keep-alive активен {uptime.days} дней, {hours} часов, {minutes} минут. "
                            f"Успешно: {self.stats['successful_pings']}/{self.stats['total_pings']} пингов."
                        )
                    
                    # Если один из URL работает, прекращаем проверку остальных
                    break
                else:
                    # Записываем информацию об ошибке
                    error_info = {
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'url': url,
                        'error': error
                    }
                    
                    # Ограничиваем количество сохраняемых ошибок
                    self.stats['errors'].append(error_info)
                    if len(self.stats['errors']) > 10:
                        self.stats['errors'] = self.stats['errors'][-10:]
            
            # Если ни один URL не ответил, увеличиваем счетчик ошибок
            if not ping_success:
                self.stats['failed_pings'] += 1
                logger.warning(f"Keep-alive: все пинги провалились. Всего ошибок: {self.stats['failed_pings']}")
            
            # Рандомизированная задержка между запросами (от 8 до 12 минут)
            # Это поможет избежать паттернов, которые могут привести к засыпанию
            sleep_time = 600 + random.randint(-120, 120)
            time.sleep(sleep_time)
    
    def start(self):
        """Запускает keep-alive сервис в отдельном потоке"""
        if self.is_running:
            logger.warning("Keep-alive уже запущен")
            return self
        
        # Настраиваем параметры, если еще не сделано
        if not self.ping_urls:
            self.setup()
        
        self.is_running = True
        self.thread = threading.Thread(target=self._keep_alive_task, daemon=True)
        self.thread.start()
        logger.info("Keep-alive сервис запущен")
        return self
    
    def stop(self):
        """Останавливает keep-alive сервис"""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            # Ждем завершения потока, но не больше 5 секунд
            self.thread.join(timeout=5)
        logger.info("Keep-alive сервис остановлен")
        return self
    
    def get_status(self):
        """Возвращает текущий статус сервиса keep-alive"""
        uptime = datetime.now() - datetime.strptime(self.stats['start_time'], '%Y-%m-%d %H:%M:%S')
        return {
            'is_running': self.is_running,
            'uptime': str(uptime),
            'stats': self.stats,
            'ping_urls': self.ping_urls
        }

def start_keep_alive_thread():
    """
    Создает и запускает экземпляр сервиса keep-alive.
    Возвращает созданный экземпляр.
    """
    service = KeepAliveService().setup().start()
    return service

# Для тестирования, если файл запущен напрямую
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    service = start_keep_alive_thread()
    logger.info("Keep-alive поток запущен для тестирования.")
    try:
        # Держим основной поток открытым для тестирования
        while True:
            time.sleep(60)
            status = service.get_status()
            logger.info(f"Статус: {json.dumps(status, indent=2, ensure_ascii=False)}")
    except KeyboardInterrupt:
        logger.info("Тестирование keep-alive завершено.")
        service.stop() 