from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bing_search_key: str = ""
    bing_search_endpoint: str = "https://api.bing.microsoft.com/v7.0/search"
    bing_news_endpoint: str = "https://api.microsoft.ai/v3/search/news"
    bing_finance_endpoint: str = "https://api.microsoft.ai/v3/search/finance"
    bing_places_endpoint: str = "https://api.microsoft.ai/v3/search/places"

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_planner_model: str = "gpt-4o"
    openai_synth_model: str = "gpt-4o-mini"
    openai_timeout: float = 120.0
    openai_planner_effort: str = "low"

    max_depth: int = 3
    expand_per_level: int = 2


settings = Settings()
