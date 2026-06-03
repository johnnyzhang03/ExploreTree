from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bing_search_key: str = ""
    bing_search_endpoint: str = "https://api.bing.microsoft.com/v7.0/search"

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_planner_model: str = "gpt-4o"
    openai_synth_model: str = "gpt-4o-mini"


settings = Settings()
