import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class TestHarness {
    @Test
    void testCreateOrder() {
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
            assertEquals(OrderStatus.PENDING, order.getStatus(), "Order status should be PENDING");
        } catch (IllegalArgumentException e) {
            fail("Should not throw IllegalArgumentException for valid order");
        }
    }

    @Test
    void testProcessOrder() {
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
            assertEquals(OrderStatus.PAID, order.getStatus(), "Order status should be PAID");
        } catch (EventProcessingException e) {
            fail("Should not throw EventProcessingException for valid order");
        }
    }

    @Test
    void testProcessOrderWithNegativeAmount() {
        EventBus eventBus = new EventBus();
        OrderService orderService = new OrderService(eventBus);
        PaymentListener paymentListener = new PaymentListener();
        NotificationListener notificationListener = new NotificationListener();
        AuditLogListener auditLogListener = new AuditLogListener();
        eventBus.registerListener(paymentListener);
        eventBus.registerListener(notificationListener);
        eventBus.registerListener(auditLogListener);
        try {
            Order order = orderService.createOrder("123", -100.0);
            orderService.processOrder(order);
            fail("Should throw IllegalArgumentException for negative amount");
        } catch (IllegalArgumentException e) {
            assertEquals("Amount must be greater than 0", e.getMessage(), "Exception message should be 'Amount must be greater than 0'");
        }
    }

    @Test
    void testProcessOrderWithZeroAmount() {
        EventBus eventBus = new EventBus();
        OrderService orderService = new OrderService(eventBus);
        PaymentListener paymentListener = new PaymentListener();
        NotificationListener notificationListener = new NotificationListener();
        AuditLogListener auditLogListener = new AuditLogListener();
        eventBus.registerListener(paymentListener);
        eventBus.registerListener(notificationListener);
        eventBus.registerListener(auditLogListener);
        try {
            Order order = orderService.createOrder("123", 0.0);
            orderService.processOrder(order);
            fail("Should throw IllegalArgumentException for zero amount");
        } catch (IllegalArgumentException e) {
            assertEquals("Amount must be greater than 0", e.getMessage(), "Exception message should be 'Amount must be greater than 0'");
        }
    }
}