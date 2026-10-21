package event;

import model.Order;

public class OrderEvent {
    private String eventId;
    private Order order;
    private long timestamp;

    public OrderEvent(String eventId, Order order, long timestamp) {
        this.eventId = eventId;
        this.order = order;
        this.timestamp = timestamp;
    }

    public String getEventId() {
        return eventId;
    }

    public Order getOrder() {
        return order;
    }

    public long getTimestamp() {
        return timestamp;
    }
}