from dotenv import load_dotenv
import os

load_dotenv()


# BUSINESS INFO
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "My Business")
BUSINESS_DESCRIPTION = os.getenv("BUSINESS_DESCRIPTION", "We are a local business")
BUSINESS_HOURS = os.getenv("BUSINESS_HOURS", "Mon-Fri 9AM-5PM")
BUSINESS_PHONE = os.getenv("BUSINESS_PHONE", "123-456-7890")
BUSINESS_ADDRESS = os.getenv("BUSINESS_ADDRESS", "123 Main St, Anytown, USA")
BUSINESS_WEBSITE = os.getenv("BUSINESS_WEBSITE", "https://example.com")

# SECURITY
PROJECT_ID = os.getenv("PROJECT_ID")
ALLOWED_DOMAINS = [d.strip() for d in os.getenv("ALLOWED_DOMAINS", "example.com").split(",") if d.strip()]
WIDGET_API_KEY = os.getenv("WIDGET_API_KEY")

# AI
API_KEY = os.getenv("API_KEY")
API_BASE = os.getenv("API_BASE")
MODEL = os.getenv("MODEL", "gpt-3.5-turbo")

# WIDGET
WIDGET_COLOR = os.getenv("WIDGET_COLOR", "#2563EB")
GREETING_MESSAGE = os.getenv("GREETING_MESSAGE", "Hi! How can I help you today?")
RATE_LIMIT = os.getenv("RATE_LIMIT", "20/minute")
QUICK_REPLIES = [r.strip() for r in os.getenv("QUICK_REPLIES", "").split(",") if r.strip()]