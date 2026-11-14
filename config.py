import os
import json

class Config:
    def __init__(self):
        self.dev = os.getenv("DEV", "false").lower() == "true"
        self.log_requests = self.dev
        self.log_responses = self.dev
        self.log_level = "DEBUG" if self.dev else "INFO"
    
    @classmethod
    def load(cls):
        config_file = "config.json"
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                data = json.load(f)
                instance = cls()
                for key, value in data.items():
                    if hasattr(instance, key):
                        setattr(instance, key, value)
                return instance
        return cls()

config = Config.load()
