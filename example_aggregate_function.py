class QScoutAggregationFunction(ABC):
    def __init__(self, context):
        pass

    @abstractmethod
    def return_vals(self):
        pass

    @abstractmethod
    def aggregate(self, cell):
        pass