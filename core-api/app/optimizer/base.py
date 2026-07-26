from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseOptimizer(ABC):
    """Abstract interface defining the contract for scheduling plan optimizers."""
    
    @abstractmethod
    def generate_plans(
        self,
        customers: List[Dict[str, Any]],
        escalations: List[Dict[str, Any]],
        specialists: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generates candidate optimization plans given the input entities."""
        pass
