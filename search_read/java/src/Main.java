package Main;

import bus.EventBus;
import event.OrderEvent;
import model.Order;
import model.OrderStatus;
import exception.EventProcessingException;
import listener.IOrderEventListener;
import listener.PaymentListener;
import listener.NotificationListener;
import listener.AuditLogListener;
import service.OrderService;

public class Main {
    public static void main(String[] args) {
        EventBus eventBus = new EventBus();
        OrderService orderService = new OrderService(eventBus);
        PaymentListener paymentListener = new PaymentListener();
        NotificationListener notificationListener = new NotificationListener();
        AuditLogListener auditLogListener = new AuditLogListener();
        eventBus.registerListener(paymentListener);
        eventBus.registerListener(notificationListener);
        eventBus.registerListener(auditLogListener);
        try {
            Order order = orderService.createOrder("123", 100.0);
            orderService.processOrder(order);
        } catch (EventProcessingException e) {
            System.err.println(e.getMessage());
        }
    }
}