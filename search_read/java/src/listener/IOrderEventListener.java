package listener;

import event.OrderEvent;
import exception.EventProcessingException;

public interface IOrderEventListener {
    void onEvent(OrderEvent event) throws EventProcessingException;
}