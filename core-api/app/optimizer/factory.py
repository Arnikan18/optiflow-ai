import logging
from app.config.settings import settings
from app.optimizer.base import BaseOptimizer
from app.optimizer.greedy import GreedyOptimizer

logger = logging.getLogger("core-api.optimizer.factory")

class OptimizerFactory:
    """Factory class to construct and retrieve the active optimization strategy class."""
    
    @staticmethod
    def get_optimizer(strategy_name: str = None) -> BaseOptimizer:
        """Returns the appropriate BaseOptimizer strategy instance."""
        if not strategy_name:
            strategy_name = settings.optimization_strategy or "greedy"
            
        strategy_name = strategy_name.lower().strip()
        logger.info(f"Instantiating optimizer strategy: {strategy_name}")
        
        if strategy_name == "cp-sat":
            try:
                from app.optimizer.cpsat import CPSatOptimizer
                return CPSatOptimizer()
            except (ImportError, Exception) as e:
                logger.warning(f"Failed to load CPSatOptimizer: {str(e)}. Falling back to GreedyOptimizer.")
                return GreedyOptimizer()
                
        return GreedyOptimizer()
