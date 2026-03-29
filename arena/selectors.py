# ============================================================================
# IIStudio — CSS/XPath селекторы для arena.ai (Playwright)
# ============================================================================

from __future__ import annotations

# ── Аутентификация ────────────────────────────────────────────────────────────

LOGIN_EMAIL_INPUT     = 'input[type="email"], input[name="email"], input[placeholder*="email" i]'
LOGIN_PASSWORD_INPUT  = 'input[type="password"], input[name="password"]'
LOGIN_SUBMIT_BUTTON   = 'button[type="submit"], button:has-text("Sign in"), button:has-text("Log in"), button:has-text("Continue")'
LOGIN_ERROR_MSG       = '.error, [class*="error"], [class*="alert"], [role="alert"]'
GOOGLE_LOGIN_BUTTON   = 'button:has-text("Google"), [aria-label*="Google"]'

# ── Навигация ─────────────────────────────────────────────────────────────────

NAV_TEXT_TAB    = 'button:has-text("Text"), a:has-text("Text"), [data-mode="text"]'
NAV_IMAGES_TAB  = 'button:has-text("Image"), a:has-text("Image"), [data-mode="images"]'
NAV_VIDEO_TAB   = 'button:has-text("Video"), a:has-text("Video"), [data-mode="video"]'
NAV_CODING_TAB  = 'button:has-text("Code"), a:has-text("Code"), [data-mode="coding"]'

MODE_TAB_MAP = {
    "text":   NAV_TEXT_TAB,
    "images": NAV_IMAGES_TAB,
    "video":  NAV_VIDEO_TAB,
    "coding": NAV_CODING_TAB,
}

# ── Выбор модели ──────────────────────────────────────────────────────────────

MODEL_SELECTOR_BUTTON   = '[class*="model-selector"], button[class*="model"], [aria-label*="model" i], [class*="ModelSelector"], button[class*="ModelSelect"], [data-testid*="model"]'
MODEL_DROPDOWN          = '[role="listbox"], [class*="dropdown"], [class*="model-list"], [class*="ModelList"]'
MODEL_OPTION            = '[role="option"], [class*="model-option"], [class*="ModelOption"]'
MODEL_SEARCH_INPUT      = 'input[placeholder*="search" i], input[placeholder*="model" i]'
MODEL_SELECTED_LABEL    = '[class*="model-name"], [class*="selected-model"], [class*="ModelName"]'

# ── Чат ──────────────────────────────────────────────────────────────────────

CHAT_INPUT              = 'textarea[placeholder], textarea[class*="input"], div[contenteditable="true"][class*="editor"], [class*="chat-input"] textarea, [class*="ChatInput"] textarea'
CHAT_SEND_BUTTON        = 'button[type="submit"]:not([disabled]), button[aria-label*="send" i], button[class*="send"], button:has-text("Send")'
CHAT_RESPONSE_CONTAINER = '[class*="bg-surface-raised"], [class*="message"], [class*="assistant"], [data-role="assistant"]'
CHAT_RESPONSE_TEXT      = '.prose, [class*="prose prose-sm"], [class*="markdown"], [class*="response-text"]'
CHAT_STREAM_CURSOR      = '[class*="cursor"], [class*="typing"], [class*="streaming"]'
CHAT_LOADING_INDICATOR  = '[class*="loading"], [class*="spinner"], [aria-busy="true"]'
CHAT_GENERATING_TEXT    = 'text=Generating...'
RECAPTCHA_FRAME         = 'iframe[src*="recaptcha"]'
SECURITY_VERIFICATION   = 'text=Security Verification'
CHAT_STOP_BUTTON        = 'button[aria-label*="stop" i], button:has-text("Stop"), button[class*="stop"]'
CHAT_COPY_BUTTON        = 'button[aria-label*="copy" i], button:has-text("Copy")'

# ── Генерация изображений ─────────────────────────────────────────────────────

IMAGE_PROMPT_INPUT      = 'textarea[placeholder*="describe" i], textarea[placeholder*="prompt" i], textarea[class*="prompt"]'
IMAGE_GENERATE_BUTTON   = 'button:has-text("Generate"), button[class*="generate"], button[type="submit"]'
IMAGE_RESULT            = 'img[class*="generated"], img[class*="result"], [class*="image-output"] img'
IMAGE_DOWNLOAD_BUTTON   = 'a[download], button[aria-label*="download" i]'

# ── Статус ────────────────────────────────────────────────────────────────────

USER_AVATAR             = '[class*="avatar"], [class*="user-menu"], img[alt*="avatar" i]'
USER_EMAIL_DISPLAY      = '[class*="user-email"], [class*="account-email"]'
LOGOUT_BUTTON           = 'button:has-text("Sign out"), button:has-text("Log out"), a:has-text("Sign out")'

# ── Уведомления и ошибки ──────────────────────────────────────────────────────

ERROR_BANNER            = '[class*="error"], [class*="alert-error"], [role="alert"][class*="error"]'
RATE_LIMIT_MSG          = 'text="rate limit" i, text="too many requests" i'
CAPTCHA_FRAME           = 'iframe[src*="captcha"], iframe[src*="hcaptcha"], iframe[src*="recaptcha"]'
