"""Workflow node registration mechanism

Uses a decorator to automatically register workflow nodes, supporting
Pydantic models and metadata.
"""

from typing import Dict, Callable, List, Optional
from loguru import logger
import inspect

from .types import NodeMetadata


# Node registry
_NODE_REGISTRY: Dict[str, NodeMetadata] = {}


def register_node(cls):
    """Class decorator: register a class-based workflow node
    
    Directly calls the node class's get_metadata() method to obtain a NodeMetadata object.
    """
    if not inspect.isclass(cls):
        raise TypeError("@register_node must be used on a class")

    # Check required attributes
    node_type = getattr(cls, "node_type", None)
    if not node_type:
        raise ValueError(f"Node class {cls.__name__} must define 'node_type'")

    # Directly call the node's get_metadata() method, returning a NodeMetadata object
    metadata = cls.get_metadata()
    
    _NODE_REGISTRY[node_type] = metadata
    logger.debug(f"[Node Registration] {node_type} ({metadata.category}) -> {cls.__name__}")
    return cls


def get_registered_nodes() -> Dict[str, Callable]:
    """Get all registered node executors
    
    Returns:
        Mapping from node type to executor class
    """
    return {type_name: meta.executor for type_name, meta in _NODE_REGISTRY.items()}


def get_node_metadata(node_type: str) -> Optional[NodeMetadata]:
    """Get node metadata
    
    Args:
        node_type: Node type
        
    Returns:
        Node metadata, or None if it does not exist
    """
    return _NODE_REGISTRY.get(node_type)


def get_all_node_metadata() -> List[NodeMetadata]:
    """Get all node metadata
    
    Returns:
        List of node metadata
    """
    return list(_NODE_REGISTRY.values())


def get_node_types() -> List[str]:
    """Get all registered node type names
    
    Returns:
        List of node type names
    """
    return list(_NODE_REGISTRY.keys())


def get_nodes_by_category(category: str) -> List[NodeMetadata]:
    """Get nodes by category
    
    Args:
        category: Category name
        
    Returns:
        All node metadata in that category
    """
    return [meta for meta in _NODE_REGISTRY.values() if meta.category == category]


class NodeRegistry:
    """Node registry wrapper class
    
    Provides node type checking and retrieval interfaces
    """

    def has_node(self, node_type: str) -> bool:
        """Check whether a node type exists"""
        return node_type in _NODE_REGISTRY

    def get(self, node_type: str) -> Optional[Callable]:
        """Get a node executor"""
        meta = _NODE_REGISTRY.get(node_type)
        return meta.executor if meta else None
    
    def list_nodes(self) -> List[str]:
        """List all registered node types"""
        return list(_NODE_REGISTRY.keys())


def discover_workflow_nodes():
    """Log the number of registered workflow nodes

    All workflow node modules are imported in app.services.workflow.__init__.py,
    and decorators automatically perform registration at package import time.
    """
    logger.info(f"[Node Discovery] Loaded {len(_NODE_REGISTRY)} workflow nodes")

    # Count by category
    categories = {}
    for meta in _NODE_REGISTRY.values():
        categories[meta.category] = categories.get(meta.category, 0) + 1

    for cat, count in categories.items():
        logger.debug(f"  - {cat}: {count} nodes")