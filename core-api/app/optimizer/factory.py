import logging
from app.config.settings import settings
from app.optimizer.base import BaseOptimizer
from app.optimizer.greedy import GreedyOptimizer

logger = logging.getLogger("core-api.optimizer.factory")

class OptimizerFactory:
    """Factory class to construct and retrieve the active optimization strategy class."""
    
    @staticmethod
    def get_optimizer(strategy_name: str | None = None) -> BaseOptimizer:
        """Returns the appropriate BaseOptimizer strategy instance."""
        if not strategy_name:
            strategy_name = settings.optimizer_provider or settings.optimization_strategy or "cp_sat"
            
        strategy_name = strategy_name.lower().strip().replace("_", "-")
        logger.info("Instantiating optimizer strategy: %s", strategy_name)
        
        if strategy_name in ("cp-sat", "cpsat"):
            from app.optimizer.cpsat import CPSatOptimizer
            return CPSatOptimizer()
                
        if strategy_name == "greedy":
            return GreedyOptimizer()

        raise ValueError(f"Unsupported optimizer provider: {strategy_name}")
