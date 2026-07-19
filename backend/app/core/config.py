"""Application configuration management

Unified management of all configuration items, supporting environment variables and default values.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    
    # Database path
    db_path: Optional[str] = Field(default=None, alias="NOVELFORGE_DB_PATH")
    
    # Whether to print SQL logs
    echo: bool = Field(default=False, alias="DB_ECHO")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields
    
    def get_database_url(self) -> str:
        """Get database URL
        
        Strategy:
        1) Packaged (onefile/onedir): prefer placing alongside the executable
        2) Development: place in the source backend directory
        3) Support overriding the absolute path via the NOVELFORGE_DB_PATH environment variable (compatible with the legacy variable AIAUTHOR_DB_PATH)
        
        Returns:
            Database URL
        """
        override_path = self.db_path or os.getenv("AIAUTHOR_DB_PATH")
        if override_path:
            db_file = Path(override_path)
        else:
            if getattr(sys, "frozen", False):
                base_dir = Path(sys.executable).resolve().parent
            else:
                # Go up 2 levels from app/core/config.py to backend/
                # config.py -> core/ -> app/ -> backend/
                base_dir = Path(__file__).resolve().parents[2]
            db_file = base_dir / 'novelforge.db'
        
        return f"sqlite:///{db_file.as_posix()}"


class KnowledgeGraphSettings(BaseSettings):
    """Knowledge graph configuration"""
    
    # Knowledge graph provider
    provider: str = Field(default="sqlmodel", alias="KNOWLEDGE_GRAPH_PROVIDER")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields


class Neo4jSettings(BaseSettings):
    """Neo4j graph database configuration"""
    
    uri: str = Field(default="neo4j://127.0.0.1:7687", alias="NEO4J_URI")
    user: str = Field(default="neo4j", alias="NEO4J_USER")
    password: str = Field(default="neo4j", alias="NEO4J_PASSWORD")
    
    # Compatible with legacy environment variables
    graph_db_uri: Optional[str] = Field(default=None, alias="GRAPH_DB_URI")
    graph_db_user: Optional[str] = Field(default=None, alias="GRAPH_DB_USER")
    graph_db_password: Optional[str] = Field(default=None, alias="GRAPH_DB_PASSWORD")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields
    
    def get_uri(self) -> str:
        """Get URI (compatible with legacy environment variables)"""
        return self.graph_db_uri or self.uri
    
    def get_user(self) -> str:
        """Get username (compatible with legacy environment variables)"""
        return self.graph_db_user or self.user
    
    def get_password(self) -> str:
        """Get password (compatible with legacy environment variables)"""
        return self.graph_db_password or self.password


class BootstrapSettings(BaseSettings):
    """Startup initialization configuration"""
    
    # Whether to overwrite built-in data (prompts, knowledge bases, etc.)
    overwrite: bool = Field(default=True, alias="BOOTSTRAP_OVERWRITE")
    # Whether to overwrite built-in card type schemas
    overwrite_card_schemas: bool = Field(default=False, alias="BOOTSTRAP_OVERWRITE_CARD_SCHEMAS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields
    
    @property
    def should_overwrite(self) -> bool:
        """Whether to overwrite updates
        
        Supports multiple formats: true/false, 1/0, yes/no, on/off
        
        Returns:
            Whether to overwrite
        """
        if isinstance(self.overwrite, bool):
            return self.overwrite
        return str(self.overwrite).lower() in ('1', 'true', 'yes', 'on')

    @property
    def should_overwrite_card_schemas(self) -> bool:
        """Whether to overwrite built-in card type schemas."""
        if isinstance(self.overwrite_card_schemas, bool):
            return self.overwrite_card_schemas
        return str(self.overwrite_card_schemas).lower() in ('1', 'true', 'yes', 'on')


class AISettings(BaseSettings):
    """AI-related configuration"""
    
    # Maximum retry count on model call failure
    max_tool_call_retries: int = Field(default=3, alias="MAX_TOOL_CALL_RETRIES")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields


class AppSettings(BaseSettings):
    """Application configuration"""
    
    # Application name
    app_name: str = Field(default="NovelForge", alias="APP_NAME")
    
    # Application version
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    
    # Whether to enable debug mode
    debug: bool = Field(default=False, alias="DEBUG")
    
    # API prefix
    api_prefix: str = Field(default="/api", alias="API_PREFIX")
    
    # CORS allowed origins
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields
    
    def get_cors_origins_list(self) -> list:
        """Get CORS origin list
        
        Returns:
            Origin list
        """
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


class WorkflowSettings(BaseSettings):
    """Workflow configuration"""
    
    # Persistence record retention period (days)
    retention_persistent_days: int = Field(default=30, alias="WORKFLOW_RETENTION_PERSISTENT_DAYS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


class Settings:
    """Global configuration object"""
    
    def __init__(self):
        self.database = DatabaseSettings()
        self.kg = KnowledgeGraphSettings()
        self.neo4j = Neo4jSettings()
        self.ai = AISettings()
        self.bootstrap = BootstrapSettings()
        self.workflow = WorkflowSettings()
        self.app = AppSettings()
    
    def __repr__(self) -> str:
        return (
            f"Settings(\n"
            f"  database_url={self.database.get_database_url()},\n"
            f"  kg_provider={self.kg.provider},\n"
            f"  neo4j_uri={self.neo4j.get_uri()},\n"
            f"  max_retries={self.ai.max_tool_call_retries},\n"
            f"  bootstrap_overwrite={self.bootstrap.should_overwrite},\n"
            f"  bootstrap_overwrite_card_schemas={self.bootstrap.should_overwrite_card_schemas},\n"
            f"  app_name={self.app.app_name}\n"
            f")"
        )


# Global configuration instance
settings = Settings()