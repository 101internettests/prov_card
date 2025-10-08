from typing import List, Tuple
import logging
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


PROVIDER_CARD_XPATH = "//div[@data-sentry-component='ProviderCardFull']"
BUTTON_IN_CARD_XPATH = ".//div[@data-sentry-element='TextPriceButtonTariff']"


def build_driver(headless: bool, wait_seconds: int, page_load_strategy: str = "eager", disable_images: bool = True, disable_css: bool = True, disable_fonts: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.page_load_strategy = page_load_strategy

    prefs = {"profile.managed_default_content_settings.images": 2 if disable_images else 1}
    options.add_experimental_option("prefs", prefs)

    # DevTools команды для отключения CSS/шрифтов не стандартны, но можно снизить трафик:
    # В headless режиме эффекты ограничены, однако отключение картинок уже даёт выигрыш.

    driver = webdriver.Chrome(options=options)
    # Даем больше времени навигации в headless/Jenkins среде
    driver.set_page_load_timeout(max(60, wait_seconds * 4))
    driver.implicitly_wait(wait_seconds)
    return driver


def _normalize_text(value: str) -> str:
    lowered = (value or "").replace("\xa0", " ").lower()
    return re.sub(r"\s+", " ", lowered).strip()


def _has_span_with_text(card, text: str) -> bool:
    xp = f".//span[normalize-space(text())='{text}']"
    return len(card.find_elements(By.XPATH, xp)) > 0


def _extract_provider_name(card) -> str:
    for xp in [
        ".//*[@role='heading']",
        ".//h1",
        ".//h2",
        ".//h3",
        ".//h4",
        ".//h5",
    ]:
        elems = card.find_elements(By.XPATH, xp)
        for el in elems:
            name = (el.text or "").strip()
            if name:
                return name
    text = (card.text or "").strip()
    if text:
        return text.splitlines()[0][:80]
    return "Неизвестный провайдер"


def check_url_with_driver(driver: webdriver.Chrome, url: str, wait_seconds: int = 15) -> Tuple[List[str], int, int]:
    """
    Проверка страницы, используя уже созданный драйвер.
    Возвращает (провайдеры_без_абонплаты, всего_карточек, проверено_карточек).
    Логика выбора карточек:
    - Если карточек с кнопкой TextPriceButtonTariff меньше всех карточек — проверяем только их; иначе все.
    - Карточка проверяется, если содержит «Скорость» и «Подключение». В такой карточке ищем «Абонентская плата».
    """
    missing: List[str] = []
    total_cards = 0
    checked_cards = 0

    logging.info("Открываю URL: %s", url)
    try:
        driver.get(url)
    except TimeoutException:
        logging.warning("Таймаут загрузки при переходе на %s, повторная попытка", url)
        try:
            driver.get(url)
        except TimeoutException:
            logging.warning("Повторный таймаут загрузки %s, продолжаем с уже загруженным контентом", url)

    WebDriverWait(driver, wait_seconds).until(
        EC.presence_of_element_located((By.XPATH, PROVIDER_CARD_XPATH))
    )

    cards = driver.find_elements(By.XPATH, PROVIDER_CARD_XPATH)
    total_cards = len(cards)
    logging.info("Найдено карточек провайдеров: %s", total_cards)

    cards_with_button = [c for c in cards if len(c.find_elements(By.XPATH, BUTTON_IN_CARD_XPATH)) > 0]
    num_with_button = len(cards_with_button)
    if 0 < num_with_button < total_cards:
        target_cards = cards_with_button
        logging.info("Ориентируемся на карточки с кнопкой: %d из %d", len(target_cards), total_cards)
    else:
        target_cards = cards
        if num_with_button == 0:
            logging.info("Кнопок не найдено, проверяем все карточки: %d", len(target_cards))
        else:
            logging.info("Кнопок не меньше карточек, проверяем все карточки: %d", len(target_cards))

    for idx, card in enumerate(target_cards, start=1):
        has_speed = _has_span_with_text(card, "Скорость")
        has_connect = _has_span_with_text(card, "Подключение")
        if not (has_speed and has_connect):
            continue
        checked_cards += 1

        has_fee = _has_span_with_text(card, "Абонентская плата")
        if not has_fee:
            name = _extract_provider_name(card)
            if not name:
                name = f"Провайдер #{idx}"
            missing.append(name)

    return missing, total_cards, checked_cards


def check_url_for_missing_fee(url: str, headless: bool, wait_seconds: int = 15) -> Tuple[List[str], int, int]:
    driver = build_driver(headless=headless, wait_seconds=wait_seconds)
    try:
        return check_url_with_driver(driver, url, wait_seconds)
    finally:
        driver.quit()
