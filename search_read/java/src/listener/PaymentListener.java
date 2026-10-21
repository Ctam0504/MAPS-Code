package listener;

import event.OrderEvent;
import model.Order;
import model.OrderStatus;
import exception.EventProcessingException;

public class PaymentListener implements IOrderEventListener {
    @Override
    public void onEvent(OrderEvent event) throws EventProcessingException {
        Order order = event.getOrder();
        if (order != null) {
            order.setStatus(OrderStatus.PAID);
        } else {
            throw new EventProcessingException("Order is null in PaymentListener");
        }
    }
}