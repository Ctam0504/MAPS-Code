package listener;

import event.OrderEvent;
import exception.EventProcessingException;

public class AuditLogListener implements IOrderEventListener {
    @Override
    public void onEvent(OrderEvent event) throws EventProcessingException {
        // Log event history
        System.out.println("Audit Log: " + event.getEventId() + " - " + event.getTimestamp() + " - " + event.getOrder());
    }
}