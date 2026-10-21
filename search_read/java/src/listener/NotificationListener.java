package listener;

import event.OrderEvent;
import exception.EventProcessingException;

public class NotificationListener implements IOrderEventListener {
    @Override
    public void onEvent(OrderEvent event) throws EventProcessingException {
        Order order = event.getOrder();
        System.out.println("Order processed: " + order.getOrderId() + ", Amount: " + order.getAmount());
        // Send email notification logic here
    }
}