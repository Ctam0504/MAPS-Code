package service;

import bus.EventBus;
import event.OrderEvent;
import model.Order;
import model.OrderStatus;
import exception.EventProcessingException;
import listener.IOrderEventListener;

public class OrderService {
    private EventBus eventBus;

    public OrderService(EventBus eventBus) {
        this.eventBus = eventBus;
    }

    public Order createOrder(String orderId, double amount) {
        if (amount <= 0) {
            throw new IllegalArgumentException("Amount must be greater than 0");
        }
        Order order = new Order(orderId, amount);
        eventBus.publishEvent(new OrderEvent(System.currentTimeMillis(), order, OrderStatus.PENDING));
        return order;
    }

    public void processOrder(Order order) {
        if (order.getAmount() > 0) {
            order.setStatus(OrderStatus.PAID);
            eventBus.publishEvent(new OrderEvent(System.currentTimeMillis(), order, OrderStatus.PAID));
        } else {
            order.setStatus(OrderStatus.CANCELLED);
            eventBus.publishEvent(new OrderEvent(System.currentTimeMillis(), order, OrderStatus.CANCELLED));
        }
    }
}