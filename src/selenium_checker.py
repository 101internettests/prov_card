from typing import List, Tuple
import logging
import re

from playwright.sync_api import sync_playwright, Page, Locator


PROVIDER_CARD_XPATH = "xpath=//div[@data-sentry-component='ProviderCardFull']"
TARIFF_BUTTONS_XPATH = "xpath=//div[contains(@class,'TariffCard')]//div[contains(@class,'TextPriceButtonTariff_price-button')]"


class PlaywrightDriver:
    def __init__(self, p, browser, context, page: Page):
        self._p = p
        self._browser = browser
        self._context = context
        self.page = page

    def quit(self) -> None:
        try:
            self._context.close()
        except Exception:
            pass
        try:
            self._browser.close()
        except Exception:
            pass
        try:
            self._p.stop()
        except Exception:
            pass


def build_driver(headless: bool, wait_seconds: int, page_load_strategy: str = "eager", disable_images: bool = True, disable_css: bool = True, disable_fonts: bool = True) -> PlaywrightDriver:
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
    )

    page = context.new_page()
    page.set_default_timeout(max(1, wait_seconds) * 1000)
    return PlaywrightDriver(p=p, browser=browser, context=context, page=page)


def _normalize_text(value: str) -> str:
    lowered = (value or "").replace("\xa0", " ").lower()
    return re.sub(r"\s+", " ", lowered).strip()


def _has_span_with_text(card: Locator, text: str) -> bool:
    xp = f"xpath=.//span[text()='{text}']"
    return card.locator(xp).count() > 0


def _extract_provider_name(card: Locator) -> str:
    name_locator = card.locator(
        "xpath=.//div[contains(@class,'ProviderCardHeader_provider-block')]//p[contains(@class,'ProviderCardHeader')]"
    )
    c = name_locator.count()
    for i in range(c):
        txt = (name_locator.nth(i).text_content(timeout=0) or "").strip()
        if txt and re.search(r"[A-Za-zА-Яа-я]", txt):
            return txt

    text = (card.text_content(timeout=0) or "").strip()
    if text:
        for line in text.splitlines():
            candidate = line.strip()
            if candidate and re.search(r"[A-Za-zА-Яа-я]", candidate):
                return candidate[:80]
    return "Неизвестный провайдер"


def check_url_with_driver(driver, url: str, wait_seconds: int = 15) -> Tuple[List[str], int, int]:
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
    page: Page = driver.page
    page.set_default_timeout(max(1, wait_seconds) * 1000)
    page.goto(url, wait_until="domcontentloaded", timeout=max(1, wait_seconds) * 1000)

    cards = page.locator(PROVIDER_CARD_XPATH)
    total_cards = cards.count()
    logging.info("Найдено карточек провайдеров: %s", total_cards)
    if total_cards == 0:
        # Ничего не найдено быстро — не ждём, продолжаем без зависаний
        return [], 0, 0

    # Сравнение количества заголовков с текстами и числа кнопок тарифов
    fee_headers = page.locator("xpath=//div[@data-sentry-component='ProviderCardFull']//span[text()='Абонентская плата']").count()
    speed_headers = page.locator("xpath=//div[@data-sentry-component='ProviderCardFull']//span[text()='Скорость']").count()
    connect_headers = page.locator("xpath=//div[@data-sentry-component='ProviderCardFull']//span[text()='Подключение']").count()
    headers_count = min(fee_headers, speed_headers, connect_headers)
    buttons_count = page.locator(TARIFF_BUTTONS_XPATH).count()
    logging.info("Кнопок тарифов: %d, заголовков (мин по трем): %d", buttons_count, headers_count)

    target_cards = cards
    logging.info("Проверяем все карточки: %d", total_cards)

    target_count = target_cards.count()
    for i in range(target_count):
        card = target_cards.nth(i)
        has_speed = _has_span_with_text(card, "Скорость")
        has_connect = _has_span_with_text(card, "Подключение")
        if not (has_speed and has_connect):
            continue
        checked_cards += 1

        has_fee = _has_span_with_text(card, "Абонентская плата")
        if not has_fee:
            name = _extract_provider_name(card)
            if not name:
                name = f"Провайдер #{i + 1}"
            missing.append(name)

    return missing, total_cards, checked_cards


def check_url_for_missing_fee(url: str, headless: bool, wait_seconds: int = 15) -> Tuple[List[str], int, int]:
    driver = build_driver(headless=headless, wait_seconds=wait_seconds)
    try:
        return check_url_with_driver(driver, url, wait_seconds)
    finally:
        driver.quit()
